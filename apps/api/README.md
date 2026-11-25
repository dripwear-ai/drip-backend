# DRIP 2.0 API

Foundation API using FastAPI, async SQLAlchemy, PostgreSQL 18 and Redis 8.2. Gate B acceptance is pending.

Use the repository-root [setup and verification guide](../../docs/setup.md). From the repository root:

```sh
uv sync --project apps/api --locked --python 3.14.7 --extra dev
pnpm test
uv run --project apps/api --locked uvicorn drip.main:create_app --factory --reload --port 8000
```

The project is installed by uv from its declared build backend. The API reads the repository-root `.env`, not `apps/api/.env`; process variables take precedence. Tests disable local dotenv loading. Live tests require the isolated test infrastructure documented in the guide.
