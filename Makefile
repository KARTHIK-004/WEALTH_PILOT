.PHONY: install dev-backend dev-frontend migrate test generate-types

install:
	cd backend && python -m venv ../.venv
	../.venv/bin/pip install -e "backend[dev]" || .venv/Scripts/pip install -e "backend[dev]"
	cd frontend && npm install

dev-backend:
	# PYTHONPATH=.. puts the repo root (not just backend/) on sys.path --
	# agents/nodes.py's model-cache loaders import the top-level training/
	# package (e.g. training.behaviour.common.PANEL_FEATURES), which
	# pytest.ini's own `pythonpath = .` already provides for the test
	# suite; api/lifespan.py now eagerly triggers those same loaders at
	# startup (Phase 15), which surfaced this as a real "ModuleNotFoundError:
	# No module named 'training'" when uvicorn was launched exactly as this
	# target previously did, with the repo root missing from sys.path.
	cd backend && PYTHONPATH=.. ../.venv/bin/uvicorn wealthpilot.api.main:app --reload --app-dir . || \
	cd backend && PYTHONPATH=.. ../.venv/Scripts/uvicorn wealthpilot.api.main:app --reload --app-dir .

dev-frontend:
	cd frontend && npm run dev

migrate:
	cd backend && ../.venv/bin/alembic upgrade head || ../.venv/Scripts/alembic upgrade head

test:
	pytest

generate-types:
	cd frontend && npm run generate-types
