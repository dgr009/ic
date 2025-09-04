#!/bin/bash
# setup-mcp-server.sh
# Script to set up MCP server for GCP integration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MCP_PORT=8080
MCP_HOST="0.0.0.0"
MCP_CONFIG_DIR="$HOME/.mcp/gcp"
MCP_LOG_DIR="$HOME/.mcp/logs"
SERVICE_ACCOUNT_PATH=""
PROJECTS=""
REGIONS="us-central1,us-east1"
INSTALL_METHOD="docker"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -p, --port PORT              MCP server port (default: 8080)"
    echo "  -h, --host HOST              MCP server host (default: 0.0.0.0)"
    echo "  -s, --service-account PATH   Path to service account key file"
    echo "  -P, --projects PROJECTS      Comma-separated list of GCP projects"
    echo "  -r, --regions REGIONS        Comma-separated list of GCP regions"
    echo "  -m, --method METHOD          Installation method: docker|pip (default: docker)"
    echo "  -c, --config-dir DIR         Configuration directory (default: ~/.mcp/gcp)"
    echo "  -l, --log-dir DIR            Log directory (default: ~/.mcp/logs)"
    echo "  --help                       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -s /path/to/key.json -P project1,project2"
    echo "  $0 --method pip --port 8081"
    echo "  $0 --service-account ~/gcp-key.json --projects my-project --regions us-central1"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--port)
            MCP_PORT="$2"
            shift 2
            ;;
        -h|--host)
            MCP_HOST="$2"
            shift 2
            ;;
        -s|--service-account)
            SERVICE_ACCOUNT_PATH="$2"
            shift 2
            ;;
        -P|--projects)
            PROJECTS="$2"
            shift 2
            ;;
        -r|--regions)
            REGIONS="$2"
            shift 2
            ;;
        -m|--method)
            INSTALL_METHOD="$2"
            shift 2
            ;;
        -c|--config-dir)
            MCP_CONFIG_DIR="$2"
            shift 2
            ;;
        -l|--log-dir)
            MCP_LOG_DIR="$2"
            shift 2
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

print_header "MCP Server Setup for GCP Integration"
print_status "Installation method: $INSTALL_METHOD"
print_status "Server host: $MCP_HOST"
print_status "Server port: $MCP_PORT"
print_status "Config directory: $MCP_CONFIG_DIR"
print_status "Log directory: $MCP_LOG_DIR"

# Create directories
mkdir -p "$MCP_CONFIG_DIR"
mkdir -p "$MCP_LOG_DIR"

# Validate service account if provided
if [ -n "$SERVICE_ACCOUNT_PATH" ]; then
    if [ -f "$SERVICE_ACCOUNT_PATH" ]; then
        print_status "Service account key: $SERVICE_ACCOUNT_PATH"
        
        # Copy service account to MCP config directory
        cp "$SERVICE_ACCOUNT_PATH" "$MCP_CONFIG_DIR/service-account.json"
        chmod 600 "$MCP_CONFIG_DIR/service-account.json"
        print_status "Service account key copied to MCP config directory"
    else
        print_error "Service account key file not found: $SERVICE_ACCOUNT_PATH"
        exit 1
    fi
else
    print_warning "No service account key provided - will use other auth methods"
fi

# Create MCP server configuration
print_status "Creating MCP server configuration..."

cat > "$MCP_CONFIG_DIR/config.json" << EOF
{
  "server": {
    "host": "$MCP_HOST",
    "port": $MCP_PORT,
    "workers": 4
  },
  "gcp": {
    "auth": {
      "method": "service_account",
      "service_account_path": "$MCP_CONFIG_DIR/service-account.json",
      "scopes": [
        "https://www.googleapis.com/auth/cloud-platform.read-only",
        "https://www.googleapis.com/auth/compute.readonly",
        "https://www.googleapis.com/auth/container.readonly"
      ]
    },
    "projects": {
      "default": "$(echo "$PROJECTS" | cut -d',' -f1)",
      "allowed": [$(echo "$PROJECTS" | sed 's/,/", "/g' | sed 's/^/"/' | sed 's/$/"/')],
      "discovery": true
    },
    "regions": {
      "default": [$(echo "$REGIONS" | sed 's/,/", "/g' | sed 's/^/"/' | sed 's/$/"/')],
      "allowed": ["us-central1", "us-east1", "us-west1", "us-west2", "europe-west1", "europe-west2", "asia-northeast1", "asia-southeast1"]
    },
    "services": {
      "compute": {
        "enabled": true,
        "cache_ttl": 300
      },
      "vpc": {
        "enabled": true,
        "cache_ttl": 600
      },
      "gke": {
        "enabled": true,
        "cache_ttl": 300
      },
      "storage": {
        "enabled": true,
        "cache_ttl": 900
      },
      "sql": {
        "enabled": true,
        "cache_ttl": 600
      },
      "functions": {
        "enabled": true,
        "cache_ttl": 300
      },
      "run": {
        "enabled": true,
        "cache_ttl": 300
      },
      "lb": {
        "enabled": true,
        "cache_ttl": 600
      },
      "firewall": {
        "enabled": true,
        "cache_ttl": 900
      },
      "billing": {
        "enabled": true,
        "cache_ttl": 3600
      }
    },
    "performance": {
      "max_workers": 20,
      "request_timeout": 30,
      "retry_attempts": 3,
      "connection_pool_size": 10
    },
    "logging": {
      "level": "INFO",
      "format": "json",
      "file": "$MCP_LOG_DIR/mcp-server.log"
    }
  }
}
EOF

