#!/bin/bash

# Agent Mojo Production Deployment Script for Vultr Server
# This script deploys the Agent Mojo application to a Vultr server

set -e  # Exit on any error

# Configuration
APP_NAME="agentmojo"
APP_USER="agentmojo"
APP_DIR="/opt/agentmojo"
DATA_DIR="/var/lib/agentmojo"
LOG_DIR="/var/log/agentmojo"
REPO_URL="https://github.com/your-username/agentmojo.git"  # Update with your repo URL
BRANCH="main"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ✗${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   log_error "This script should not be run as root. Please run as a regular user with sudo privileges."
   exit 1
fi

# Check if sudo is available
if ! command -v sudo &> /dev/null; then
    log_error "sudo is required but not installed. Please install sudo first."
    exit 1
fi

log "Starting Agent Mojo deployment..."

# Step 1: Run environment setup
log "Step 1: Setting up environment..."
if [ -f "./setup_environment.sh" ]; then
    chmod +x ./setup_environment.sh
    sudo ./setup_environment.sh
    log_success "Environment setup completed"
else
    log_error "setup_environment.sh not found. Please ensure it's in the same directory."
    exit 1
fi

# Step 2: Clone or update repository
log "Step 2: Setting up application code..."
if [ -d "$APP_DIR" ]; then
    log "Application directory exists, updating..."
    sudo -u $APP_USER git -C $APP_DIR pull origin $BRANCH
else
    log "Cloning repository..."
    sudo mkdir -p $APP_DIR
    sudo chown $APP_USER:$APP_USER $APP_DIR
    sudo -u $APP_USER git clone -b $BRANCH $REPO_URL $APP_DIR
fi
log_success "Application code ready"

# Step 3: Install Python dependencies
log "Step 3: Installing Python dependencies..."
sudo -u $APP_USER bash -c "cd $APP_DIR && /home/$APP_USER/.local/bin/uv venv .venv"
sudo -u $APP_USER bash -c "cd $APP_DIR && source .venv/bin/activate && /home/$APP_USER/.local/bin/uv sync"
log_success "Python dependencies installed"

# Step 4: Build frontend
log "Step 4: Building frontend..."
sudo -u $APP_USER bash -c "cd $APP_DIR/frontend && npm ci && npm run build"
log_success "Frontend built"

# Step 5: Set up systemd service
log "Step 5: Setting up systemd service..."
if [ -f "./agentmojo.service" ]; then
    sudo cp ./agentmojo.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable agentmojo
    log_success "Systemd service configured"
else
    log_error "agentmojo.service not found. Please ensure it's in the same directory."
    exit 1
fi

# Step 6: Set up nginx
log "Step 6: Setting up nginx..."
if [ -f "./agentmojo.nginx.conf" ]; then
    sudo cp ./agentmojo.nginx.conf /etc/nginx/sites-available/agentmojo
    sudo ln -sf /etc/nginx/sites-available/agentmojo /etc/nginx/sites-enabled/
    
    # Remove default nginx site if it exists
    if [ -f "/etc/nginx/sites-enabled/default" ]; then
        sudo rm /etc/nginx/sites-enabled/default
    fi
    
    # Test nginx configuration
    if sudo nginx -t; then
        log_success "Nginx configuration is valid"
    else
        log_error "Nginx configuration test failed"
        exit 1
    fi
else
    log_error "agentmojo.nginx.conf not found. Please ensure it's in the same directory."
    exit 1
fi

# Step 7: Create configuration file
log "Step 7: Setting up application configuration..."
sudo -u $APP_USER bash -c "cd $APP_DIR && cp trae_config.json.example trae_config.json" || true
log_warning "Please configure trae_config.json with your API keys and settings"

# Step 8: Set proper permissions
log "Step 8: Setting permissions..."
sudo chown -R $APP_USER:$APP_USER $APP_DIR
sudo chown -R $APP_USER:$APP_USER $DATA_DIR
sudo chown -R $APP_USER:$APP_USER $LOG_DIR
log_success "Permissions set"

# Step 9: Start services
log "Step 9: Starting services..."

# Start Agent Mojo service
sudo systemctl start agentmojo
if sudo systemctl is-active --quiet agentmojo; then
    log_success "Agent Mojo service started"
else
    log_error "Failed to start Agent Mojo service"
    sudo systemctl status agentmojo
    exit 1
fi

# Restart nginx
sudo systemctl restart nginx
if sudo systemctl is-active --quiet nginx; then
    log_success "Nginx restarted"
else
    log_error "Failed to restart nginx"
    sudo systemctl status nginx
    exit 1
fi

# Step 10: Verify deployment
log "Step 10: Verifying deployment..."
sleep 5  # Give services time to start

# Check if the application is responding
if curl -f http://localhost/health > /dev/null 2>&1; then
    log_success "Application is responding to health checks"
else
    log_warning "Health check failed, but this might be expected if /health endpoint doesn't exist"
fi

# Get server IP
SERVER_IP=$(curl -s http://ipv4.icanhazip.com || echo "unknown")

log_success "Deployment completed successfully!"
echo ""
echo "=== Deployment Summary ==="
echo "Application URL: http://$SERVER_IP"
echo "Service status: $(sudo systemctl is-active agentmojo)"
echo "Nginx status: $(sudo systemctl is-active nginx)"
echo ""
echo "=== Next Steps ==="
echo "1. Configure your API keys in $APP_DIR/trae_config.json"
echo "2. Restart the service: sudo systemctl restart agentmojo"
echo "3. Check logs: sudo journalctl -u agentmojo -f"
echo "4. Configure your domain name in nginx if needed"
echo "5. Set up SSL certificate for HTTPS (recommended)"
echo ""
echo "=== Useful Commands ==="
echo "View logs: sudo journalctl -u agentmojo -f"
echo "Restart service: sudo systemctl restart agentmojo"
echo "Check status: sudo systemctl status agentmojo"
echo "Update code: cd $APP_DIR && sudo -u $APP_USER git pull && sudo systemctl restart agentmojo"