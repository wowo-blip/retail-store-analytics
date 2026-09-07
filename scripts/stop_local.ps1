$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $projectRoot '.runtime\dashboard.pid'
if (Test-Path -LiteralPath $pidPath) {
    $dashboardPid = [int](Get-Content -LiteralPath $pidPath)
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $dashboardPid" -ErrorAction SilentlyContinue
    $expectedPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if ($proc -and $proc.ExecutablePath -eq $expectedPython -and $proc.CommandLine -match 'streamlit.*8502') {
        Stop-Process -Id $dashboardPid
        Write-Output 'Project dashboard stopped.'
    } elseif ($proc) {
        throw 'PID belongs to another process; no action taken.'
    }
}
& (Join-Path $projectRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'stop_mysql.py')
