"""NapCat 掉线自动重启看门狗。

背景：NapCat/QQ 已知风控问题（NapNeko/NapCatQQ#1728、#1636），号挂几小时被踢，
NapCat 侧无法根治；缓解办法是掉线后重启容器靠快登恢复。本看门狗让这一恢复无人值守。

工作流（每 napcat_poll_interval_seconds 跑一次）：
  get_status → 连续 2 次 online=false 才 docker restart napcat
  → 等 ~90s 看是否快登恢复
  → 恢复：QQ 私聊管理员通知；仍离线：钉钉带外告警（号离线发不出 QQ）
带 10min 冷却 + 每日 6 次上限，超限只告警不再重启，避免把号弄更严。

判据说明：只信 /get_status 的 data.online。日志里每 30 分钟的"账号状态变更为离线"
是在线状态显示的假信号（机器人仍在收消息），不作为触发条件。
"""
import asyncio
import logging
import subprocess
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.napcat.client import get_status, send_private_msg
from app.alerts.dingtalk import send_watchdog_alert

logger = logging.getLogger(__name__)
watchdog_scheduler = AsyncIOScheduler()

# 模块级状态（单进程足够）
_consecutive_offline = 0          # 连续检测到离线的次数
_restart_times: list[datetime] = []  # 最近的重启时间戳（utc），用于每日上限
_cooling_until: datetime | None = None  # 冷却截止时间，此前不检测/不重启
_watchdog_running = False         # 防止两次 tick 重叠（重启后会 sleep 90s）

_RESTART_WAIT_SECONDS = 90        # 重启后等待启动+快登的时间


def start_napcat_watchdog() -> None:
    settings = get_settings()
    if not settings.napcat_watchdog_enabled:
        logger.info("[watchdog] 未启用（NAPCAT_WATCHDOG_ENABLED=false），跳过")
        return
    if not settings.qq_napcat_url:
        logger.warning("[watchdog] QQ_NAPCAT_URL 未配置，看门狗不启动")
        return
    watchdog_scheduler.add_job(
        watchdog_tick,
        "interval",
        seconds=settings.napcat_poll_interval_seconds,
        id="napcat_watchdog",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.utcnow() + timedelta(seconds=30),  # 启动 30s 后首跑
    )
    watchdog_scheduler.start()
    logger.info(
        f"[watchdog] 已启动，轮询={settings.napcat_poll_interval_seconds}s，"
        f"容器={settings.napcat_container_name}，冷却={settings.napcat_restart_cooldown_minutes}min，"
        f"每日上限={settings.napcat_restart_daily_limit}次"
    )


async def watchdog_tick() -> None:
    global _consecutive_offline, _cooling_until, _watchdog_running
    if _watchdog_running:
        return
    _watchdog_running = True
    try:
        now = datetime.utcnow()

        # 1. 冷却中：跳过
        if _cooling_until and now < _cooling_until:
            return

        # 2. 查在线状态
        online = await get_status()

        # 3. 在线：清零计数
        if online:
            _consecutive_offline = 0
            return

        # 4. 离线：连续 2 次才动作
        _consecutive_offline += 1
        logger.warning(f"[watchdog] 检测到离线（连续 {_consecutive_offline} 次）")
        if _consecutive_offline < 2:
            return

        # 5. 检查每日上限
        settings = get_settings()
        cutoff = now - timedelta(hours=24)
        _restart_times[:] = [t for t in _restart_times if t > cutoff]
        if len(_restart_times) >= settings.napcat_restart_daily_limit:
            logger.error("[watchdog] 已达每日重启上限，停止自动重启，发告警")
            await send_watchdog_alert(
                f"⚠️ NapCat「小阿月」24h 内已自动重启 {len(_restart_times)} 次仍掉线，"
                f"已达上限（{settings.napcat_restart_daily_limit}），停止自动重启，请人工介入排查风控。"
            )
            _consecutive_offline = 0
            _cooling_until = now + timedelta(minutes=settings.napcat_restart_cooldown_minutes)
            return

        # 6. 执行重启
        await _restart_and_verify(settings, now)
    finally:
        _watchdog_running = False


async def _restart_and_verify(settings, now: datetime) -> None:
    global _consecutive_offline, _cooling_until

    container = settings.napcat_container_name
    logger.warning(f"[watchdog] 连续离线，执行 docker restart {container}")

    # 状态先行更新：无论重启成功与否，都进入冷却并计入当日次数，
    # 避免重启命令本身失败时下一轮立刻重试把号弄更严。
    _restart_times.append(now)
    _cooling_until = now + timedelta(minutes=settings.napcat_restart_cooldown_minutes)
    _consecutive_offline = 0

    ok = await _docker_restart(container)
    if not ok:
        await send_watchdog_alert(
            f"🔴 NapCat 看门狗执行 `docker restart {container}` 失败，请检查 Docker 与容器名。"
        )
        return

    # 等启动 + 快登
    await asyncio.sleep(_RESTART_WAIT_SECONDS)

    online = await get_status()
    if online:
        logger.info("[watchdog] 重启后已恢复在线，发 QQ 私聊通知")
        await send_private_msg(
            settings.napcat_admin_qq,
            "✅ 「小阿月」被踢后已自动重启并恢复在线。",
        )
    else:
        logger.error("[watchdog] 重启后仍离线，需扫码，发钉钉告警")
        await send_watchdog_alert(
            f"🔴 「小阿月」被踢，自动重启后仍未恢复（快登失败），"
            f"需要你去 WebUI 扫码登录：{settings.napcat_webui_url}"
        )


def _docker_restart_sync(container: str) -> bool:
    """同步执行 docker restart。"""
    try:
        r = subprocess.run(
            ["docker", "restart", container],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0:
            logger.info(f"[watchdog] docker restart {container} 成功")
            return True
        logger.error(f"[watchdog] docker restart 返回 {r.returncode}: {r.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"[watchdog] docker restart 异常: {e}")
        return False


async def _docker_restart(container: str) -> bool:
    """在线程里跑同步 subprocess.run。

    不能用 asyncio.create_subprocess_exec：uvicorn 在 Windows 用 SelectorEventLoop，
    该 loop 不支持子进程创建，会抛 NotImplementedError（参见 xiaoheihe 模块注释）。
    docker restart 很快返回，放线程池里跑即可。
    """
    return await asyncio.to_thread(_docker_restart_sync, container)
