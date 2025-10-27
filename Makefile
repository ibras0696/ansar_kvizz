.PHONY: up down logs run db-init lint fmt

up:
	docker compose up -d --build && docker compose logs -f bot

down:
	docker compose down

logs:
	docker compose logs -f bot

run:
	poetry run quizbot

db-init:
	poetry run python -c "from quizbot.db import init_db; import asyncio; asyncio.run(init_db())"

lint:
	poetry run ruff check .
	poetry run mypy .

fmt:
	poetry run ruff check --select I --fix .
	poetry run ruff format .

clean: ## Очистить кэши, coverage и сборочные артефакты
	echo "🧺 Cleaning caches..."
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov build dist *.egg-info
