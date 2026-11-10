# WealthPilot AI backend image (deployment only; local development stays native per CLAUDE.md).
# Build context is the REPO ROOT, because the backend resolves models/, config/, training/
# relative to the repository root (agents/nodes.py: REPO_ROOT = parents[3]).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

# libgomp1: OpenMP runtime needed by xgboost / scikit-learn wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (cached layer unless pyproject.toml changes).
COPY backend/pyproject.toml backend/pyproject.toml
RUN mkdir -p backend/wealthpilot \
    && touch backend/wealthpilot/__init__.py \
    && pip install ./backend

# Application code and the repo-root folders it reads at runtime.
COPY backend/ backend/
COPY config/ config/
COPY training/ training/
COPY models/ models/
COPY reports/ reports/
COPY datasets/ datasets/
COPY scripts/fetch_far_trans.py scripts/fetch_far_trans.py
RUN pip install --no-deps -e ./backend \
    && mkdir -p datasets/raw/FAR-Trans

# Never run as root.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Render injects $PORT; default to 8000 for local `docker run`.
# FAR-Trans CSVs are third-party data kept out of git; fetched from FAR_TRANS_URL if absent.
# Migrations run from backend/ because alembic.ini uses a relative script_location.
CMD ["sh", "-c", "python scripts/fetch_far_trans.py && cd backend && alembic upgrade head && cd .. && exec uvicorn wealthpilot.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
