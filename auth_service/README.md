# Auth Service

A production-ready, reusable Authentication & Identity Management API built with **FastAPI** and **PostgreSQL**, following Clean Architecture. Designed to be dropped into new applications as a standalone service with minimal changes.

## Features

- Email/password registration and login
- JWT access tokens + rotating, revocable refresh tokens (with reuse-detection)
- Session management: logout (single session) and logout-all (all sessions)
- Password change with automatic session invalidation
- Brute-force protection: account lockout after repeated failed logins
- Role-based access control (`user` / `admin`), extensible to more roles
- Admin user management endpoints (list, get, deactivate)
- Rate limiting on sensitive endpoints (login, register)
- Structured error responses with machine-readable error codes
- Security headers, request logging with correlation IDs, CORS
- Async SQLAlchemy 2.0 + Alembic migrations
- Full test suite (unit + integration), Docker/Compose setup

## Architecture

Clean Architecture with strict dependency direction: **API → Services → Repositories → Models**. Nothing in `services/` or `repositories/` imports from `api/` or FastAPI request/response objects — this is what makes the core logic reusable and unit-testable without a running web server or database.

```
app/
├── api/v1/            HTTP layer only: request/response wiring, no business logic
│   ├── auth.py         /auth/* endpoints
│   └── users.py        /users/* endpoints
├── core/               Framework-agnostic building blocks
│   ├── config.py        Pydantic settings, sourced entirely from env vars
│   ├── security.py      Password hashing (bcrypt) + JWT create/verify
│   └── constants.py     Enums shared across layers
├── db/                 Database wiring
│   ├── database.py       Async engine + session factory
│   ├── session.py        FastAPI `get_db` dependency
│   ├── base.py            Declarative base (no model imports — avoids a
│   │                       circular import with models/*)
│   └── base_all_models.py Registers all models on Base.metadata; imported
│                           only by Alembic and tests, never by app code
├── models/              SQLAlchemy ORM models (User, RefreshToken)
├── schemas/             Pydantic request/response contracts + validation
├── repositories/        Data access only — no business rules
├── services/             Business logic (AuthService, UserService) —
│                          depends only on repositories + core, never on
│                          FastAPI. This is the reusable core.
├── dependencies/        FastAPI DI wiring: builds repos/services per
│                          request, extracts/validates the current user,
│                          RBAC guards (`require_role(...)`)
├── middleware/           Rate limiting, request logging, security headers
├── exceptions/           Domain exceptions (HTTP-agnostic) + global
│                          handlers that translate them to HTTP responses
├── utils/                Small cross-cutting helpers (logging config)
└── main.py               Application factory (`create_app()`)

migrations/               Alembic migration environment + versions
tests/
├── unit/                 Fast tests, mocked repositories, no DB/HTTP
├── integration/          Real HTTP requests via httpx against an
│                          in-memory-SQLite-backed app instance
└── e2e/                   Reserved for tests against a real running
                           stack (e.g. docker-compose + real Postgres)
scripts/create_superuser.py  One-off admin-account bootstrap script
```

### Why this shape is reusable

- **Business logic has no HTTP or ORM leakage.** `AuthService`/`UserService` take repository objects and return domain models/Pydantic schemas — never `Request`/`Response`. Wrap them in a CLI, a gRPC service, or a different web framework and the logic doesn't change.
- **All configuration is environment-driven** (`core/config.py`). No hardcoded hosts, secrets, or table names. Point `DATABASE_URL` and `SECRET_KEY` at a new environment and it works.
- **Domain exceptions are decoupled from HTTP status codes.** They carry a `status_code` and `error_code` but are raised and caught as plain Python exceptions in the service layer, so services stay testable without spinning up FastAPI.
- **Repositories abstract SQLAlchemy specifics** behind plain async methods (`get_by_email`, `create`, `revoke`, ...), so swapping the ORM or adding a caching layer only touches one file per entity.
- **The router is namespaced and self-contained** (`/api/v1/auth`, `/api/v1/users`) so it can be `include_router()`'d directly into a larger application's existing FastAPI app.

## Security design notes

