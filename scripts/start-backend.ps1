$ErrorActionPreference = "Stop"
$backendDir = "D:\project\New folder\New folder\S7_PROJECT_SKILL_1-main\S7_PROJECT_SKILL_1-main\backend"
$envFile = Join-Path $backendDir ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $name = $parts[0].Trim()
            $val = $parts[1].Trim()
            [Environment]::SetEnvironmentVariable($name, $val, "Process")
        }
    }
}

# Check if local Firebase emulator is actively running on port 8080
$emulatorListening = $false
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $iar = $tcp.BeginConnect("127.0.0.1", 8080, $null, $null)
    if ($iar.AsyncWaitHandle.WaitOne(200, $false)) {
        $tcp.EndConnect($iar)
        $emulatorListening = $true
    }
    $tcp.Close()
} catch {}

if ($emulatorListening) {
    $env:ENVIRONMENT = "local-test"
    $env:TALENTSCOPE_FIREBASE_MODE = "emulator"
    $env:TALENTSCOPE_OFFLINE_TEST_MODE = "0"
    $env:FIREBASE_PROJECT_ID = "demo-talentscope-local"
    $env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8080"
    $env:FIREBASE_AUTH_EMULATOR_HOST = "127.0.0.1:9099"
}

$env:PYTHONDONTWRITEBYTECODE = "1"
$pythonExe = "D:\project\New folder\New folder\S7_PROJECT_SKILL_1-main\.venv\Scripts\python.exe"

Set-Location $backendDir
& $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
