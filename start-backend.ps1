# 启动后端 — 自动清理残留 Python 进程再启动
# 用法：在项目根目录执行  .\start-backend.ps1
param(
    [int]$Port = 8001
)

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"

# 1. 找出占用端口的进程并杀掉
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    $ownerPid = $conn.OwningProcess
    if ($ownerPid -gt 0) {
        Write-Host "端口 $Port 被 PID=$ownerPid 占用，正在终止..."
        Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
    } else {
        # 孤儿 socket（进程已死但 socket 未释放），清理所有 python 进程
        Write-Host "端口 $Port 存在孤儿 socket，清理所有 Python 进程..."
        Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 800
}

# 2. 启动后端
Write-Host "启动后端，端口 $Port ..."
Set-Location "$PSScriptRoot\backend"
..\.venv\Scripts\uvicorn app.main:app --reload --port $Port --host 0.0.0.0