- **Passwords**: hashed with `bcrypt` directly (not via `passlib`, whose bcrypt backend has known compatibility issues with `bcrypt>=4.1`).
- **Refresh tokens are never stored raw.** Only a SHA-256 hash and the token's `jti` are persisted, so a DB read alone can't be used to forge a session.
- **Refresh token rotation + reuse detection**: each refresh call issues a new refresh token and revokes the old one. If a *revoked* refresh token is presented again (a strong signal of token theft/replay), the entire session family for that user is revoked immediately.
- **Account lockout**: after `MAX_FAILED_LOGIN_ATTEMPTS` consecutive failures, the account is locked for `ACCOUNT_LOCKOUT_MINUTES`.
- **Password changes revoke all existing sessions**, so a compromised session can't persist after the legitimate user changes their password.
- **Constant response shape on login failures** (unknown email vs. wrong password both return `401 INVALID_CREDENTIALS`) to reduce user-enumeration risk.
- **Rate limiting** on `/auth/login` and `/auth/register` specifically, in addition to a global default limit.

## Getting started

### Option A — Docker Compose (recommended)

```bash
cp .env.example .env   # edit SECRET_KEY at minimum
docker compose up --build
```

The API will be available at `http://localhost:8000`, with interactive docs at `/docs`. Migrations run automatically on container startup.

### Option B — Local Python environment

Requires Python 3.12+ and a running PostgreSQL instance.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env   # edit DATABASE_URL and SECRET_KEY

alembic upgrade head
uvicorn app.main:app --reload
```

### Create an admin account

```bash
python -m scripts.create_superuser --email admin@example.com --password 'Str0ng!Pass1'
```

## API overview

All routes are prefixed with `/api/v1`.

| Method | Path                        | Auth        | Description                                  |
|--------|-----------------------------|-------------|-----------------------------------------------|
| POST   | `/auth/register`            | —           | Create a new account                          |
| POST   | `/auth/login`                | —           | Authenticate, receive access + refresh tokens |
| POST   | `/auth/refresh`              | —           | Exchange a refresh token for a new pair       |
| POST   | `/auth/logout`               | —           | Revoke one refresh token                      |
| POST   | `/auth/logout-all`           | Bearer      | Revoke all sessions for the current user      |
| POST   | `/auth/change-password`      | Bearer      | Change password (revokes all sessions)        |
| GET    | `/users/me`                  | Bearer      | Get the current user's profile                |
| PATCH  | `/users/me`                  | Bearer      | Update the current user's profile             |
| GET    | `/users`                     | Bearer/Admin | Paginated list of users                       |
| GET    | `/users/{user_id}`           | Bearer/Admin | Get a specific user                           |
| POST   | `/users/{user_id}/deactivate`| Bearer/Admin | Deactivate a user account                     |
| GET    | `/health`                    | —           | Liveness/readiness probe                      |

Full interactive schema: `/docs` (Swagger UI) or `/redoc`, disabled automatically when `ENVIRONMENT=production`.

### Error response shape

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Incorrect email or password."
  }
}
```

`code` is a stable, machine-readable value from `app/core/constants.py::ErrorCode` — safe to branch on in client code without parsing the human-readable `message`.

## Testing

```bash
pytest -v                                        # full suite
pytest --cov=app --cov-report=term-missing        # with coverage
```

Tests run against an isolated in-memory SQLite database (see `tests/conftest.py`), so the suite has no external dependencies and runs in seconds. The repository/service layer uses only portable SQLAlchemy constructs, so behavior verified here carries over to Postgres in production; anything Postgres-specific is exercised by the Alembic migration itself.

## Database migrations

```bash
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
alembic downgrade -1
```

`migrations/env.py` reads `DATABASE_URL` from the same `Settings` object the app uses at runtime, so there's no separate connection config to keep in sync.

## Integrating into a new application

1. Copy this repository (or add it as a git submodule / internal package).
2. Point `DATABASE_URL` at the new application's Postgres instance (a dedicated schema or database is recommended) and set a unique `SECRET_KEY`.
3. Run `alembic upgrade head` against the new database.
4. Either run this service standalone and have your other services call it over HTTP, or `include_router(api_router, prefix="/api/v1")` directly into a larger existing FastAPI app and reuse `get_current_user` / `require_role(...)` as dependencies on your own routes.
5. Extend `UserRole` in `core/constants.py` and add fields to the `User` model + an Alembic migration for any app-specific profile data.

## Configuration reference

See `.env.example` for the full list of environment variables (database pool sizing, JWT TTLs, password policy, lockout thresholds, rate limits, CORS origins).

## Known limitations / next steps

- Email verification and password-reset-via-email flows are not included (the `is_verified` flag and user model support them, but no email delivery integration is wired up).
- No OAuth/social login providers.
- Rate limiting is in-memory per-process (via `slowapi`); for multi-replica deployments, back it with Redis instead.
- `e2e/` is scaffolded but empty — intended for tests against a full docker-compose stack with real Postgres in CI.
