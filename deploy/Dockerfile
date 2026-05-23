FROM python:3.12-slim

WORKDIR /app

# Install system deps for akshare (pandas/numpy need gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (use --only-binary for speed)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY backend/ ./backend/
COPY scripts/ ./scripts/

ENV PYTHONPATH=/app/backend
ENV PORT=8000
ENV DATABASE_URL=sqlite+aiosqlite:////app/backend/data/cb_monitor.db
ENV DEBUG=false

EXPOSE 8000

# Entrypoint: init DB tables, then start server
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
