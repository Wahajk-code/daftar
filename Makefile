# Shortcuts for the commands in the README. Everything runs through Docker Compose.
.PHONY: up down test seed openapi

up:
	docker compose up -d --build

down:
	docker compose down

# The whole backend gate: ruff, format, mypy, then the full suite against Postgres.
test:
	docker compose --profile test run --rm backend-test

# Demonstration data (needs the migrations applied). Safe to run twice; refuses in production.
seed:
	docker compose exec backend python -m app.seed

# Rewrite backend/openapi.json and docs/api.md from the running code.
openapi:
	docker compose --profile test run --rm backend-test python -m app.openapi_export openapi > backend/openapi.json
	docker compose --profile test run --rm backend-test python -m app.openapi_export api-list > docs/api.md
