#!/usr/bin/env bash
set -euo pipefail

# Minimal one-shot deploy for AgenticMojo
# Usage: sudo ./simple_deploy.sh <domain>

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Please run with sudo (needed to install packages and write systemd/nginx)." >&2
  exit 1
fi

DOMAIN="${1:-agenticmojo.sixtyoneeighty.com}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$REPO_DIR"

OWNER_USER="${SUDO_USER:-$(logname 2>/dev/null || echo root)}"
OWNER_GROUP="$OWNER_USER"

echo "==> Using repo at: $APP_DIR"
echo "==> Service will run as: $OWNER_USER"
echo "==> Domain: $DOMAIN"

echo "==> Installing base packages (nginx, git, curl)..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y nginx git curl

echo "==> Installing uv (Python toolchain manager) if missing..."
if ! sudo -u "$OWNER_USER" bash -lc 'command -v uv >/dev/null 2>&1'; then
  sudo -u "$OWNER_USER" bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi

UV_BIN="$(sudo -u "$OWNER_USER" bash -lc 'command -v uv || echo "$HOME/.local/bin/uv"')"
if [[ ! -x "$UV_BIN" ]]; then
  echo "uv not found after install attempt; aborting." >&2
  exit 1
fi

echo "==> Creating venv and installing Python dependencies with uv..."
sudo -u "$OWNER_USER" bash -lc "cd '$APP_DIR' && '$UV_BIN' venv .venv"
sudo -u "$OWNER_USER" bash -lc "set -e; cd '$APP_DIR' && source .venv/bin/activate && '$UV_BIN' sync"

echo "==> Ensuring frontend build exists..."
if [[ ! -f "$APP_DIR/frontend/dist/index.html" ]]; then
  echo "-- frontend/dist not found; installing Node.js 20 and building..."
  if ! command -v node >/dev/null 2>&1 || [[ -z "$(node -v 2>/dev/null | grep -E 'v(18|19|20|21)')" ]]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
  fi
  sudo -u "$OWNER_USER" bash -lc "cd '$APP_DIR/frontend' && npm ci && npm run build"
else
  echo "-- Reusing existing frontend/dist"
fi

SERVICE_PATH="/etc/systemd/system/agenticmojo.service"
echo "==> Writing systemd unit: $SERVICE_PATH"
cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=AgenticMojo (FastAPI/uvicorn)
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=HOST=127.0.0.1
Environment=PORT=8000
ExecStart=$APP_DIR/.venv/bin/python -m uvicorn server.app:app --host 127.0.0.1 --port 8000 --no-access-log
Restart=always
RestartSec=2
User=$OWNER_USER
Group=$OWNER_GROUP

[Install]
WantedBy=multi-user.target
EOF

echo "==> Enabling and starting service..."
systemctl daemon-reload
systemctl enable --now agenticmojo

NGINX_SITE="/etc/nginx/sites-available/agenticmojo"
echo "==> Writing Nginx site: $NGINX_SITE"
cat > "$NGINX_SITE" <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
EOF

echo "==> Activating Nginx site..."
ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/agenticmojo
rm -f /etc/nginx/sites-enabled/default || true
nginx -t
systemctl reload nginx

echo
echo "Deployment complete. Verify with:"
echo "  systemctl status agenticmojo"
echo "  journalctl -u agenticmojo -f"
echo "Then visit:  http://$DOMAIN/  (or http://$(hostname -I | awk '{print $1}')/)"

