#!/usr/bin/env python3
"""
SelfMirror API server — minimal launcher.
Runs only the /api/mirror/* routes (no OpenBiliClaw dependencies).
"""
import sys
from pathlib import Path

# Add src/ to path so 'import selfmirror' resolves correctly
_src = Path(__file__).parent / "src"
if not any(p.match(str(_src)) for p in map(Path, sys.path)):
    sys.path.insert(0, str(_src))

import uvicorn
from selfmirror.self_mirror.router import router as _self_mirror_router


def create_mirror_app():
    """Minimal FastAPI app with only SelfMirror routes."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="SelfMirror", version="0.1.0")
    app.include_router(_self_mirror_router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:*", "http://localhost:*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SelfMirror API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8400)
    args = parser.parse_args()

    app = create_mirror_app()
    print(f"Starting SelfMirror API on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
