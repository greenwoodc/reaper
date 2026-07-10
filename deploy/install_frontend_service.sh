#!/usr/bin/env bash
# Reaper — install/refresh the reaper-frontend systemd service from
# deploy/reaper-frontend.service, then start it. Needs sudo — run this
# directly in an interactive terminal so the password prompt works (running
# it through a non-interactive `ssh host "sudo ..."` will fail with
# "sudo: a terminal is required").
#
# Usage: bash deploy/install_frontend_service.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Installing systemd unit =="
sudo cp "$REPO_DIR/deploy/reaper-frontend.service" /etc/systemd/system/reaper-frontend.service

echo "== Enabling + starting =="
sudo systemctl daemon-reload
sudo systemctl enable reaper-frontend
sudo systemctl restart reaper-frontend

sleep 2
echo "== Status =="
sudo systemctl status reaper-frontend --no-pager

echo ""
echo "== Recent logs =="
sudo journalctl -u reaper-frontend -n 20 --no-pager