print_status "MCP server configuration created: $MCP_CONFIG_DIR/config.json"

# Setup based on installation method
case $INSTALL_METHOD in
    docker)
        print_header "Setting up MCP Server with Docker"
        
        # Check if Docker is available
        if ! command -v docker &> /dev/null; then
            print_error "Docker is not installed. Please install Docker first."
            exit 1
        fi
        
        # Create Docker Compose file
        cat > "$MCP_CONFIG_DIR/docker-compose.yml" << EOF
version: '3.8'
services:
  mcp-server:
    image: mcp-server-gcp:latest
    container_name: mcp-gcp-server
    ports:
      - "$MCP_PORT:$MCP_PORT"
    environment:
      - MCP_CONFIG_PATH=/app/config/config.json
      - MCP_LOG_LEVEL=INFO
    volumes:
      - $MCP_CONFIG_DIR:/app/config:ro
      - $MCP_LOG_DIR:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:$MCP_PORT/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - mcp-network

networks:
  mcp-network:
    driver: bridge
EOF
        
        print_status "Docker Compose file created: $MCP_CONFIG_DIR/docker-compose.yml"
        
        # Create Dockerfile if it doesn't exist
        cat > "$MCP_CONFIG_DIR/Dockerfile" << EOF
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 mcp && chown -R mcp:mcp /app
USER mcp

# Expose port
EXPOSE $MCP_PORT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \\
    CMD curl -f http://localhost:$MCP_PORT/health || exit 1

# Start server
CMD ["python", "server.py"]
EOF
        
        # Create requirements.txt
        cat > "$MCP_CONFIG_DIR/requirements.txt" << EOF
fastapi==0.104.1
uvicorn==0.24.0
google-cloud-compute==1.14.1
google-cloud-container==2.34.0
google-cloud-storage==2.10.0
google-cloud-sql==3.4.4
google-cloud-functions==1.13.3
google-cloud-run==0.10.3
google-cloud-billing==1.12.1
google-auth==2.23.4
pydantic==2.5.0
redis==5.0.1
structlog==23.2.0
EOF
        
        print_status "Build and start the MCP server:"
        print_status "  cd $MCP_CONFIG_DIR"
        print_status "  docker-compose up -d --build"
        ;;
        
    pip)
        print_header "Setting up MCP Server with pip"
        
        # Check if Python is available
        if ! command -v python3 &> /dev/null; then
            print_error "Python 3 is not installed. Please install Python 3 first."
            exit 1
        fi
        
        # Create virtual environment
        print_status "Creating virtual environment..."
        python3 -m venv "$MCP_CONFIG_DIR/venv"
        source "$MCP_CONFIG_DIR/venv/bin/activate"
        
        # Install MCP server package
        print_status "Installing MCP server package..."
        pip install --upgrade pip
        pip install mcp-server-gcp
        
        # Create systemd service file (if systemd is available)
        if command -v systemctl &> /dev/null; then
            print_status "Creating systemd service..."
            
            sudo tee /etc/systemd/system/mcp-gcp-server.service > /dev/null << EOF
[Unit]
Description=MCP GCP Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$MCP_CONFIG_DIR
Environment=PATH=$MCP_CONFIG_DIR/venv/bin
ExecStart=$MCP_CONFIG_DIR/venv/bin/mcp-server --config $MCP_CONFIG_DIR/config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
            
            sudo systemctl daemon-reload
            sudo systemctl enable mcp-gcp-server
            
            print_status "Systemd service created and enabled"
            print_status "Start the service with: sudo systemctl start mcp-gcp-server"
        else
            print_status "Systemd not available. Start manually with:"
            print_status "  source $MCP_CONFIG_DIR/venv/bin/activate"
            print_status "  mcp-server --config $MCP_CONFIG_DIR/config.json"
        fi
        ;;
        
    *)
        print_error "Invalid installation method: $INSTALL_METHOD"
        print_error "Valid methods: docker, pip"
        exit 1
        ;;
esac

# Create startup script
print_status "Creating startup script..."

cat > "$MCP_CONFIG_DIR/start-mcp-server.sh" << EOF
#!/bin/bash
# Start MCP GCP Server

set -e

CONFIG_DIR="$MCP_CONFIG_DIR"
LOG_DIR="$MCP_LOG_DIR"
INSTALL_METHOD="$INSTALL_METHOD"

echo "Starting MCP GCP Server..."
echo "Config directory: \$CONFIG_DIR"
echo "Log directory: \$LOG_DIR"
echo "Installation method: \$INSTALL_METHOD"

