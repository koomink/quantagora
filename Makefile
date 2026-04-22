PYTHON ?= python3.11
BACKEND_VENV ?= backend/.venv311

.PHONY: backend-venv backend-dev frontend-dev db-upgrade db-downgrade db-revision backend-check backend-lint frontend-build check

backend-venv:
	$(PYTHON) -m venv $(BACKEND_VENV)
	$(BACKEND_VENV)/bin/pip install -r backend/requirements.txt

backend-dev:
	cd backend && ../$(BACKEND_VENV)/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && npm run dev -- --host 0.0.0.0

db-upgrade:
	cd backend && ../$(BACKEND_VENV)/bin/alembic upgrade head

db-downgrade:
	cd backend && ../$(BACKEND_VENV)/bin/alembic downgrade -1

db-revision:
	cd backend && ../$(BACKEND_VENV)/bin/alembic revision --autogenerate -m "$(m)"

backend-check:
	cd backend && ../$(BACKEND_VENV)/bin/python -m py_compile $$(find app -name '*.py')

backend-lint:
	$(BACKEND_VENV)/bin/ruff check backend/app

frontend-build:
	cd frontend && npm run build

check: backend-lint backend-check frontend-build
