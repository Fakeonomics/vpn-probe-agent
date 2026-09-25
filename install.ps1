$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$App = Join-Path $env:LOCALAPPDATA "vpn-probe"
$Bin = Join-Path $env:LOCALAPPDATA "bin"
$Config = Join-Path $App "client.env"
New-Item -ItemType Directory -Force $App, $Bin | Out-Null
Copy-Item (Join-Path $Root "probe_agent.py") $App -Force
Copy-Item (Join-Path $Root "singbox_engine.py") $App -Force

if (-not (Test-Path $Config)) {
    $key = if ($env:PROBE_KEY) { $env:PROBE_KEY } else { "" }
    $bind = if ($env:PROBE_BIND_CODE) { $env:PROBE_BIND_CODE } else { "" }
    @(
        "PROBE_URL=https://fakeonomics.online"
        "PROBE_KEY=$key"
        "PROBE_BIND_CODE=$bind"
        "PROBE_ACCESS_TYPE=home"
    ) | Set-Content -Path $Config -Encoding UTF8
}

$cmd = @"
@echo off
setlocal
if "%1"=="on" powershell -NoProfile -Command "`$p=Start-Process python.exe -ArgumentList '$App\probe_agent.py' -PassThru; Set-Content -Path '$App\probe.pid' -Value `$p.Id"
if "%1"=="off" powershell -NoProfile -Command "`$p=Get-Content '$App\probe.pid' -ErrorAction SilentlyContinue; if (`$p) { Stop-Process -Id `$p -Force -ErrorAction SilentlyContinue; Remove-Item '$App\probe.pid' -Force -ErrorAction SilentlyContinue }"
if "%1"=="status" powershell -NoProfile -Command "`$p=Get-Content '$App\probe.pid' -ErrorAction SilentlyContinue; if (`$p -and (Get-Process -Id `$p -ErrorAction SilentlyContinue)) { 'running' } else { 'stopped' }"
"@
$cmd | Set-Content (Join-Path $Bin "probe.cmd") -Encoding ASCII

$task = "VPN Probe"
$existing = Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
if (-not $existing) {
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Bin\probe.cmd` on"
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Force | Out-Null
}

Write-Host "Installed: $Bin\probe.cmd"
Write-Host "Run: probe.cmd on"