case \$INSTALL_METHOD in
    docker)
        cd "\$CONFIG_DIR"
        if [ -f "docker-compose.yml" ]; then
            echo "Starting with Docker Compose..."
            docker-compose up -d
            echo "MCP server started. Check status with: docker-compose ps"
            echo "View logs with: docker-compose logs -f"
        else
            echo "Error: docker-compose.yml not found"
            exit 1
        fi
        ;;
    pip)
        if [ -f "\$CONFIG_DIR/venv/bin/activate" ]; then
            echo "Starting with pip installation..."
            source "\$CONFIG_DIR/venv/bin/activate"
            nohup mcp-server --config "\$CONFIG_DIR/config.json" > "\$LOG_DIR/mcp-server.log" 2>&1 &
            echo \$! > "\$CONFIG_DIR/mcp-server.pid"
            echo "MCP server started. PID: \$(cat \$CONFIG_DIR/mcp-server.pid)"
            echo "View logs with: tail -f \$LOG_DIR/mcp-server.log"
        else
            echo "Error: Virtual environment not found"
            exit 1
        fi
        ;;
    *)
        echo "Error: Unknown installation method: \$INSTALL_METHOD"
        exit 1
        ;;
esac

# Wait a moment and test connectivity
sleep 5
if curl -f -s http://localhost:$MCP_PORT/health > /dev/null; then
    echo "✓ MCP server is running and healthy"
    echo "✓ Endpoint: http://localhost:$MCP_PORT"
else
    echo "⚠ MCP server may not be ready yet. Check logs for details."
fi
EOF

chmod +x "$MCP_CONFIG_DIR/start-mcp-server.sh"

# Create stop script
cat > "$MCP_CONFIG_DIR/stop-mcp-server.sh" << EOF
#!/bin/bash
# Stop MCP GCP Server

set -e

CONFIG_DIR="$MCP_CONFIG_DIR"
INSTALL_METHOD="$INSTALL_METHOD"

echo "Stopping MCP GCP Server..."

case \$INSTALL_METHOD in
    docker)
        cd "\$CONFIG_DIR"
        if [ -f "docker-compose.yml" ]; then
            docker-compose down
            echo "MCP server stopped"
        else
            echo "Error: docker-compose.yml not found"
            exit 1
        fi
        ;;
    pip)
        if [ -f "\$CONFIG_DIR/mcp-server.pid" ]; then
            PID=\$(cat "\$CONFIG_DIR/mcp-server.pid")
            if kill "\$PID" 2>/dev/null; then
                echo "MCP server stopped (PID: \$PID)"
                rm "\$CONFIG_DIR/mcp-server.pid"
            else
                echo "MCP server was not running or already stopped"
            fi
        else
            echo "PID file not found. MCP server may not be running."
        fi
        ;;
    *)
        echo "Error: Unknown installation method: \$INSTALL_METHOD"
        exit 1
        ;;
esac
EOF

chmod +x "$MCP_CONFIG_DIR/stop-mcp-server.sh"

# Update IC CLI configuration
print_status "Updating IC CLI configuration..."

if [ -f ".env" ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    print_status "Backed up existing .env file"
fi

# Add MCP configuration to .env
{
    echo ""
    echo "# --------- MCP Server Configuration (Generated by setup-mcp-server.sh) ------------"
    echo "MCP_GCP_ENABLED=true"
    echo "MCP_GCP_ENDPOINT=http://localhost:$MCP_PORT/gcp"
    echo "MCP_GCP_AUTH_METHOD=service_account"
    echo "MCP_GCP_TIMEOUT=30"
    echo "MCP_GCP_RETRY_ATTEMPTS=3"
    echo "MCP_GCP_CONNECTION_POOL_SIZE=10"
    echo "MCP_GCP_FALLBACK_ENABLED=true"
    echo "MCP_GCP_FALLBACK_TIMEOUT=10"
    echo "GCP_PREFER_MCP=true"
    if [ -n "$PROJECTS" ]; then
        echo "GCP_PROJECTS=$PROJECTS"
        echo "GCP_DEFAULT_PROJECT=$(echo "$PROJECTS" | cut -d',' -f1)"
    fi
    echo "GCP_REGIONS=$REGIONS"
} >> .env

print_header "Setup Complete"
print_status "MCP server setup completed successfully!"
print_status ""
print_status "Configuration files:"
print_status "  Config: $MCP_CONFIG_DIR/config.json"
print_status "  Start script: $MCP_CONFIG_DIR/start-mcp-server.sh"
print_status "  Stop script: $MCP_CONFIG_DIR/stop-mcp-server.sh"
print_status ""
print_status "Next steps:"
print_status "1. Start the MCP server:"
print_status "   $MCP_CONFIG_DIR/start-mcp-server.sh"
print_status ""
print_status "2. Test the server:"
print_status "   curl http://localhost:$MCP_PORT/health"
print_status ""
print_status "3. Test IC CLI integration:"
print_status "   ic gcp compute info"
print_status ""
print_status "4. Stop the server when needed:"
print_status "   $MCP_CONFIG_DIR/stop-mcp-server.sh"
print_status ""
print_status "For troubleshooting, check logs in: $MCP_LOG_DIR"