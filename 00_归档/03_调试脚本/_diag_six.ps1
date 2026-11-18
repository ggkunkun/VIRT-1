$ErrorActionPreference = 'Continue'
$out = @()
$lnks = @(
  'C:\Users\Public\Desktop\AutoCAD 2026 - 简体中文 (Simplified Chinese).lnk',
  'C:\Users\Public\Desktop\CIMCO Edit 2026.lnk',
  'C:\Users\Public\Desktop\Vericut 9.6.lnk',
  'C:\Users\Public\Desktop\SOLIDWORKS 2021.lnk',
  'C:\Users\Public\Desktop\斯沃数控仿真软件.lnk',
  'C:\Users\Administrator\Desktop\中文版NX12.0.lnk'
)
$sh = New-Object -ComObject WScript.Shell
foreach ($l in $lnks) {
  if (Test-Path -LiteralPath $l) {
    $s = $sh.CreateShortcut($l)
    $out += "[$([IO.Path]::GetFileNameWithoutExtension($l))]`nTarget=$($s.TargetPath)`nArgs=$($s.Arguments)`nWorkDir=$($s.WorkingDirectory)"
  } else {
    $out += "[$l] MISSING"
  }
}
$out -join "`r`n" | Out-File -FilePath 'D:\Virtu模型\_lnk_resolve.txt' -Encoding utf8

& 'C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\reverse-skill\skills\scripts\master-route.ps1' -Hint '逆向六大工业软件功能模块：SOLIDWORKS 2021、AutoCAD 2026、NX 12.0、CIMCO Edit 2026、VERICUT 9.6、斯沃数控仿真 SSCNC 7.2' *> 'D:\Virtu模型\_route_run.txt'

'DONE' | Out-File -FilePath 'D:\Virtu模型\_diag_done.txt' -Encoding utf8
