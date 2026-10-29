"""Explicit schema/index/seed setup; run once before enabling SKIP_DB_INIT.

This preserves the existing initialization behavior. It is not a replacement
for Alembic migrations when changing existing columns or constraints.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import init_db, seed_default_data


def main():
    init_db()
    seed_default_data()
    print("Database initialization completed.")


if __name__ == "__main__":
    main()
