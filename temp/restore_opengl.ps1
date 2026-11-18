# Restore original system opengl32.dll
$ErrorActionPreference = 'Stop'
$sys = 'C:\Windows\System32\opengl32.dll'
$bak = 'C:\Windows\System32\opengl32.dll.mesa_backup_20261117'
if (Test-Path $bak) {
    takeown /f $sys /a | Out-Null
    icacls $sys /grant '*S-1-5-32-544:F' | Out-Null
    Copy-Item $bak $sys -Force
    "restored $sys from $bak" | Tee-Object -FilePath 'd:\Virtu模型\temp\mesa_restore.log' -Append
} else { 'backup missing' }
