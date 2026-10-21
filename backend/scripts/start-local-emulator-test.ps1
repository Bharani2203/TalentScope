param(
  [ValidateSet('127.0.0.1')][string]$BindHost = '127.0.0.1',
  [ValidateRange(1024, 65535)][int]$Port = 8010,
  [switch]$HealthCheckOnly
)

$ErrorActionPreference = 'Stop'

function Test-Endpoint([string]$url, [string]$expectedPattern, [int]$timeoutSec = 2) {
  try {
    $resp = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec $timeoutSec -ErrorAction Stop
    $str = if ($resp -is [string]) { $resp } else { $resp | ConvertTo-Json -Compress }
    return ($str -match $expectedPattern)
  } catch {
    return $false
  }
}

# 1. Validate required local tools
$missingTools = @()
if (-not (Get-Command 'firebase' -ErrorAction SilentlyContinue)) { $missingTools += 'firebase CLI (npm install -g firebase-tools)' }
if (-not (Get-Command 'java' -ErrorAction SilentlyContinue)) { $missingTools += 'Java runtime (Eclipse Adoptium/OpenJDK 11+)' }
if (-not (Get-Command 'python' -ErrorAction SilentlyContinue)) { $missingTools += 'Python runtime' }
if ($missingTools.Count -gt 0) {
  throw "Required tool(s) missing: $($missingTools -join ', '). Cannot start isolated emulator test environment."
}

# 2. Check current status of Auth (9099) and Firestore (8080) emulators
$authReady = Test-Endpoint 'http://127.0.0.1:9099/' 'authEmulator|ready'
$firestoreReady = Test-Endpoint 'http://127.0.0.1:8080/' 'Ok'

if ($HealthCheckOnly) {
  $backendReady = Test-Endpoint "http://${BindHost}:${Port}/api/v1/health" 'ok'
  Write-Output "Health Summary:"
  Write-Output "  Firebase Auth Emulator (127.0.0.1:9099): $(if ($authReady) { 'HEALTHY' } else { 'DOWN' })"
  Write-Output "  Firestore Emulator (127.0.0.1:8080):     $(if ($firestoreReady) { 'HEALTHY' } else { 'DOWN' })"
  Write-Output "  Backend API (http://${BindHost}:${Port}):  $(if ($backendReady) { 'HEALTHY' } else { 'DOWN' })"
  return
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$spawnedEmulator = $null

if (-not ($authReady -and $firestoreReady)) {
  Write-Output "Starting Firebase Auth (9099) and Firestore (8080) emulators for demo-talentscope-local..."
  $spawnedEmulator = Start-Process firebase -ArgumentList "emulators:start","--only","auth,firestore","--project","demo-talentscope-local" -WorkingDirectory $repoRoot -PassThru
  $timeout = 30
  $elapsed = 0
  while ($elapsed -lt $timeout) {
    if (-not $authReady) { $authReady = Test-Endpoint 'http://127.0.0.1:9099/' 'authEmulator|ready' }
    if (-not $firestoreReady) { $firestoreReady = Test-Endpoint 'http://127.0.0.1:8080/' 'Ok' }
    if ($authReady -and $firestoreReady) { break }
    Start-Sleep -Seconds 1
    $elapsed += 1
  }
  if (-not ($authReady -and $firestoreReady)) {
    if ($spawnedEmulator -and -not $spawnedEmulator.HasExited) {
      Stop-Process -Id $spawnedEmulator.Id -Force -ErrorAction SilentlyContinue
    }
    throw "Firebase emulators failed to become ready within $timeout seconds (Auth: $authReady, Firestore: $firestoreReady)."
  }
  Write-Output "Firebase emulators ready on 127.0.0.1:9099 (Auth) and 127.0.0.1:8080 (Firestore)."
} else {
  Write-Output "Firebase emulators already running and verified healthy on 127.0.0.1:9099 and 127.0.0.1:8080."
}

# 3. Check if backend port is already active and healthy
$backendHealthy = Test-Endpoint "http://${BindHost}:${Port}/api/v1/health" 'ok'
if ($backendHealthy) {
  Write-Output "Backend is already running and healthy on http://${BindHost}:${Port}."
  return
}

# Ensure port is bindable
$probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse($BindHost), $Port)
try {
  $probe.Start()
}
catch {
  throw "Local-test backend port $Port is unavailable on $BindHost and is not responding to /api/v1/health."
}
finally {
  $probe.Stop()
}

