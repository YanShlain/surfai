# Surfai — Workflow Evaluator

A FastAPI service that receives a **workflow graph** as JSON, validates it, executes each step (variables, branching, file reads, outbound HTTP calls, printing), and returns a structured result with status, variables, print output, and errors.

Designed for internal tooling and interview/demo scenarios, with a clean 3-tier architecture that can be hardened for production. See [docs/design.md](docs/design.md) for architecture, flow diagrams, and the production roadmap.

---

## Requirements

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) package manager

---

## Quick start

```bash
# Install dependencies (creates .venv, includes dev tools)
uv sync

# Run the API
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Run tests
uv run pytest

# Run tests with coverage (fails below 90% on app/)
uv run pytest --cov=app --cov-report=term-missing
```

Open `http://127.0.0.1:8000/health` to confirm the server is up.

---

## API

### `GET /health`

Liveness check.

**Response:**

```json
{ "status": "ok" }
```

### `POST /v1/workflows/execute`

Execute a workflow synchronously.

**Headers (optional):**

| Header | Description |
|--------|-------------|
| `Content-Type` | `application/json` (required) |
| `X-Request-ID` | Correlation ID; generated if omitted and echoed on the response |

**Request body:**

```json
{
  "workflow": {
    "schema_version": 1,
    "entry": "set",
    "nodes": [
      {
        "id": "set",
        "action": "set_variable",
        "name": "x",
        "value": 1,
        "next": "print-it"
      },
      {
        "id": "print-it",
        "action": "print",
        "parts": [{ "type": "variable", "name": "x" }],
        "next": "done"
      },
      {
        "id": "done",
        "action": "exit",
        "status": "success"
      }
    ]
  }
}
```

**Success response (HTTP 200):**

```json
{
  "status": "success",
  "variables": { "x": 1 },
  "prints": ["1"],
  "error": null
}
```

**Failure response (HTTP 200):**

Business and validation failures still return HTTP **200**. Check `status` and `error`:

```json
{
  "status": "failure",
  "variables": {},
  "prints": [],
  "error": {
    "code": "INVALID_NODE_ROUTING",
    "message": "Node 'bad' has mixed routing fields",
    "step_id": null,
    "action": null,
    "cause": null
  }
}
```

Malformed requests (invalid JSON shape) return **422**.

### Example with curl

Using the bundled test fixture:

```bash
curl -X POST http://127.0.0.1:8000/v1/workflows/execute \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: demo-1" \
  -d @tests/fixtures/workflows/happy_path.json
```

---

## Workflow actions

| Action | Description |
|--------|-------------|
| `set_variable` | Set a string or number variable |
| `call_service` | POST JSON to an external URL; store response as a string variable |
| `read_file` | Read a file relative to the sandbox root |
| `print` | Append one line to the `prints` array |
| `if_equals` | Branch on string comparison of two operands |
| `if_file_exists` | Branch on whether a sandboxed file exists |
| `exit` | Terminate with `success` or `failure` |

Full schema, routing rules, and validation matrix: [plan.md](plan.md) and [docs/design.md](docs/design.md).

---

## Configuration

Environment variables (read at startup from `app/config.py`):

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKFLOW_FS_ROOT` | `.` | Root directory for `read_file` / `if_file_exists` |
| `CALL_SERVICE_TIMEOUT_SECONDS` | `10` | Default HTTP timeout per attempt |
| `CALL_SERVICE_MAX_TIMEOUT_SECONDS` | `60` | Maximum allowed node timeout |
| `CALL_SERVICE_MAX_RETRIES` | `3` | Default retries after timeout |
| `CALL_SERVICE_RETRY_BASE_SECONDS` | `0.5` | Exponential backoff base |
| `CALL_SERVICE_RETRY_MAX_SECONDS` | `30` | Backoff ceiling |
| `CALL_SERVICE_MAX_RETRIES_CAP` | `5` | Maximum allowed node retries |

Example — run with a dedicated file sandbox:

```bash
WORKFLOW_FS_ROOT=/data/workflows uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Project layout

```
app/
  api/              # HTTP routes, schemas, middleware
  domain/           # Models, ports, validation types
  infrastructure/   # File reader, HTTP client, retry policy
  services/         # Validator, executor, action handlers
  config.py         # Environment settings
  dependencies.py   # Dependency injection wiring
  main.py           # FastAPI app factory
main.py             # ASGI entry (uvicorn target)
tests/
  unit/             # Service and infrastructure unit tests
  integration/      # Full HTTP scenario tests
  fixtures/         # Sample workflows and expected responses
docs/
  design.md         # Architecture and production roadmap
```

---

## Development

```bash
# Sync after dependency changes
uv sync

# Run a single test file
uv run pytest tests/integration/api/test_execute_happy_path.py -v
```

The test suite uses pytest with asyncio mode `auto`. Integration tests drive the app via httpx ASGITransport without starting a real server.

---

## Documentation

- [docs/design.md](docs/design.md) — How the system works, Mermaid diagrams, production readiness (persistence, graceful shutdown, scaling, resilience)
- [plan.md](plan.md) — Detailed workflow JSON schema and validation rules
