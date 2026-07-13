# Image for both `app` and `worker` — same code, same deps.
# docker-compose overrides the command (uvicorn for app, python -m worker.main for worker).
FROM python:3.11-slim

# Run as a non-root user (created up front so later COPYs can be owned by it).
RUN useradd --create-home appuser
WORKDIR /app

# --- Dependencies layer (cached on requirements.txt alone) -------------------
# requirements.txt is the pinned lock generated from pyproject.toml, so builds
# are reproducible and editing app code does NOT re-download dependencies.
# (No gcc needed — asyncpg / pydantic-core / uvloop all ship cp311 linux wheels.)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- Source layer (rebuilds only when code changes) --------------------------
# PYTHONPATH makes `app` and `worker` importable without installing our package.
COPY app ./app
COPY worker ./worker
COPY migrations ./migrations
ENV PYTHONPATH=/app

USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
