#!/bin/bash

# Enhanced entrypoint script with environment variable support and progress monitoring
set -e

# Default configuration - can be overridden by environment variables
CONFIG_FILE="${CONFIG_FILE:-/app/ifd_bot_config.yaml}"
REPORT_DIR="${REPORT_DIR:-/app/reports}"
MODEL_TYPE="${MODEL_TYPE:-rest}"
MODEL_NAME="${MODEL_NAME:-RestGenerator}"
PROBES="${PROBES:-lmrc}"
REPORT_PREFIX="${REPORT_PREFIX:-chatbot-security}"
VERBOSE_LEVEL="${VERBOSE_LEVEL:--vv}"

# Create reports directory
mkdir -p "$REPORT_DIR"

echo "=== Garak Security Scan Configuration ==="
echo "Config File: $CONFIG_FILE"
echo "Model Type: $MODEL_TYPE"
echo "Model Name: $MODEL_NAME" 
echo "Probes: $PROBES"
echo "Report Directory: $REPORT_DIR"
echo "Report Prefix: $REPORT_PREFIX"
echo "Additional Args: $*"
echo "========================================="

# Function to send progress updates via Pub/Sub
send_progress() {
    local message="$1"
    local status="$2"
    
    if [ ! -z "$PUBSUB_TOPIC" ]; then
        gcloud pubsub topics publish "$PUBSUB_TOPIC" --message="{\"status\":\"$status\",\"message\":\"$message\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
    fi
}

# Send start notification
send_progress "Starting garak security scan" "started"

# Run garak with proper error handling
# If no additional arguments provided, use environment variables
if [ $# -eq 0 ]; then
    GARAK_CMD="garak --model_type $MODEL_TYPE --model_name $MODEL_NAME --config $CONFIG_FILE --probes $PROBES $VERBOSE_LEVEL --report_prefix ${REPORT_PREFIX}-$(date +%Y%m%d-%H%M%S)"
else
    # Use provided arguments, but still include config if not specified
    if [[ "$*" != *"--config"* ]]; then
        GARAK_CMD="garak --config $CONFIG_FILE $VERBOSE_LEVEL $*"
    else
        GARAK_CMD="garak $VERBOSE_LEVEL $*"
    fi
fi

echo "Executing: $GARAK_CMD"

if eval "$GARAK_CMD"; then
    send_progress "Garak scan completed successfully" "completed"
    
    # List generated reports
    echo "Generated reports:"
    ls -la "$REPORT_DIR"/*.{jsonl,html} 2>/dev/null || echo "No reports found"
    
    # Upload reports to Cloud Storage if bucket is specified
    if [ ! -z "$REPORTS_BUCKET" ]; then
        gsutil -m cp "$REPORT_DIR"/* "gs://$REPORTS_BUCKET/$(date +%Y%m%d)/"
        send_progress "Reports uploaded to Cloud Storage" "uploaded"
    fi
else
    send_progress "Garak scan failed" "failed"
    exit 1
fi
