# Database migrations

Alembic is the only supported way to change the PostgreSQL schema. Run commands
from `backend/` (or add `-c backend/alembic.ini` when running from the repository
root).

```bash
# Apply every pending revision
alembic upgrade head

# Inspect state and history
alembic current
alembic history --verbose

# Create an empty revision, then implement upgrade() and downgrade()
alembic revision -m "add property status"

# Roll back one revision
alembic downgrade -1
```

Equivalent shortcuts are available as `make db-upgrade`, `make db-current`,
`make db-history`, `make db-downgrade`, and
`make db-revision m="describe change"`.

Before downgrading, review the target revision's `downgrade()` function and take a
backup. Downgrading the initial revision removes the application tables and their
data; the `vector` extension itself is intentionally retained because another
schema may use it.

The application has no declarative SQLAlchemy model metadata, so `--autogenerate`
is intentionally not supported. Every schema change must be explicit and reviewed.

`DATABASE_URL` can provide the full connection URL. Otherwise Alembic reads
`USERNAME_DB`, `PASSWORD_DB`, `HOST_DB`, `PORT_DB`, and `DATABASE` from the
environment or the nearest `.env` file.
