# NapCat (Docker) 在线监控 —— 每 60 秒探测一次小号是否在线
# 判断依据：调用 OneBot HTTP API /get_status，看 data.online 是否为 true（被踢下线时为 false）
# 注意：不能用 /get_login_info 判断，它只返回本地缓存的账号信息，进程活着就永远返回 ok
$ErrorActionPreference = 'SilentlyContinue'
$api     = 'http://127.0.0.1:3000/get_login_info'  # 仅用于取昵称
$statApi = 'http://127.0.0.1:3000/get_status'       # 判断真实在线状态
$webui = 'http://127.0.0.1:6099/webui?token=napcat123456'

Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  NapCat 在线监控 (每 60 秒一次)' -ForegroundColor Cyan
Write-Host '  关闭本窗口即停止监控，不影响容器运行' -ForegroundColor DarkGray
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''

while ($true) {
    $ts = Get-Date -Format 'MM-dd HH:mm:ss'
    $online = $false
    $nick = ''
    try {
        $s = Invoke-RestMethod -Uri $statApi -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 8
        if ($s.status -eq 'ok' -and $s.data.online -eq $true) {
            $online = $true
            $r = Invoke-RestMethod -Uri $api -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 8
            $nick = "$($r.data.nickname) ($($r.data.user_id))"
        }
    } catch { }

    if ($online) {
        Write-Host "[$ts] OK 在线  $nick" -ForegroundColor Green
    } else {
        Write-Host "[$ts] XX 离线/无响应 —— QQ 可能被踢或容器异常!" -ForegroundColor Red
        Write-Host "         重新扫码: $webui" -ForegroundColor Yellow
        Write-Host "         --- 最近日志 ---" -ForegroundColor DarkGray
        docker logs napcat --tail 8 2>&1 | ForEach-Object { Write-Host "         $_" -ForegroundColor DarkGray }
    }
    Start-Sleep -Seconds 60
}
