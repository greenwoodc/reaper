#!/usr/bin/env bash
# Reaper — install/refresh the reaper-backend systemd service from
# deploy/reaper-backend.service, then start it. Needs sudo — run this
# directly in an interactive terminal so the password prompt works.
#
# Usage: bash deploy/install_backend_service.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Stopping any manually-started backend/app.py (frees port 5001) =="
pkill -f 'backend/app.py' || true
sleep 1

echo "== Installing systemd unit =="
sudo cp "$REPO_DIR/deploy/reaper-backend.service" /etc/systemd/system/reaper-backend.service

echo "== Enabling + starting =="
sudo systemctl daemon-reload
sudo systemctl enable reaper-backend
sudo systemctl restart reaper-backend

sleep 2
echo "== Status =="
sudo systemctl status reaper-backend --no-pager

echo ""
echo "== Recent logs =="
sudo journalctl -u reaper-backend -n 20 --no-pager
