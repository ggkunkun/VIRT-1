# 重启 WorkBuddy (Trae CN) 以刷新模型列表。
# 由计划任务 VirtuRestartWorkBuddy 在独立进程中执行，避免随会话进程一起被杀。
$ErrorActionPreference = 'SilentlyContinue'
$log = 'd:\Virtu模型\logs\workbuddy_restart.log'
function Write-Log([string]$msg) {
    Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg) -Encoding utf8
}

Write-Log 'restart script started'
Start-Sleep -Seconds 35

$exe = Join-Path $env:LOCALAPPDATA 'Programs\Trae CN\Trae CN.exe'
if (-not (Test-Path $exe)) {
    Write-Log "exe not found: $exe"
    exit 1
}

$procs = @(Get-Process 'Trae CN' -ErrorAction SilentlyContinue)
Write-Log ("stopping {0} Trae CN processes" -f $procs.Count)
$main = $procs | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if ($main) { $null = $main.CloseMainWindow() }

Start-Sleep -Seconds 6
Get-Process 'Trae CN' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe)
Start-Sleep -Seconds 6

$new = @(Get-Process 'Trae CN' -ErrorAction SilentlyContinue)
Write-Log ("relaunched, processes={0}" -f $new.Count)

# 一次性任务，执行完自删除
schtasks /Delete /TN "VirtuRestartWorkBuddy" /F | Out-Null
Write-Log 'done'
