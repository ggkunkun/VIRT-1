# Virtu 模型本机适配一键部署脚本
# 基线硬件：RTX 4050 Laptop 6GB / i5-12450H / 16GB RAM / Ollama 0.40.14
# 作用：按实测最优参数创建 virtu-opt-* 部署 tag（不改动任何原有模型），并预热验证

$ErrorActionPreference = 'Stop'
$DeployDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "===== 1. 检查 Ollama 服务 =====" -ForegroundColor Cyan
try {
    $v = (Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 5).version
    Write-Host "  Ollama $v 已就绪"
} catch {
    Write-Host "  Ollama 未运行，请先启动：" -ForegroundColor Yellow
    Write-Host "  Start-Process 'E:\OllamaApp\ollama.exe' -ArgumentList 'serve'"
    exit 1
}

Write-Host "===== 2. 创建适配版部署 tag =====" -ForegroundColor Cyan
$map = @(
    @{ Tag = 'virtu-opt-8b';      File = 'Modelfile.virtu-opt-8b' },
    @{ Tag = 'virtu-opt-8b-ties'; File = 'Modelfile.virtu-opt-8b-ties' },
    @{ Tag = 'virtu-opt-8b-v3';   File = 'Modelfile.virtu-opt-8b-v3' },
    @{ Tag = 'virtu-opt-13b';     File = 'Modelfile.virtu-opt-13b' },
    @{ Tag = 'virtu-opt-moe14b';  File = 'Modelfile.virtu-opt-moe14b' },
    @{ Tag = 'virtu-opt-13b-q4';  File = 'Modelfile.virtu-opt-13b-q4' }
)
foreach ($m in $map) {
    $mf = Join-Path $DeployDir $m.File
    if (-not (Test-Path $mf)) { Write-Host "  跳过 $($m.Tag)（缺少 $($m.File)）" -ForegroundColor Yellow; continue }
    Write-Host "  -> $($m.Tag)"
    & ollama create $m.Tag -f $mf
}

Write-Host "===== 3. 预热与实测 =====" -ForegroundColor Cyan
function Test-Model($tag) {
    $body = @{
        model    = $tag
        messages = @(@{ role = 'user'; content = '用一句话说明数控加工中心。' })
        stream   = $false
        keep_alive = '3m'
    } | ConvertTo-Json -Depth 6
    try {
        $r = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/chat' -Method Post `
            -Body $body -ContentType 'application/json' -TimeoutSec 600
        $tps = [math]::Round($r.eval_count / ($r.eval_duration / 1e9), 2)
        Write-Host ("  {0,-20} {1,8} tok/s   load={2}s" -f $tag, $tps, [math]::Round($r.load_duration/1e9,1)) -ForegroundColor Green
    } catch {
        Write-Host ("  {0,-20} 失败: {1}" -f $tag, $_.Exception.Message) -ForegroundColor Red
    }
}
foreach ($m in $map) { Test-Model $m.Tag }

Write-Host "===== 4. 当前显存占用 =====" -ForegroundColor Cyan
& nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
Write-Host "`n部署完成。日常调用请使用 virtu-opt-* 系列 tag。" -ForegroundColor Cyan
