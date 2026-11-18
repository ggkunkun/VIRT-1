# PowerShell Script: Start, Status, or Stop Virtu Autonomous Internet Learning Service

param (
    [string]$Action = "status",
    [int]$Interval = 1800
)

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Workspace = (Resolve-Path "$PSScriptRoot\..").Path
$PythonExe = "python"
$ScriptPath = Join-Path $Workspace "scripts\run_autonomous_learning.py"

& $PythonExe $ScriptPath --mode $Action.ToLower() --interval $Interval
