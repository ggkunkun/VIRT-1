$targets = Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like '*_probe6.py*' }
foreach ($t in $targets) {
    Write-Output ("Killing PID {0}: {1}" -f $t.ProcessId, $t.CommandLine)
    Stop-Process -Id $t.ProcessId -Force -ErrorAction SilentlyContinue
}
Write-Output "KILL_DONE"
