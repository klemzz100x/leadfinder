FROM python:3.11-slim

# Node.js 20 LTS pour builder le frontend
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Dépendances Python ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Build frontend ---
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm ci --omit=dev
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# --- Backend ---
COPY backend/ ./backend/
COPY .env.example .env.example

# Données persistantes sur /data (Render Disk)
RUN mkdir -p /data
ENV SQLITE_PATH=/data/leadfinder.db

EXPOSE 8000
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
