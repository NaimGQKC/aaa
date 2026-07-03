PY := .venv/bin/python
PIP := .venv/bin/pip
PYTHONPATH_ALL := api:packages/schemas:scripts

.PHONY: setup api worker web seed eval test lint docker-up docker-down clean

setup:  ## create venv + install backend deps (local provider, no GPU/API needed)
	python3 -m venv .venv
	$(PIP) install -q -e ./packages/schemas -e "./api[dev]"

setup-full:  ## + optional extras: postgres, s3, mistral, pdf/docx export
	$(PIP) install -q -e "./api[postgres,s3,mistral,reports,dev]"

api:  ## run the FastAPI app (starts in-process worker thread too)
	PYTHONPATH=$(PYTHONPATH_ALL) $(PY) -m uvicorn app.main:app --app-dir api --reload --port 8000

worker:  ## run a standalone queue worker
	PYTHONPATH=$(PYTHONPATH_ALL) $(PY) workers/worker.py

web:  ## run the React dev server
	cd web && npm install && npm run dev

seed:  ## seed the synthetic demo deal end-to-end (offline)
	PYTHONPATH=$(PYTHONPATH_ALL) $(PY) scripts/seed_demo.py

eval:  ## run the gold-set eval harness (CI-gating)
	PYTHONPATH=$(PYTHONPATH_ALL) $(PY) eval/run_eval.py

test:  ## run backend tests
	PYTHONPATH=$(PYTHONPATH_ALL) $(PY) -m pytest api/tests -q

lint:
	.venv/bin/ruff check api packages scripts eval workers

docker-up:
	docker compose -f infra/docker-compose.yml up --build -d

docker-down:
	docker compose -f infra/docker-compose.yml down

clean:
	rm -rf data .venv web/node_modules web/dist eval/results
