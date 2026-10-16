param(
  [Parameter(Mandatory = $true)][ValidatePattern('^[a-z][a-z0-9-]{4,28}[a-z0-9]$')][string]$ProjectId,
  [Parameter(Mandatory = $true)][ValidatePattern('^[a-z]+-[a-z]+[0-9]$')][string]$Region,
  [Parameter(Mandatory = $true)][ValidatePattern('^.+/.+/.+:.+$')][string]$Image,
  [ValidatePattern('^[a-z]{2}$')][string]$Country = 'in',
  [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$collectorName = 'talentscope-market-collector'
$schedulerName = 'talentscope-market-collector-daily'
$collectorAccount = "talentscope-collector@$ProjectId.iam.gserviceaccount.com"
$schedulerAccount = "talentscope-scheduler-invoker@$ProjectId.iam.gserviceaccount.com"
$jobUri = "https://run.googleapis.com/v2/projects/$ProjectId/locations/$Region/jobs/${collectorName}:run"

$plan = [ordered]@{
  project = $ProjectId
  region = $Region
  cloud_run_job = $collectorName
  image = $Image
  command = 'python -m app.scripts.collect_market_data'
  arguments = @('--country', $Country)
  job_service_account = $collectorAccount
  scheduler_job = $schedulerName
  schedule = '15 3 * * * UTC'
  scheduler_service_account = $schedulerAccount
  scheduler_target = $jobUri
  task_timeout = '900s'
  task_max_retries = 1
  task_count = 1
  task_parallelism = 1
  provider_secrets = @('JSEARCH_API_KEY=jsearch-api-key:latest', 'ADZUNA_APP_ID=adzuna-app-id:latest', 'ADZUNA_APP_KEY=adzuna-app-key:latest', 'GITHUB_TOKEN=github-token:latest')
  plaintext_environment = @("FIREBASE_PROJECT_ID=$ProjectId", "ADZUNA_COUNTRY=$Country", 'GITHUB_TOPIC=python')
}

if (-not $Apply) {
  $plan | ConvertTo-Json -Depth 5
  Write-Host 'Validation only. Add -Apply after provisioning service accounts, IAM, APIs, and Secret Manager values.'
  exit 0
}

$gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
if (-not $gcloud) { throw 'gcloud CLI is unavailable; no cloud resources were changed.' }

& gcloud auth print-access-token --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) { throw 'No active gcloud credentials for the selected project; no cloud resources were changed.' }

& gcloud run jobs deploy $collectorName --project $ProjectId --region $Region --image $Image `
  --service-account $collectorAccount --tasks 1 --parallelism 1 --max-retries 1 --task-timeout 900s `
  --command python --args "-m,app.scripts.collect_market_data,--country,$Country" `
  --set-env-vars "FIREBASE_PROJECT_ID=$ProjectId,ADZUNA_COUNTRY=$Country,GITHUB_TOPIC=python" `
  --set-secrets 'JSEARCH_API_KEY=jsearch-api-key:latest,ADZUNA_APP_ID=adzuna-app-id:latest,ADZUNA_APP_KEY=adzuna-app-key:latest,GITHUB_TOKEN=github-token:latest' `
  --wait
if ($LASTEXITCODE -ne 0) { throw 'Cloud Run Job deployment failed.' }

$existing = & gcloud scheduler jobs describe $schedulerName --project $ProjectId --location $Region --format='value(name)' 2>$null
if ($LASTEXITCODE -eq 0 -and $existing) {
  $verb = 'update'
} else {
  $verb = 'create'
}
& gcloud scheduler jobs $verb http $schedulerName --project $ProjectId --location $Region `
  --schedule '15 3 * * *' --time-zone UTC --uri $jobUri --http-method POST `
  --oauth-service-account-email $schedulerAccount --oauth-token-scope 'https://www.googleapis.com/auth/cloud-platform' `
  --message-body '{}' --attempt-deadline 1200s --max-retry-attempts 2 --max-retry-duration 3600s `
  --min-backoff 60s --max-backoff 600s --max-doublings 3
if ($LASTEXITCODE -ne 0) { throw 'Cloud Scheduler deployment failed. The Cloud Run Job may already exist; inspect it before retrying.' }

Write-Host "Deployed $collectorName and $schedulerName in $ProjectId/$Region. Verify their status and perform an authorized manual execution before enabling normal operations."
