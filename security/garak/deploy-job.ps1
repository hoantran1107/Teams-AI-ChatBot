# PowerShell deployment script for Cloud Run Job
param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-central1",
    
    [Parameter(Mandatory=$false)]
    [string]$ImageTag = "latest",
    
    [Parameter(Mandatory=$false)]
    [string]$JobName = "garak-security-scan"
)

Write-Host "=== Deploying Garak Security Scanner to Cloud Run Job ===" -ForegroundColor Green

# Set project
Write-Host "Setting project to $ProjectId..." -ForegroundColor Yellow
gcloud config set project $ProjectId

# Build and push Docker image
$ImageUri = "gcr.io/$ProjectId/garak-scanner:$ImageTag"
Write-Host "Building and pushing Docker image: $ImageUri..." -ForegroundColor Yellow

docker build -t $ImageUri .
docker push $ImageUri

# Update the job configuration with correct project ID
Write-Host "Updating job configuration..." -ForegroundColor Yellow
$JobConfig = Get-Content "cloudrun-job.yaml" -Raw
$JobConfig = $JobConfig -replace "PROJECT_ID", $ProjectId
$JobConfig = $JobConfig -replace "gcr.io/PROJECT_ID/garak-scanner:latest", $ImageUri
$JobConfig | Set-Content "cloudrun-job-deploy.yaml"

# Deploy the job
Write-Host "Deploying Cloud Run Job: $JobName..." -ForegroundColor Yellow
gcloud run jobs replace cloudrun-job-deploy.yaml --region=$Region

Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "To execute the job with default settings:" -ForegroundColor Cyan
Write-Host "gcloud run jobs execute $JobName --region=$Region" -ForegroundColor White
Write-Host ""
Write-Host "To execute with custom parameters:" -ForegroundColor Cyan
Write-Host "gcloud run jobs execute $JobName --region=$Region --args='--probes,dan,xss --verbose'" -ForegroundColor White
Write-Host ""
Write-Host "To execute with different config:" -ForegroundColor Cyan
Write-Host "gcloud run jobs execute $JobName --region=$Region --args='--config,custom_config.yaml --probes,lmrc'" -ForegroundColor White

# Clean up temporary file
Remove-Item "cloudrun-job-deploy.yaml" -ErrorAction SilentlyContinue