$names = @(
  'TALENTSCOPE_FIREBASE_MODE', 'TALENTSCOPE_OFFLINE_TEST_MODE',
  'ENVIRONMENT', 'FIREBASE_PROJECT_ID', 'FIRESTORE_EMULATOR_HOST',
  'FIREBASE_AUTH_EMULATOR_HOST', 'GEMINI_API_KEY', 'JSEARCH_API_KEY',
  'ADZUNA_APP_ID', 'ADZUNA_APP_KEY', 'GITHUB_TOKEN', 'GOOGLE_APPLICATION_CREDENTIALS',
  'MARKET_COLLECTION_ENABLED_PROVIDERS', 'MARKET_SCHEDULER_ENABLED',
  'CORS_ALLOWED_ORIGINS', 'SKILL_INTELLIGENCE_READ_BACKEND'
)
$prior = @{}
foreach ($name in $names) {
  $prior[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

try {
  $env:TALENTSCOPE_FIREBASE_MODE = 'emulator'
  $env:TALENTSCOPE_OFFLINE_TEST_MODE = '1'
  $env:ENVIRONMENT = 'local-test'
  $env:FIREBASE_PROJECT_ID = 'demo-talentscope-local'
  $env:FIRESTORE_EMULATOR_HOST = '127.0.0.1:8080'
  $env:FIREBASE_AUTH_EMULATOR_HOST = '127.0.0.1:9099'
  $env:GOOGLE_APPLICATION_CREDENTIALS = ''
  $env:GEMINI_API_KEY = ''
  $env:JSEARCH_API_KEY = ''
  $env:ADZUNA_APP_ID = ''
  $env:ADZUNA_APP_KEY = ''
  $env:GITHUB_TOKEN = ''
  $env:MARKET_COLLECTION_ENABLED_PROVIDERS = '[]'
  $env:MARKET_SCHEDULER_ENABLED = 'false'
  $env:CORS_ALLOWED_ORIGINS = '["http://localhost:3000","http://127.0.0.1:3000"]'
  $env:SKILL_INTELLIGENCE_READ_BACKEND = 'firestore'
  Write-Output "Starting local-only backend on ${BindHost}:$Port with demo project and Auth/Firestore emulators; Gemini and provider collection are disabled."
  Push-Location (Join-Path $PSScriptRoot '..')
  try {
    python -c "from app.core.config import get_settings; s=get_settings(); assert s.environment == 'local-test'; assert s.firebase_project_id == 'demo-talentscope-local'; assert s.skill_intelligence_read_backend == 'firestore'; assert s.market_collection_enabled_providers == []; assert not s.market_scheduler_enabled; assert not s.google_application_credentials; assert not (s.gemini_api_key and s.gemini_api_key.get_secret_value().strip()); assert not (s.jsearch_api_key or '').strip(); assert not (s.adzuna_app_id or '').strip(); assert not (s.adzuna_app_key or '').strip(); assert not (s.github_token or '').strip(); print('Local backend config verified: demo project, emulator backend, no service account, Gemini or provider credentials.')"
    if ($LASTEXITCODE -ne 0) {
      throw 'Local backend configuration validation failed.'
    }
    python -m uvicorn app.main:app --host $BindHost --port $Port
  }
  finally {
    Pop-Location
  }
}
finally {
  foreach ($name in $names) {
    [Environment]::SetEnvironmentVariable($name, $prior[$name], 'Process')
  }
  if ($spawnedEmulator -and -not $spawnedEmulator.HasExited) {
    Write-Output "Stopping Firebase emulators ($($spawnedEmulator.Id))..."
    Stop-Process -Id $spawnedEmulator.Id -Force -ErrorAction SilentlyContinue
  }
}
