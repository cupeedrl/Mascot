"""CLI script to promote an existing user account to 'admin' role.

Usage:
  python scripts/set_admin.py <email>
"""

import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.user import User
from app.services.auth import normalize_email


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/set_admin.py <email>")
        sys.exit(1)

    target_email = sys.argv[1].strip()
    normalized = normalize_email(target_email)

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.normalized_email == normalized))
        if user is None:
            print(f"[ERROR] User with email '{target_email}' was not found in the database.")
            sys.exit(1)

        user.role = "admin"
        db.commit()
        print(f"[SUCCESS] User '{user.email}' (ID: {user.id}) role successfully set to 'admin'.")


if __name__ == "__main__":
    main()
