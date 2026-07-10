#!/usr/bin/env bash
# Reaper — one-time server setup for the frontend. Installs Node 20 via nvm
# (the server's apt-installed Node 18.19.1 is below Next.js 16's >=20.9.0
# minimum), pulls main, and builds the frontend. Run on the server itself
# (not via a wrapping ssh command — avoids quoting headaches).
#
# Usage: bash deploy/setup_frontend.sh
#
# After this succeeds, run deploy/install_frontend_service.sh to install
# and start the systemd service.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# deploy/.env is gitignored — drop a REAPER_API_URL=http://<your-server>:5001
# line in there once so you don't have to pass it on every run.
if [ -f "$REPO_DIR/deploy/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$REPO_DIR/deploy/.env"
    set +a
fi

if [ -z "${REAPER_API_URL:-}" ]; then
    echo "!! REAPER_API_URL is not set."
    echo "!! This gets baked into the frontend build as NEXT_PUBLIC_API_URL, so it"
    echo "!! must be the address browsers on your network will use to reach the"
    echo "!! backend (e.g. its Tailscale IP or LAN IP), not localhost."
    echo "!! Either export it, or put it in deploy/.env (gitignored):"
    echo "!!   echo 'REAPER_API_URL=http://100.x.x.x:5001' > deploy/.env"
    exit 1
fi
API_URL="$REAPER_API_URL"

echo "== Killing stale next-server process, if any =="
pkill -f 'next-server' || true

echo "== Installing nvm (per-user, no sudo, isolates our Node version) =="
if [ ! -d "$HOME/.nvm" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
fi
export NVM_DIR="$HOME/.nvm"
# shellcheck source=/dev/null
source "$NVM_DIR/nvm.sh"

# Pinned to an exact patch (not just "20") so re-running this script later
# can't silently pick up a different Node build than the one this was tested
# against. Bump deliberately if you need a newer patch.
NODE_VERSION="20.20.2"

echo "== Installing Node $NODE_VERSION (Next.js 16 requires >=20.9.0) =="
nvm install "$NODE_VERSION"
nvm use "$NODE_VERSION"
nvm alias default "$NODE_VERSION"
node -v
npm -v

echo "== Checking for uncommitted changes before touching git state =="
cd "$REPO_DIR"
if [ -n "$(git status --porcelain)" ]; then
    echo "!! Uncommitted changes found in $REPO_DIR — not touching git state."
    echo "!! Review/stash/commit manually, then re-run this script."
    git status --short
    exit 1
fi

echo "== Pulling latest main =="
git fetch origin
git checkout main
git pull origin main

echo "== Writing frontend/.env.production (NEXT_PUBLIC_API_URL is inlined at BUILD time) =="
cat > frontend/.env.production <<ENVEOF
NEXT_PUBLIC_API_URL=${API_URL}
ENVEOF

echo "== Installing deps + building =="
cd frontend
npm ci
npm run build

echo "== Done. Node/npm resolved to: =="
which node
which npm
