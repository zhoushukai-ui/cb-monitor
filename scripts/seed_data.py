#!/usr/bin/env python3
"""Run data collection once and seed the database.

Usage:
    python scripts/seed_data.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from database import AsyncSessionLocal, init_db
from services.collector import collect_all


async def main():
    print("Initializing database…")
    await init_db()

    print("Starting data collection (this may take 10-30 seconds)…")
    async with AsyncSessionLocal() as session:
        result = await collect_all(session)
        print(f"Collection complete:")
        for source, count in result.items():
            print(f"  {source}: {count} records")

    print("Done! Data seeded.")


if __name__ == "__main__":
    asyncio.run(main())
