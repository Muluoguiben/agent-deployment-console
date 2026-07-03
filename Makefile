.PHONY: dev-agent dev-console test lint build docker-build

dev-agent:
	cd apps/agent && .venv/bin/uvicorn agent_service.main:app --reload --port 8080

dev-console:
	cd apps/console && npm run dev

test:
	cd apps/agent && .venv/bin/pytest

lint:
	cd apps/agent && .venv/bin/ruff check .
	cd apps/console && npx tsc --noEmit

build:
	cd apps/console && npm run build

docker-build:
	docker build -t agent-deployment-console .
