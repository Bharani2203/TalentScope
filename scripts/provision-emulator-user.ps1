$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:9099'
$projectId = 'demo-talentscope-local'
$email = 'browser-test@example.test'
$readiness = "$base/emulator/v1/projects/$projectId/config"

try {
  $null = Invoke-RestMethod -Method Get -Uri $readiness -TimeoutSec 2
}
catch {
  throw 'Auth Emulator is unavailable; no user was created.'
}

$securePassword = Read-Host 'Enter a new synthetic emulator-only password' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
  $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
  $body = @{ email = $email; password = $password; returnSecureToken = $true } | ConvertTo-Json -Compress
  $null = Invoke-RestMethod -Method Post -Uri "$base/identitytoolkit.googleapis.com/v1/accounts:signUp?key=local-emulator-only" -ContentType 'application/json' -Body $body -TimeoutSec 5
  Write-Output "Synthetic Auth Emulator user created: $email (password and token were not displayed)."
}
catch {
  throw 'Synthetic Auth Emulator user provisioning failed; response details were suppressed.'
}
finally {
  if ($passwordPointer -ne [IntPtr]::Zero) {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
  }
  $password = $null
  $body = $null
  $securePassword.Dispose()
}
