.PHONY: install run test test-cov migrate migrate-new format lint docker-up docker-down

install:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements-dev.txt

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -v

test-cov:
	pytest --cov=app --cov-report=term-missing --cov-report=html

migrate:
	alembic upgrade head

migrate-new:
	alembic revision --autogenerate -m "$(msg)"

format:
	ruff format app tests

lint:
	ruff check app tests
	mypy app

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v
