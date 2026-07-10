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
# projects running locally), so allow any localhost/127.0.0.1 port rather than
# hardcoding one — this is a local-only personal tool, not exposed publicly.
FRONTEND_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


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
