#!/bin/bash

# Environment Setup Script for Vultr Server Deployment
# This script installs all necessary dependencies for running Agent Mojo

set -e  # Exit on any error

echo "🚀 Setting up Agent Mojo environment on Vultr server..."

# Update system packages
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install essential system packages
echo "🔧 Installing essential packages..."
sudo apt install -y \
    curl \
    wget \
    git \
    build-essential \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    nginx \
    supervisor

# Install Python 3.12
echo "🐍 Installing Python 3.12..."
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev python3-pip

# Install Node.js and npm
echo "📦 Installing Node.js and npm..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install uv (Python package manager)
echo "⚡ Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Create application user
echo "👤 Creating application user..."
sudo useradd -m -s /bin/bash agentmojo || echo "User agentmojo already exists"

# Create application directories
echo "📁 Creating application directories..."
sudo mkdir -p /opt/agentmojo
sudo mkdir -p /var/log/agentmojo
sudo mkdir -p /var/lib/agentmojo
sudo chown -R agentmojo:agentmojo /opt/agentmojo /var/log/agentmojo /var/lib/agentmojo

# Configure firewall
echo "🔥 Configuring firewall..."
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 8000
sudo ufw --force enable

echo "✅ Environment setup completed!"
echo "📋 Next steps:"
echo "   1. Copy your application code to /opt/agentmojo"
echo "   2. Run the deployment script"
echo "   3. Configure nginx and systemd services"