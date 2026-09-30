# Real Estate Recommendation System

Hybrid real-estate search for the Vietnamese market. Uses validated structured
filters, PostgreSQL full-text search, multilingual-E5 embeddings in pgvector,
Neo4j relationship retrieval, evidence-based reranking and deterministic explanations.

## Hybrid search V1

PostgreSQL remains the source of truth while Neo4j is an optional online candidate
and evidence source. Vietnamese natural-language queries are parsed into weighted
structured and semantic preferences; only the separate UI filter payload creates
hard constraints. PostgreSQL
FTS/pgvector candidates and Neo4j traversal candidates are merged before deterministic
reranking. Search falls back to PostgreSQL when Neo4j is unavailable.

```text
POST /v1/search/parse
POST /v1/search
POST /v1/search/similar/{listing_id}
GET /v1/properties/{property_id}/graph
```

Prepare a fresh local database (run from the repository root):

```bash
docker compose up -d --build backend

# Imports Final_Data.csv, graph-ready amenity distances and builds search_text.
docker compose exec backend \
  python scripts/build_search_index.py --skip-embeddings

# Generates missing pgvector embeddings through the configured embedding API.
docker compose exec backend \
  python scripts/build_search_index.py --skip-catalog-import \
  --skip-graph-metadata --batch-size 32
```

Semantic retrieval is enabled only when every active listing has an embedding. Until
then `/v1/search` remains available in structured + PostgreSQL full-text mode and
reports embedding coverage when `debug=true`.

### Embedding provider

The backend uses an OpenAI-compatible embeddings API only; it does not download or
load a Hugging Face model inside the API container. Configure a 1024-dimensional
embedding model in LM Studio, OpenRouter, or another compatible server:

```dotenv
SEARCH_EMBEDDING_PROVIDER=lmstudio
SEARCH_EMBEDDING_MODEL=qwen/qwen3-embedding-4b
SEARCH_EMBEDDING_BASE_URL=http://127.0.0.1:1234/v1
SEARCH_EMBEDDING_API_KEY=
SEARCH_EMBEDDING_TIMEOUT=60
```

When the backend runs in Docker, use
`http://host.docker.internal:1234/v1`. Both index and query vectors must come from
the same model; rebuild existing vectors with
`python scripts/build_search_index.py --skip-catalog-import --skip-graph-metadata --force`.
The API response is validated against the current pgvector schema (`vector(1024)`).

### Enable Neo4j graph search

Set `SEARCH_USE_NEO4J=true` in `.env`, then start and import the graph:

```bash
docker compose --profile graph-search up -d neo4j
docker compose exec neo4j sh -lc \
  '/var/lib/neo4j/bin/cypher-shell -u "$GRAPH_USER" -p "$GRAPH_PASSWORD" \
  -f /opt/search-graph/import_search_graph.cypher'

docker compose --profile graph-search up -d --build backend
```

The graph import uses the V2 address-mapping package. It is idempotent: existing
listings are updated by `listing_node_id`, while former administrative-area nodes
and relationships are merged without duplicating the original graph.

For a remote Neo4j configured through `NEO4J_URI`, import the same package from
the client instead of relying on server-side `LOAD CSV`:

```bash
docker compose run --rm --no-deps backend python scripts/import_neo4j_v2.py
```

Use `debug=true` on `/v1/search` to inspect graph availability, candidate count and
latency. `/v1/search/similar/{listing_id}` also combines vector similarity with shared
ward, street, geo-cluster and amenity relationships.

## Database migrations

PostgreSQL schema changes are versioned with Alembic. The backend Docker container
automatically applies pending migrations before starting Gunicorn. For local
development, migrate before starting the API:

