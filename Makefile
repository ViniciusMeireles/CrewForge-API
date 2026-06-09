# Makefile for Django/Docker operations

.PHONY: help build up down logs uv_add uv_upgrade makemigrations migrate createsuperuser shell_plus spectacular format_code test precommit

DEFAULT_GOAL := help

help:  ## Display this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ General

build:  ## Build Docker images
	docker compose build \
      --build-arg USER_NAME=$(shell whoami) \
	  --build-arg USER_ID=$(shell id -u) \
	  --build-arg GROUP_ID=$(shell id -g) \
	  --no-cache

up:  ## Start containers in background mode
	docker compose up -d

up_db:  ## Start only the database container in background mode
	docker compose up postgres_db -d

down:  ## Stop and remove containers
	docker compose down --remove-orphans

down_api:  ## Down only django_api container
	docker compose down django_api --remove-orphans

logs:  ## Show django_api container logs
	docker compose logs -f django_api

uv_add:  ## Add a new library to the uv project
	@if [ -z "$(lib)" ]; then \
		echo "Error: lib variable is not set. Usage: make uv_add lib=<library_name>"; \
		exit 1; \
	fi
	docker compose exec django_api uv add $$lib

uv_upgrade:  ## Upgrade all libraries in the uv project
	docker compose exec django_api uv sync --upgrade


##@ Development

makemigrations:  ## Make migrations for the Django project
	docker compose exec django_api uv run python manage.py makemigrations

migrate:  ## Apply migrations for the Django project
	docker compose exec django_api uv run python manage.py migrate

createsuperuser:  ## Create a superuser for the Django project
	docker compose exec django_api uv run python manage.py createsuperuser

shell_plus:  ## Open Django shell with all models imported
	docker compose exec django_api uv run python manage.py shell_plus

spectacular:  ## Generate OpenAPI schema for the Django project
	docker compose exec django_api uv run python manage.py spectacular --color --file schema.yml

format_code:  ## Format code with ruff
	docker compose exec django_api uv run ruff check . --fix
	docker compose exec django_api uv run ruff format .

test:  ## Run tests for the Django project
	docker compose exec django_api uv run pytest

precommit: format_code spectacular test  ## Run code formatting and tests
	@echo "Pre-commit checks passed."


##@ Local venv development

l_uv_upgrade:  ## Upgrade all libraries in the uv project
	uv sync --upgrade

l_makemigrations:  ## Make migrations for the Django project
	uv run python manage.py makemigrations

l_migrate:  ## Apply migrations for the Django project
	POSTGRES_HOST=localhost uv run python manage.py migrate

l_createsuperuser:  ## Create a superuser for the Django project
	POSTGRES_HOST=localhost uv run python manage.py createsuperuser

l_shell_plus:  ## Open Django shell with all models imported
	POSTGRES_HOST=localhost uv run python manage.py shell_plus

l_spectacular:  ## Generate OpenAPI schema for the Django project
	uv run python manage.py spectacular --color --file schema.yml

l_format_code:  ## Format code with ruff
	uv run ruff check . --fix
	uv run ruff format .

l_test:  ## Run tests for the Django project
	POSTGRES_HOST=localhost uv run --env-file test.env pytest

l_precommit: l_format_code l_spectacular l_test  ## Run code formatting and tests
	@echo "Pre-commit checks passed."
