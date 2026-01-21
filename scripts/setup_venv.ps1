# setup_venv.ps1
# Creates a Python 3.11 virtual environment matching the Cloud Functions runtime

$PYTHON_VERSION = "3.11"
$VENV_PATH = ".venv"

Write-Host "=== PEB Service - Virtual Environment Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check if Python 3.11 is available
try {
    $pyVersion = py -$PYTHON_VERSION --version 2>&1
    Write-Host "[OK] Found: $pyVersion" -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] Python $PYTHON_VERSION not found. Install it from python.org" -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "Creating virtual environment at $VENV_PATH..." -ForegroundColor Yellow

if (Test-Path $VENV_PATH) {
    Write-Host "[INFO] Removing existing venv..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $VENV_PATH
}

py -$PYTHON_VERSION -m venv $VENV_PATH

if (-not (Test-Path "$VENV_PATH\Scripts\Activate.ps1")) {
    Write-Host "[ERROR] Failed to create virtual environment" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Virtual environment created" -ForegroundColor Green

# Activate and install dependencies
Write-Host ""
Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Yellow

& "$VENV_PATH\Scripts\python.exe" -m pip install --upgrade pip --quiet
& "$VENV_PATH\Scripts\pip.exe" install -r requirements.txt --quiet
& "$VENV_PATH\Scripts\pip.exe" install pytest --quiet

Write-Host "[OK] Dependencies installed" -ForegroundColor Green

# Verify installation
Write-Host ""
Write-Host "=== Installed Packages ===" -ForegroundColor Cyan
& "$VENV_PATH\Scripts\pip.exe" list

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "To activate the environment, run:" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "To run tests:" -ForegroundColor Yellow
Write-Host "  python -m pytest tests/ -v"
