"""Reaper webapp backend — Flask API in front of the core/ pipeline library.

Local/Tailscale-only personal tool, same trust model as the rest of Reaper:
no auth. Run with:

    cd backend && python3 app.py
"""

import os
import sys
from pathlib import Path

from flask import Flask
from flask_cors import CORS

REPO_ROOT = Path(__file__).resolve().parent.parent

# core/ and the phase scripts assume they're run with the repo root as cwd
# (relative paths like "playlists/", "config.yml") — make that true regardless
# of how this process was launched.
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

from backend.routes import api_bp  # noqa: E402  (must follow chdir/sys.path setup)

# Next dev picks the next free port whenever 3000 is taken (common with other
# projects running locally), so allow any port rather than hardcoding one —
# this is a local-only personal tool, not exposed publicly. Beyond
# localhost/127.0.0.1 (running the frontend on your own machine), also allow
# private LAN ranges and Tailscale's CGNAT range (100.64.0.0/10) since the
# frontend now also runs on the homelab server, reached over Tailscale from
# other devices.
FRONTEND_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost|127\.0\.0\.1"
    r"|10(?:\.\d{1,3}){3}"
    r"|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}"
    r"|192\.168(?:\.\d{1,3}){2}"
    r"|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}"
    r")(:\d+)?$"
)


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app, origins=FRONTEND_ORIGIN_REGEX)
    app.register_blueprint(api_bp)
    return app


app = create_app()

if __name__ == "__main__":
    # 0.0.0.0 so this is reachable from other devices (e.g. a frontend running
    # on your Mac, talking to this over Tailscale/LAN) — safe here since this
    # is a no-auth personal tool already scoped to a trusted network.
    #
    # Not port 5000: macOS's AirPlay Receiver (AirTunes) squats on that port on
    # the loopback interface and silently intercepts requests to
    # "localhost:5000" (though not "127.0.0.1:5000", which is what makes this
    # so confusing). Linux hosts don't have this problem, but we keep 5001
    # everywhere for consistency.
    app.run(host="0.0.0.0", port=5001, debug=True, threaded=True, use_reloader=False)
