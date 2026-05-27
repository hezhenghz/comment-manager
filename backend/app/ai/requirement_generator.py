"""
需求描述生成器：将玩家反馈快照转化为开发导向的需求描述。
生成格式：方案导向，开发者视角，可直接作为 Claude Code 的输入。
"""
import logging

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是一名游戏产品经理，负责将玩家反馈转化为开发需求描述。

要求：
- 使用开发者视角，方案导向
- 直接描述"需要新增/修改/修复什么"，不做文字润色
- 格式简洁清晰，50~150字
- 可直接作为 Claude Code 的输入（开发修改指令格式）

示例（不要复制，仅参考风格）：
- "在用户登录流程（auth/login.py）中增加异常捕获，记录崩溃日志到 Sentry，并向用户展示友好的错误提示页面"
- "将每日任务奖励金币从 100 提升至 200，修改 rewards/daily.py 中 DAILY_COIN_REWARD 常量"
"""

_CATEGORY_LABEL = {
    "bug": "Bug/故障",
    "suggestion": "功能建议",
    "complaint": "用户投诉",
    "praise": "好评",
    "other": "其他",
}

_SOURCE_TYPE_LABEL = {
    "comment": "玩家评论",
    "bug": "Bug 反馈",
    "suggestion": "功能建议",
    "topic": "群聊话题",
}


async def generate_requirement_text(snapshot: dict) -> str:
    """
    根据玩家反馈快照生成开发需求描述。
    snapshot 字段（来自 Comment 或 QQTopic）：
      content / summary, author_name, platform, category, sentiment, source_url
      或（话题）title, summary, category, sentiment, comment_count
    """
    from app.ai.router import get_ai_router

    source_type = snapshot.get("source_type", "")
    content = snapshot.get("content") or snapshot.get("summary") or ""
    title = snapshot.get("title", "")
    category = snapshot.get("category", "")
    sentiment = snapshot.get("sentiment", "")
    ai_summary = snapshot.get("summary", "") if source_type != "topic" else ""
    platform = snapshot.get("platform", "")

    category_label = _CATEGORY_LABEL.get(category, category)
    source_label = _SOURCE_TYPE_LABEL.get(source_type, source_type)

    lines = [f"来源：{source_label}"]
    if platform:
        lines.append(f"平台：{platform}")
    if category_label:
        lines.append(f"分类：{category_label}")
    if sentiment:
        lines.append(f"情感：{sentiment}")
    if title:
        lines.append(f"话题标题：{title}")
    lines.append(f"\n玩家原始反馈：\n{content[:500]}")
    if ai_summary and ai_summary != content:
        lines.append(f"\nAI 摘要：{ai_summary[:200]}")

    user_msg = "\n".join(lines)

    router = get_ai_router()
    try:
        result = await router.chat(_SYSTEM_PROMPT, user_msg, temperature=0.3, max_tokens=300)
        return result.strip()
    except Exception as e:
        logger.warning(f"[requirement_generator] AI 生成失败，使用 fallback: {e}")
        # fallback：返回 title 或 content 前 200 字
        return (title or content)[:200]
