Simplified Deployment (Minimal, No Docker)

This guide sets up the app with a single FastAPI/uvicorn service and Nginx reverse proxy. It assumes Ubuntu/Debian and low traffic.

Domain: replace agenticmojo.sixtyoneeighty.com with your actual hostname (if you intend to use agenticmojoj.sixtyoneeighty.com, update that consistently).

Prerequisites
- DNS: Point an A record for your domain to 149.28.225.47
- SSH access with sudo privileges

Quick Start
1) Copy the repo to the server (recommended path `/opt/agenticmojo`):
   sudo mkdir -p /opt/agenticmojo
   sudo chown $USER:$USER /opt/agenticmojo
   git clone https://your.git.repo/agenticmojo.git /opt/agenticmojo

2) Run the one-shot deploy script:
   cd /opt/agenticmojo/deploy
   chmod +x simple_deploy.sh
   sudo ./simple_deploy.sh agenticmojo.sixtyoneeighty.com

That’s it. Nginx will listen on port 80 and proxy everything to uvicorn on 127.0.0.1:8000. The backend serves the built frontend directly from `frontend/dist`.

What the script does
- Installs minimal deps: nginx, git, curl (adds Node.js 20 if needed to build the frontend)
- Installs uv (fast Python installer/manager) and creates a venv
- Installs Python deps from `pyproject.toml`/`uv.lock`
- Builds the frontend if `frontend/dist` is missing
- Creates a simple systemd unit `agenticmojo.service`
- Creates minimal Nginx vhost that proxies all paths (incl. WebSockets & SSE)

Useful commands
- Check app logs:
  sudo journalctl -u agenticmojo -f
- Restart app:
  sudo systemctl restart agenticmojo
- Check Nginx config and reload:
  sudo nginx -t && sudo systemctl reload nginx

HTTPS (optional, recommended)
1) Install certbot:
   sudo apt-get install -y certbot python3-certbot-nginx
2) Issue a cert:
   sudo certbot --nginx -d agenticmojo.sixtyoneeighty.com
3) Test renewal:
   sudo certbot renew --dry-run

Updating the app
- Pull changes and rebuild frontend (when needed):
  cd /opt/agenticmojo
  git pull
  source .venv/bin/activate && uv sync
  (if frontend changed) cd frontend && npm ci && npm run build
  sudo systemctl restart agenticmojo

