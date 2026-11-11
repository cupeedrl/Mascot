"""Production entrypoint: apply database migrations, then start the API.

Run as ``python -m app.serve``. Hosts such as Render pass their start
command without a shell, so ``alembic upgrade head && uvicorn ...`` cannot be
written there; this module does both steps in one process instead. If a
migration fails the process exits before serving, and the host keeps the
previous version running.
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[1]


def migrate() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")


def main() -> None:
    migrate()
    # Same port as the Dockerfile CMD; MASCOT_PORT lets a host override it.
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("MASCOT_PORT", "8000")))


if __name__ == "__main__":
    main()
