$ErrorActionPreference = "Stop"

# Generates a random suffix for the project ID to ensure uniqueness
$RANDOM_SUFFIX = Get-Random -Minimum 1000 -Maximum 9999
$PROJECT_ID = "pathway-email-bot-$RANDOM_SUFFIX"
$REGION = "us-central1"
$TOPIC_NAME = "email-notifications"
$SERVICE_ACCOUNT_NAME = "peb-service-account"
$BILLING_ACCOUNT_ID = "" # We will try to fetch this

Write-Host "Create PEB Service Infrastructure"
Write-Host "======================="
Write-Host "Target Project ID: $PROJECT_ID"
Write-Host ""

# 1. Create Project
Write-Host "1. Creating Google Cloud Project..."
try {
    gcloud projects create $PROJECT_ID --name="Pathway Email Bot" --quiet
    Write-Host "   Project '$PROJECT_ID' created successfully." -ForegroundColor Green
}
catch {
    Write-Host "   Error creating project. It might already exist or you ran out of project quota." -ForegroundColor Red
    Write-Error $_
}

# 2. Link Billing (Required for Cloud Functions)
Write-Host "2. Checking Billing Accounts..."
$BILLING_ACCOUNTS = gcloud beta billing accounts list --format="value(name, displayName)" --filter="open=true"
if ($BILLING_ACCOUNTS) {
    # Takes the first active billing account
    $BILLING_ACCOUNT_ID = ($BILLING_ACCOUNTS -split "`t")[0]
    $BILLING_NAME = ($BILLING_ACCOUNTS -split "`t")[1]
    
    if ($BILLING_ACCOUNT_ID) {
        Write-Host "   Found Billing Account: $BILLING_NAME ($BILLING_ACCOUNT_ID)"
        Write-Host "   Linking billing account..."
        gcloud beta billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT_ID --quiet
        Write-Host "   Billing linked successfully." -ForegroundColor Green
    } else {
         Write-Host "   Could not parse billing account ID. Please link billing manually." -ForegroundColor Yellow
    }
} else {
    Write-Host "   No active billing accounts found! Cloud Functions require a billing account." -ForegroundColor Red
    Write-Host "   Please create a billing account in the Google Cloud Console and link it to '$PROJECT_ID'."
    # We continue, but subsequent steps might fail
}

# 3. Set Current Project
Write-Host "3. Setting current project context..."
gcloud config set project $PROJECT_ID --quiet

# 4. Enable APIs
Write-Host "4. Enabling APIs (Gmail, Cloud Functions, Pub/Sub, Cloud Build, Artifact Registry)..."
# Cloud Functions 2nd gen prefers Cloud Run and Artifact Registry
gcloud services enable gmail.googleapis.com cloudfunctions.googleapis.com pubsub.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com run.googleapis.com logging.googleapis.com --project $PROJECT_ID

# 5. Create Pub/Sub Topic
Write-Host "5. Creating Pub/Sub Topic: $TOPIC_NAME"
gcloud pubsub topics create $TOPIC_NAME --project $PROJECT_ID --quiet
Write-Host "   Topic created." -ForegroundColor Green

# 6. Create Service Account
Write-Host "6. Creating Service Account: $SERVICE_ACCOUNT_NAME"
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME --display-name "PEB Service Account" --project $PROJECT_ID --quiet

# 7. Grant Permissions
Write-Host "7. Setting up IAM permissions..."
# Permissions for GitHub Actions deployment service account
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" --role="roles/cloudfunctions.developer" --quiet
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" --role="roles/run.admin" --quiet
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" --role="roles/logging.logWriter" --quiet
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" --role="roles/pubsub.editor" --quiet
Write-Host "   Granted Cloud Functions and Cloud Run deployment permissions." -ForegroundColor Green

Write-Host ""
Write-Host "Setup Complete!" -ForegroundColor Cyan
Write-Host "Project ID: $PROJECT_ID"
Write-Host "Service Account: $SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"
Write-Host "Topic: projects/$PROJECT_ID/topics/$TOPIC_NAME"
Write-Host ""
Write-Host "Next Steps:"
Write-Host "1. Configure Gmail Push Notifications to publish to the topic above."
Write-Host "2. Deploy the Cloud Function."
