# Agent Mojo Deployment Guide

This directory contains deployment helpers. For a minimal, streamlined setup, see `deploy/SIMPLE.md` and use `deploy/simple_deploy.sh`.

The rest of this README documents a more featureful (but heavier) path. If you only need something that works quickly for a handful of users, prefer the simple approach first.

## Files Overview

- `setup_environment.sh` - Sets up the server environment, installs dependencies
- `deploy.sh` - Main deployment script that orchestrates the entire process
- `agentmojo.service` - Systemd service file for process management
- `agentmojo.nginx.conf` - Nginx configuration for reverse proxy and static file serving
- `README.md` - This file

## Prerequisites

- A fresh Ubuntu 20.04+ or Debian 11+ server on Vultr
- Root or sudo access to the server
- Your Agent Mojo code repository accessible via Git

## Quick Deployment

1. **Upload deployment files to your server:**
   ```bash
   scp -r deploy/ user@YOUR_SERVER_IP:~/
   ```

2. **SSH into your server:**
   ```bash
   ssh user@YOUR_SERVER_IP
   ```

3. **Navigate to the deployment directory:**
   ```bash
   cd ~/deploy
   ```

4. **Update the repository URL in deploy.sh:**
   ```bash
   nano deploy.sh
   # Change REPO_URL to your actual repository URL
   ```

5. **Make scripts executable:**
   ```bash
   chmod +x *.sh
   ```

6. **Run the deployment:**
   ```bash
   ./deploy.sh
   ```

## Manual Step-by-Step Deployment

If you prefer to run each step manually:

### 1. Environment Setup
```bash
sudo ./setup_environment.sh
```

### 2. Application Setup
```bash
# Clone your repository
sudo mkdir -p /opt/agentmojo
sudo chown agentmojo:agentmojo /opt/agentmojo
sudo -u agentmojo git clone YOUR_REPO_URL /opt/agentmojo

# Install Python dependencies
sudo -u agentmojo bash -c "cd /opt/agentmojo && uv venv .venv"
sudo -u agentmojo bash -c "cd /opt/agentmojo && source .venv/bin/activate && uv sync"

# Build frontend
sudo -u agentmojo bash -c "cd /opt/agentmojo/frontend && npm ci && npm run build"
```

### 3. Service Configuration
```bash
# Install systemd service
sudo cp agentmojo.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable agentmojo

# Install nginx configuration
sudo cp agentmojo.nginx.conf /etc/nginx/sites-available/agentmojo
sudo ln -s /etc/nginx/sites-available/agentmojo /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
```

### 4. Configuration
```bash
# Copy and configure the application
sudo -u agentmojo cp /opt/agentmojo/trae_config.json.example /opt/agentmojo/trae_config.json
# Edit the configuration file with your API keys
sudo -u agentmojo nano /opt/agentmojo/trae_config.json
```

### 5. Start Services
```bash
sudo systemctl start agentmojo
sudo systemctl restart nginx
```

## Post-Deployment Configuration

### 1. Configure API Keys
Edit `/opt/agentmojo/trae_config.json` with your API keys:
```bash
sudo -u agentmojo nano /opt/agentmojo/trae_config.json
```

### 2. Restart the Service
```bash
sudo systemctl restart agentmojo
```

### 3. Verify Deployment
```bash
# Check service status
sudo systemctl status agentmojo
sudo systemctl status nginx

# Check logs
sudo journalctl -u agentmojo -f

# Test the application
curl http://localhost/health
```

## Firewall Configuration

The deployment script automatically configures UFW firewall. If you need to manually configure it:

```bash
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp  # Optional: direct access to FastAPI
sudo ufw --force enable
```

## SSL/HTTPS Setup (Recommended)

To enable HTTPS with Let's Encrypt:

1. **Install Certbot:**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   ```

2. **Update nginx configuration with your domain:**
   ```bash
   sudo nano /etc/nginx/sites-available/agentmojo
   # Replace 'server_name _;' with 'server_name yourdomain.com;'
   ```

3. **Obtain SSL certificate:**
   ```bash
   sudo certbot --nginx -d yourdomain.com
   ```

4. **Test auto-renewal:**
   ```bash
   sudo certbot renew --dry-run
   ```

## Useful Commands

### Service Management
```bash
# View logs
sudo journalctl -u agentmojo -f

# Restart service
sudo systemctl restart agentmojo

# Check status
sudo systemctl status agentmojo

# Stop service
sudo systemctl stop agentmojo
```

### Application Updates
```bash
# Update code and restart
cd /opt/agentmojo
sudo -u agentmojo git pull
sudo -u agentmojo bash -c "cd frontend && npm run build"
sudo systemctl restart agentmojo
```

### Nginx Management
```bash
# Test configuration
sudo nginx -t

# Reload configuration
sudo systemctl reload nginx

# Restart nginx
sudo systemctl restart nginx
```

## Troubleshooting

### Service Won't Start
1. Check logs: `sudo journalctl -u agentmojo -f`
2. Verify configuration: `sudo -u agentmojo /opt/agentmojo/.venv/bin/python -c "import server.app"`
3. Check permissions: `ls -la /opt/agentmojo`

### Nginx Issues
1. Test configuration: `sudo nginx -t`
2. Check nginx logs: `sudo tail -f /var/log/nginx/error.log`
3. Verify file permissions: `ls -la /opt/agentmojo/frontend/dist`

### Application Not Accessible
1. Check firewall: `sudo ufw status`
2. Verify services are running: `sudo systemctl status agentmojo nginx`
3. Test locally: `curl http://localhost`

### Performance Issues
1. Monitor resources: `htop`
2. Check logs for errors: `sudo journalctl -u agentmojo -f`
3. Consider increasing worker processes in systemd service

## Security Considerations

- The application runs as a non-privileged user (`agentmojo`)
- Systemd service includes security hardening options
- Nginx serves static files directly for better performance
- Firewall is configured to only allow necessary ports
- Consider setting up fail2ban for additional protection
- Regularly update the system: `sudo apt update && sudo apt upgrade`

## Monitoring

Consider setting up monitoring for:
- Service uptime: `systemctl status agentmojo`
- Resource usage: `htop`, `df -h`
- Application logs: `journalctl -u agentmojo`
- Nginx access logs: `/var/log/nginx/access.log`

## Backup

Important directories to backup:
- `/opt/agentmojo/trae_config.json` - Configuration
- `/var/lib/agentmojo/` - Application data
- `/var/log/agentmojo/` - Logs (optional)
