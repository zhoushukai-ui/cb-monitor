#!/bin/bash
set -e

echo "Initializing database tables..."
cd /app/backend && python -c "
import asyncio
from database import init_db
asyncio.run(init_db())
print('  Tables created OK')
"

echo "Starting uvicorn on 0.0.0.0:${PORT:-8000}..."
cd /app/backend && uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
