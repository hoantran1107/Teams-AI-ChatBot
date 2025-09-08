# Garak Security Scanner - Cloud Run Deployment

This folder contains the containerized deployment of the [garak](https://github.com/leondz/garak) LLM security testing framework, optimized for Google Cloud Run Jobs.

## Overview

Garak is a comprehensive LLM vulnerability scanner that tests language models against various security probes. This deployment provides a flexible, scalable way to run security scans in the cloud with configurable parameters and automated reporting.

## Features

- **Flexible Configuration**: Environment variables for common parameters with command-line override support
- **Progress Monitoring**: Optional Pub/Sub integration for real-time scan progress updates
- **Automated Reporting**: Cloud Storage integration for automatic report uploads
- **Robust Error Handling**: Comprehensive logging and failure detection
- **Scalable Execution**: Cloud Run Jobs for cost-effective, on-demand scanning

## Quick Start

### Prerequisites

- Google Cloud Project with Cloud Run API enabled
- Docker installed locally
- `gcloud` CLI configured and authenticated

### 1. Deploy the Scanner

From the `security/garak/` directory:

```powershell
# Deploy with default settings
.\deploy-job.ps1 -ProjectId "your-project-id"

# Deploy to specific region
.\deploy-job.ps1 -ProjectId "your-project-id" -Region "europe-west1"
```

### 2. Execute Security Scans

#### Default Scan (using environment variables)
```bash
# Runs with: --model_type rest --model_name RestGenerator --config ifd_bot_config.yaml --probes lmrc
gcloud run jobs execute garak-security-scan --region=us-central1
```

#### Custom Probe Sets
```bash
# Test with different security probes
gcloud run jobs execute garak-security-scan --region=us-central1 \
  --args="--probes,dan,xss,injection"

# Run comprehensive security scan
gcloud run jobs execute garak-security-scan --region=us-central1 \
  --args="--probes,all --verbose"
```

#### Custom Configuration Files
```bash
# Use different configuration file
gcloud run jobs execute garak-security-scan --region=us-central1 \
  --args="--config,production_config.yaml --probes,lmrc"

# Override model settings for OpenAI
gcloud run jobs execute garak-security-scan --region=us-central1 \
  --args="--model_type,openai --model_name,gpt-4 --config,openai_config.yaml"
```

#### Azure OpenAI Integration
```bash
# Test against Azure OpenAI endpoint
gcloud run jobs execute garak-security-scan --region=us-central1 \
  --set-env-vars="AZURE_API_KEY=your-api-key,AZURE_ENDPOINT=https://your-endpoint.openai.azure.com/,AZURE_MODEL_NAME=gpt-4o" \
  --args="--model_type,azure --model_name,your-deployment-name --probes,lmrc"

# For repeated Azure OpenAI testing, update cloudrun-job.yaml with Azure env vars
# Then run with just the model override:
gcloud run jobs execute garak-security-scan --region=us-central1 \
  --args="--model_type,azure --model_name,your-deployment-name --probes,dan"
```

#### Advanced Usage
```bash
# Custom report settings
gcloud run jobs execute garak-security-scan --region=us-central1 \
  --args="--probes,lmrc --report_prefix,my-scan --generations,5"

# Verbose debugging
gcloud run jobs execute garak-security-scan --region=us-central1 \
  --args="--probes,dan --verbose --debug"
```

## Configuration

### Environment Variables

The following environment variables can be set in `cloudrun-job.yaml` to change default behavior:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_TYPE` | `rest` | Type of model interface to use |
| `MODEL_NAME` | `RestGenerator` | Specific model generator name |
| `CONFIG_FILE` | `ifd_bot_config.yaml` | Path to garak configuration file |
| `PROBES` | `lmrc` | Default probe set to run |
| `REPORT_PREFIX` | `chatbot-security` | Prefix for generated reports |
| `VERBOSE_LEVEL` | `-vv` | Verbosity level for logging |
| `REPORTS_BUCKET` | _(optional)_ | Cloud Storage bucket for automatic report uploads |
| `PUBSUB_TOPIC` | _(optional)_ | Pub/Sub topic for progress notifications |

#### Azure OpenAI Environment Variables

For Azure OpenAI integration, add these to your `cloudrun-job.yaml`:

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_API_KEY` | Azure OpenAI API key | `your-api-key` |
| `AZURE_ENDPOINT` | Azure OpenAI endpoint URL | `https://your-endpoint.openai.azure.com/` |
| `AZURE_MODEL_NAME` | Azure model name | `gpt-4o` |

### Configuration Files

#### Main Configuration (`ifd_bot_config.yaml`)
Contains the REST API endpoint configuration for your target chatbot:

```yaml
run:
    generations: 1 # Test each prompt once
reporting:
    report_dir: "/app/reports"
    report_prefix: "chatbot-security-test"
plugins:
  generators:
    rest:
      RestGenerator:
        uri: "http://localhost:5000/chat/completions"
        method: "post"
        req_template_json_object:
          messages:
            - role: "user"
              content: "$INPUT"
        response_json: true
        response_json_field: "$.choices[0].message.content"
        headers:
          Content-Type: "application/json"
        request_timeout: 60
```

#### Cloud Run Job Configuration (`cloudrun-job.yaml`)
Defines the Cloud Run Job specification including resource limits, environment variables, and execution parameters.

## Available Security Probes

Garak includes numerous security probes. Common ones include:

- `lmrc` - Language Model Risk Cards
- `dan` - "Do Anything Now" jailbreak attempts
- `xss` - Cross-site scripting injection tests
- `injection` - SQL and command injection tests
- `privacy` - Privacy and data leakage tests
- `toxicity` - Toxic content generation tests
- `all` - Run all available probes (comprehensive but time-consuming)

## CI/CD Integration

This garak deployment is automatically deployed via GitHub Actions when changes are pushed to the `garak` branch. The workflow:

1. Triggers only on changes to `security/garak/**` files
2. Builds and pushes the Docker image
3. Deploys the Cloud Run Job
4. Optionally executes a scan if commit message contains `[run-scan]`

## Monitoring and Reports

### Local Reports
Reports are generated in `/app/reports` within the container and include:
- `.jsonl` files with detailed test results
- `.html` files with formatted reports

### Cloud Storage Integration
To automatically upload reports to Cloud Storage:

1. Create a Cloud Storage bucket
2. Update `cloudrun-job.yaml` to include:
   ```yaml
   - name: REPORTS_BUCKET
     value: "your-reports-bucket-name"
   ```
3. Ensure the Cloud Run service account has Storage Object Creator permissions

### Progress Monitoring
For real-time progress updates via Pub/Sub:

1. Create a Pub/Sub topic
2. Update `cloudrun-job.yaml` to include:
   ```yaml
   - name: PUBSUB_TOPIC
     value: "projects/your-project/topics/garak-progress"
   ```

### Azure OpenAI Configuration Example

To configure the job for Azure OpenAI, update your `cloudrun-job.yaml`:

```yaml
env:
- name: MODEL_TYPE
  value: "azure"
- name: AZURE_API_KEY
  value: "your-azure-api-key"
- name: AZURE_ENDPOINT
  value: "https://your-endpoint.openai.azure.com/"
- name: AZURE_MODEL_NAME
  value: "gpt-4o"
```

Then execute with your deployment name:
```bash
gcloud run jobs execute garak-security-scan --region=us-central1 \
  --args="--model_name,your-deployment-name --probes,lmrc"
```

## Troubleshooting

### Common Issues

1. **Job Timeout**: Increase `timeoutSeconds` in `cloudrun-job.yaml` for comprehensive scans
2. **Memory Limits**: Adjust resource limits if running large probe sets
3. **Network Access**: Ensure your target API is accessible from Cloud Run
4. **Authentication**: Configure service account permissions for Cloud Storage/Pub/Sub

### Viewing Job Logs
```bash
# Get recent job executions
gcloud run jobs executions list --job=garak-security-scan --region=us-central1

# View logs for specific execution
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=garak-security-scan" --limit=100
```

### Testing Locally
```bash
# Build and test locally (from security/garak/ directory)
docker build -t garak-scanner .

# Run with default settings
docker run --rm garak-scanner

# Run with custom parameters
docker run --rm garak-scanner --probes dan --verbose
```

## Security Considerations

- The scanner tests for security vulnerabilities - ensure you have permission to test target systems
- Generated reports may contain sensitive information - secure your Cloud Storage bucket appropriately
- Consider network security when deploying - use private endpoints if testing internal systems
- Review and customize probe selections based on your specific security requirements

## File Structure

```
security/garak/
├── Dockerfile              # Container definition
├── entrypoint.sh           # Enhanced entrypoint script
├── cloudrun-job.yaml       # Cloud Run Job configuration
├── deploy-job.ps1          # PowerShell deployment script
├── pyproject.toml          # Python dependencies
├── uv.lock                 # Locked dependencies
├── ifd_bot_config.yaml     # Garak configuration
├── main.py                 # Application entry point
└── README.md               # This file
```

## License

This deployment configuration is provided as-is. Please refer to the original [garak project](https://github.com/leondz/garak) for licensing information regarding the security scanning framework itself.
