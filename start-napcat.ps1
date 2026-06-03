# NapCat 已迁移到 Docker 运行（小号 3144134899 小阿月），与本机大号 QQ 隔离。
# 工作目录：D:\napcat-docker  | OneBot HTTP API: http://127.0.0.1:3000 | WebUI: http://127.0.0.1:6099
$ErrorActionPreference = 'Stop'
$compose = 'D:\napcat-docker\docker-compose.yml'

Write-Host '正在启动 NapCat (Docker)...' -ForegroundColor Cyan
docker compose -f $compose up -d

# 等待容器内 QQ 用持久化登录态自动恢复，并探测 OneBot HTTP API 是否就绪
Write-Host '等待 NapCat 登录并就绪 (最多 60 秒)...' -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-RestMethod -Uri 'http://127.0.0.1:3000/get_login_info' -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 5
        if ($r.status -eq 'ok') {
            Write-Host "NapCat 已在线: $($r.data.nickname) ($($r.data.user_id))" -ForegroundColor Green
            $ok = $true
            break
        }
    } catch { }
}

if (-not $ok) {
    Write-Host '⚠ NapCat 60 秒内未就绪，可能被风控踢下线，需要重新扫码。' -ForegroundColor Yellow
    Write-Host '  扫码方式: 浏览器打开 http://127.0.0.1:6099/webui?token=napcat123456' -ForegroundColor Yellow
    Write-Host '  或查看日志: docker logs napcat --tail 40' -ForegroundColor Yellow
}

Write-Host ''
Write-Host '实时日志 (Ctrl+C 退出不影响容器后台运行):' -ForegroundColor Cyan
docker logs -f napcat
