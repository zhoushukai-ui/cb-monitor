#!/usr/bin/env python3
"""Initialize the database — create all tables."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from database import init_db


async def main():
    print("Creating database tables…")
    await init_db()
    print("Done! Tables created.")


if __name__ == "__main__":
    asyncio.run(main())
