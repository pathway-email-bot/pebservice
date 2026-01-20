# setup_gcloud.ps1
# Script to configure gcloud CLI for the PEB Service project

$PROJECT_ID = "pathway-email-bot-6543"
$REGION = "us-central1"

Write-Host "=== PEB Service - gcloud Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check if gcloud is installed
try {
    $version = gcloud --version 2>&1 | Select-Object -First 1
    Write-Host "[OK] gcloud installed: $version" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] gcloud is not installed. Install via: winget install Google.CloudSDK" -ForegroundColor Red
    exit 1
}

# Check current auth status
Write-Host ""
Write-Host "Checking authentication..." -ForegroundColor Yellow
$account = gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>&1

if ([string]::IsNullOrWhiteSpace($account)) {
    Write-Host "[INFO] Not logged in. Starting authentication..." -ForegroundColor Yellow
    gcloud auth login
    $account = gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>&1
}

Write-Host "[OK] Logged in as: $account" -ForegroundColor Green

# Set project
Write-Host ""
Write-Host "Setting default project to: $PROJECT_ID" -ForegroundColor Yellow
gcloud config set project $PROJECT_ID

# Set region
Write-Host "Setting default region to: $REGION" -ForegroundColor Yellow
gcloud config set functions/region $REGION
gcloud config set run/region $REGION

# Verify configuration
Write-Host ""
Write-Host "=== Current Configuration ===" -ForegroundColor Cyan
gcloud config list

# Quick connectivity test
Write-Host ""
Write-Host "=== Verifying Project Access ===" -ForegroundColor Cyan
try {
    $functionStatus = gcloud functions describe process_email --region=$REGION --format="value(state)" 2>&1
    if ($functionStatus -match "ACTIVE") {
        Write-Host "[OK] Cloud Function 'process_email' is ACTIVE" -ForegroundColor Green
    } else {
        Write-Host "[INFO] Cloud Function status: $functionStatus" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[WARN] Could not verify function status (may need deployment)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host "You can now use gcloud commands for the PEB Service project."
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host "  gcloud functions logs read process_email --region=$REGION --limit=20"
Write-Host "  gcloud functions describe process_email --region=$REGION"
Write-Host "  gcloud pubsub topics list"