```bash
cd backend
alembic upgrade head
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Useful commands:

```bash
alembic current
alembic history --verbose
alembic revision -m "describe schema change"
alembic downgrade -1
```

The same operations are available through `make db-upgrade`, `make db-current`,
`make db-history`, `make db-downgrade`, and
`make db-revision m="describe schema change"`. Review a downgrade and back up the
database before running it; downgrading the initial revision removes its tables.

Revisions are written explicitly because the project currently uses SQL queries
without declarative ORM models. See `backend/migrations/README.md` for details.

## LangGraph chat agents

`POST /v1/chat` uses a LangGraph supervisor to keep ordinary conversation and
general real-estate Q&A separate from property consultation. Only the consultant
agent has access to the native `search_properties` and
`inspect_previous_recommendations` tools, so greetings do not invoke hybrid
search. Authenticated conversations use PostgreSQL LangGraph checkpoints in
addition to the existing visible conversation history; guest conversations keep
their bounded context in the browser tab.

The configured OpenAI-compatible endpoint must return standard Chat Completions
`tool_calls`. Verify it after changing model/server configuration:

```bash
docker compose run --rm --no-deps backend python scripts/verify_tool_calling.py
```

## Architecture

| Service | Port | Technology | Purpose |
|---------|------|-----------|---------|
| **Backend** | 8000 | FastAPI + Gunicorn | REST API with property search and AI recommendations |
| **PostgreSQL** | 5432 | pgvector/pgvector:pg16 | Relational data + vector similarity search |
| **Neo4j (optional)** | 7474, 7687 | neo4j:5-community | Online graph candidates, relationship evidence and similar-listing traversal |
| **MinIO** | 9000, 9001 | minio/minio | S3-compatible object storage for property images |

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.9+ (only for local backend development)
- A Gemini key or an OpenAI-compatible endpoint (for AI search features)

### Option 1: Docker Compose (all services)

```bash
cp .env.example .env
# Edit .env — set your passwords and LLM provider credentials

docker compose up -d
docker compose ps        # all services should be running
```

### Option 2: Docker infra + local backend

Run databases in Docker, backend locally with hot-reload.

```bash
cp .env.example .env
# Edit .env — change:
#   HOST_DB=localhost
#   MINIO_END_POINT=localhost:9000
#   NEO4J_URI=bolt://localhost:7687

# Start infra only
docker compose up -d postgres minio minio-init

# Optional graph inspection tools only
docker compose --profile graph-tools up -d neo4j

# Run backend locally
cd backend
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## Service URLs

| URL | Service |
|-----|---------|
| http://localhost:8000 | Backend API (Swagger docs at `/`) |
| http://localhost:7474 | Neo4j Browser |
| http://localhost:9001 | MinIO Console |

## Project Structure

```
CS2307/
├── backend/               FastAPI application
│   ├── Dockerfile
│   ├── Makefile           Short database migration commands
│   ├── alembic.ini
│   ├── migrations/        Versioned PostgreSQL schema changes
│   ├── requirements.txt
│   └── src/
│       ├── main.py
│       ├── api/v1/        REST endpoints
│       ├── services/      Database, inference, LLM, MinIO, recommendation
│       ├── settings/      Config, events, middleware
│       └── utils/
├── frontend/              Next.js application
├── crawl_data/            Data scraping scripts
├── docker-compose.yml     All services
├── .env.example           Environment template
└── .gitignore
```

## Environment Variables

Copy `.env.example` to `.env`. Key variables:

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `BACKEND_LLM_PROVIDER` | `gemini`, `openai`, `openai-compatible`, `groq`, or `grok` |
| `BACKEND_LLM_MODEL` | Model name sent to the selected provider |
| `BACKEND_LLM_BASE_URL` | Base URL for a custom OpenAI-compatible endpoint |
| `BACKEND_LLM_API_KEY` | API key for an OpenAI-compatible endpoint |
| `GEMINI_API_KEYS` | Gemini API key(s), comma-separated (Gemini only) |
| `SEARCH_USE_LLM_ANSWER` | Generate the chat answer and per-listing insights from hybrid-search evidence |
| `SEARCH_EMBEDDING_PROVIDER` | OpenAI-compatible embedding API mode (`lmstudio`) |
| `SEARCH_EMBEDDING_MODEL` | Model name sent to the embedding API |
| `SEARCH_EMBEDDING_BASE_URL` | LM Studio base URL, normally ending in `/v1` |
| `HOST_DB` | `postgres` (Docker) or `localhost` (local dev) |
| `MINIO_END_POINT` | `minio:9000` (Docker) or `localhost:9000` (local dev) |
| `NEO4J_AUTH` | Format: `neo4j/<password>` |

To switch the backend to an OpenAI-compatible server, only the provider settings
need to change; application code and API routes stay the same:

```dotenv
BACKEND_LLM_PROVIDER=openai-compatible
BACKEND_LLM_MODEL=qwen2.5:14b
BACKEND_LLM_BASE_URL=http://host.docker.internal:11434/v1
BACKEND_LLM_API_KEY=
```

For OpenAI, Groq, and Grok, `BACKEND_LLM_BASE_URL` is optional because the
backend includes their standard API URLs. Set the matching model and key, for
example `BACKEND_LLM_PROVIDER=openai`, `BACKEND_LLM_MODEL=gpt-4o-mini`, and
`BACKEND_LLM_API_KEY=...`.

See `.env.example` for the full list.
