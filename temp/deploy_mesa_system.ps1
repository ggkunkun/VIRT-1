# Deploy Mesa llvmpipe as system-wide opengl32.dll (with backup)
$ErrorActionPreference = 'Stop'
$log = 'd:\Virtu模型\temp\mesa_deploy.log'
function Log($m) { $m | Tee-Object -FilePath $log -Append }
"=== Mesa system deploy $(Get-Date -Format o) ===" | Out-File $log -Encoding UTF8

$sys = 'C:\Windows\System32\opengl32.dll'
$bak = 'C:\Windows\System32\opengl32.dll.mesa_backup_20261117'
$wsBak = 'd:\Virtu模型\temp\opengl32.dll.original'

if (-not (Test-Path $bak)) {
    Copy-Item $sys $bak -Force
    Log "backup -> $bak"
} else { Log "backup exists: $bak" }
if (-not (Test-Path $wsBak)) { Copy-Item $sys $wsBak -Force; Log "workspace backup -> $wsBak" }

$src = 'd:\Virtu模型\temp\mesa-mingw\x64'
foreach ($f in @('opengl32.dll', 'libgallium_wgl.dll', 'dxil.dll', 'libdlclose-skip.dll')) {
    $dst = Join-Path $env:WINDIR "System32\$f"
    if (Test-Path $dst) { takeown /f $dst /a | Out-Null; icacls $dst /grant '*S-1-5-32-544:F' | Out-Null }
    if ($f -eq 'opengl32.dll') {
        $aside = Join-Path $env:WINDIR 'System32\opengl32.dll.mesa_aside'
        if (Test-Path $aside) { Remove-Item $aside -Force -ErrorAction SilentlyContinue }
        try { Move-Item $dst $aside -Force; Log "renamed original -> $aside" }
        catch { Log ("rename original failed: {0}" -f $_.Exception.Message) }
    }
    Copy-Item (Join-Path $src $f) $dst -Force
    $h = (Get-Item $dst)
    Log ("deployed {0} ({1} bytes)" -f $f, $h.Length)
}
# restore ownership/message
takeown /f $sys /a | Out-Null
Log 'DONE'
