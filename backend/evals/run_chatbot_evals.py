from __future__ import annotations

import logging
import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "offline-eval-secret-key-that-is-long-enough")
os.environ.setdefault("CORS_ORIGINS", "[]")
logging.basicConfig(level=logging.CRITICAL)

from evals.chatbot_eval import format_report, run_evaluations

logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)


def main() -> int:
    report = run_evaluations()
    print(format_report(report))
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
