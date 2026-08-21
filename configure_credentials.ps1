# Load Visual Basic assembly to show GUI input dialogs
Add-Type -AssemblyName Microsoft.VisualBasic

$title = "AWS Credentials Configuration"

# Prompt for Access Key ID
$key = [Microsoft.VisualBasic.Interaction]::InputBox("Please enter your AWS Access Key ID:", $title, "")
if ([string]::IsNullOrEmpty($key)) {
    Write-Host "Configuration cancelled: Access Key ID cannot be empty." -ForegroundColor Red
    exit 1
}

# Prompt for Secret Access Key
$secret = [Microsoft.VisualBasic.Interaction]::InputBox("Please enter your AWS Secret Access Key:", $title, "")
if ([string]::IsNullOrEmpty($secret)) {
    Write-Host "Configuration cancelled: Secret Access Key cannot be empty." -ForegroundColor Red
    exit 1
}

# Prompt for Region
$region = [Microsoft.VisualBasic.Interaction]::InputBox("Please enter your preferred AWS Region:", $title, "us-east-1")
if ([string]::IsNullOrEmpty($region)) {
    $region = "us-east-1"
}

# Format the .env content
$envContent = @"
# AWS Credentials
AWS_ACCESS_KEY_ID=$key
AWS_SECRET_ACCESS_KEY=$secret
AWS_DEFAULT_REGION=$region
"@

# Save to .env file in the current directory
$envContent | Out-File -FilePath ".env" -Encoding utf8
Write-Host "Successfully configured AWS credentials in .env file!" -ForegroundColor Green
