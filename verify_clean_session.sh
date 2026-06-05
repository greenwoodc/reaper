#!/bin/bash
# Verify the Soulseek session is clean before logging in locally
# Run this after downloads complete to confirm no dangling connections

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Checking Soulseek session status..."
echo ""

# Check if container is running
if docker container inspect sldl >/dev/null 2>&1; then
    echo -e "${RED}❌ ERROR: sldl container still running!${NC}"
    echo ""
    echo "Recent logs:"
    docker compose logs --tail 10 sldl 2>/dev/null || true
    echo ""
    echo "This means your Soulseek session is still active."
    echo "If you log in locally NOW, you will trigger a ban!"
    echo ""
    echo "Fix: Wait for download to complete, then run:"
    echo "  docker compose down"
    exit 1
else
    echo -e "${GREEN}✓ Container not running${NC}"
fi

# Check if docker compose is still managing services
RUNNING=$(docker compose ps 2>/dev/null | grep -c "sldl" || true)
if [ "$RUNNING" -gt 0 ]; then
    echo -e "${RED}❌ WARNING: sldl service still managed by docker compose${NC}"
    docker compose down
fi

# Check for any lingering soulseek processes
if pgrep -f "soulseek" >/dev/null 2>&1 || pgrep -f "sldl" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  WARNING: soulseek/sldl process still running${NC}"
    echo "   Killing lingering processes..."
    pkill -f "soulseek" || true
    pkill -f "sldl" || true
    sleep 2
fi

# Verify again
if ! pgrep -f "soulseek" >/dev/null 2>&1 && ! pgrep -f "sldl" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ No soulseek processes running${NC}"
fi

echo ""
echo -e "${GREEN}✓ Session is clean!${NC}"
echo "✓ Safe to log into Soulseek locally now"
echo ""
