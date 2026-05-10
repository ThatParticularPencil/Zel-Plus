# Zel-Plus

**Incident Intelligence Engine (IIE)** — a Python pipeline that ingests simulated frontline chat-style messages, clusters them into incidents, calls an LLM for semantic steps, generates tasks and manager summaries, and persists resolved incidents for retrieval-augmented task generation.

Inspired by operational radio-style communication (e.g. Zello); this repo is **simulation-only** (no real dispatch integrations).

## Requirements

- Python **3.10+** recommended (3.9 may work with the same codebase)
- Dependencies: see [`requirements.txt`](requirements.txt)

## Quick start

```bash
cd Zel-Plus
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`: set **`GEMINI_API_KEY`** (or **`GOOGLE_API_KEY`**) from [Google AI Studio](https://aistudio.google.com/apikey). The project defaults to **Gemini** (`IIE_LLM_PROVIDER=gemini`).

Run the interactive CLI (one JSON message per line, then Ctrl-D / EOF):

```bash
python -m app.main demo
```

Example line:

```json
{"channel":"retail_store_4","timestamp":100,"speaker":"worker_1","message":"customer needs help at aisle 4"}
```

Run the HTTP API:

```bash
python -m app.main serve
```

The server prints full `http://` links; **Cmd+click** (Mac) or **Ctrl+click** (Windows/Linux) those lines in the terminal to open Swagger UI. If your terminal does not make links clickable, use:

```bash
python -m app.main serve --open
```

(`-o` is a shortcut.) Or open a browser to `http://127.0.0.1:8000/docs` — the app also redirects `http://127.0.0.1:8000/` to `/docs`.

### Ops dashboard (React)

Four-column console UI: **message stream** (with inject bar), **semantic layer** (intent / urgency / topic / entities), **active incidents**, **detail** (tasks, summaries, RAG). **Polling** ~400ms against `GET /dashboard/state` (no WebSocket). A slim **pipeline strip** shows when incident LLMs are running and cluster sizing vs `IIE_EMIT_MIN_MESSAGES`.

Terminal 1 — API with CORS for Vite:

```bash
python -m app.main serve
```

Terminal 2 — frontend:

```bash
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173**. Use the **inject bar** at the bottom of the message column (channel, speaker, message, **Send** or Enter), or use the CLI / Swagger below.

**CLI inject** (no curl):

```bash
python -m app.main inject "Forklift stuck near dock 3"
python -m app.main inject -c dock_3 -s worker_7 -m "Still blocked"
echo "line one" | python -m app.main inject   # stdin, one message per line
python -m app.main inject                      # REPL: type lines, empty line quits
```

Override base URL with `IIE_API_URL` or `--api-url http://127.0.0.1:8000`.

You can still use `POST /ingest` from Swagger (`:8000/docs`) or `curl` if you prefer.

`POST /ingest` returns **immediately** after the first LLM pass (message semantics) and cluster preview. **Incident** construction (type, tasks, manager summary) runs in a **background task**, so the UI can show raw + semantic data without waiting for the heavy step. Poll `/dashboard/state` (the dashboard uses ~400ms polling) to see incidents when they appear.

**Note:** `fastapi.BackgroundTasks` must be available — import is at module level in `app/main.py` so the `/ingest` route resolves correctly.

## Configuration

Variables are read from the environment and optionally from a **`.env`** file in the working directory (`python-dotenv` loads it when you run `app.main`).

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini API key |
| `OPENAI_API_KEY` | OpenAI (if `IIE_LLM_PROVIDER=openai`) |
| `ANTHROPIC_API_KEY` | Anthropic (if `IIE_LLM_PROVIDER=anthropic`) |
| `IIE_LLM_PROVIDER` | `gemini` (default), `openai`, or `anthropic` |
| `IIE_LLM_MODEL` | Override model id (e.g. `gemini-2.5-flash-lite`, `gemini-2.0-flash`) |
| `IIE_OFFLINE` | `1` / `true` — skip LLM APIs and use rule-based fallbacks |
| `IIE_EMBED_MODEL` | SentenceTransformers model name for embeddings (optional upgrade path) |
| `IIE_STORAGE_DIR` | Directory for JSON stores (default: `./storage`) |
| `IIE_EMIT_MIN_MESSAGES` | Minimum messages in one cluster before emitting an incident (default `2`; use `4` if you want one incident only after four related messages) |
| `IIE_AUTO_RESOLVE` | `false` (recommended): incidents stay **active** until a resolution follow-up or `POST /resolve`. `true`: close immediately after emit (no chance to attach “fixed it” messages). |
| `IIE_RESOLUTION_ROUTING` | `true` (default): messages that look like field resolution (e.g. “cabinet open now”) attach to the **latest active** incident on that channel and close it |
| `IIE_EMBED_CLUSTER_THRESHOLD` | Cosine similarity threshold for merging clusters (default `0.62`; was `0.75`) |
| `IIE_CLUSTER_TIME_WINDOW_S` | Max seconds between messages in one cluster (default `300`) |
| `IIE_EOF_FLUSH` | CLI only: after stdin EOF, flush leftover buffer with minimum cluster size `1` |

### Incident lifecycle (what you were missing)

1. Messages land in a **per-channel buffer** and are grouped by **clustering** (time window + embedding similarity + **lexical/anchor overlap** so “cabinet stuck” and “got the cabinet open” can merge even when the LLM reuses a generic topic like `frontline_message`).
2. An **incident** is only opened when a cluster reaches **`IIE_EMIT_MIN_MESSAGES`** (default 2), then the heavy LLM steps produce type, tasks, and summary.
3. With **`IIE_AUTO_RESOLVE=false`**, that incident stays **active** in `incident_store.json` so a follow-up can match it.
4. With **`IIE_RESOLUTION_ROUTING=true`**, a message whose text matches resolution phrases (and intent `update` / qualifying `report`) **appends to the latest active incident** on that channel, writes memory, and marks it **resolved** — instead of spawning a second bogus incident.
5. **`POST /resolve/{incident_id}`** still works for manual closure.

## HTTP API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ingest` | Body: `{ "channel", "timestamp", "speaker", "message" }` — runs full pipeline |
| `POST` | `/resolve/{incident_id}` | Optional manual resolve (`outcome` query param) |
| `GET` | `/memory` | List persisted memory entries |

## Pipeline (high level)

1. **Ingest** — validate message, append per-channel buffer  
2. **Process (LLM)** — intent, urgency, topic, entities (JSON)  
3. **Embed** — optional vectors for clustering / retrieval  
4. **Cluster** — same channel, time window, shared **non-generic** topic, **embedding** similarity (see `IIE_EMBED_CLUSTER_THRESHOLD`), or **lexical/anchor** overlap on message text; `intent=noise` excluded  
5. **Incident (LLM)** — type, severity, summary  
6. **Tasks (LLM)** — up to 3 abstract tasks; past incidents injected when available  
7. **Summary (LLM)** — short manager-facing paragraph  
8. **Memory** — optional resolve + append `MemoryEntry` to JSON store  

Implementation lives under [`engine/`](engine/), schemas under [`models/`](models/), LLM client under [`services/`](services/).

## Project layout

```
engine/          pipeline steps (ingest, processor, clustering, incident, tasks, summary, memory, retrieval)
models/          Pydantic schemas
services/        LLM + embedding clients
storage/         default JSON persistence (memory_store.json, incident_store.json)
app/main.py      FastAPI app + CLI entrypoint
```

## Offline / no API keys

Set `IIE_OFFLINE=1` (or omit provider keys so the engine falls back) to run without calling Gemini/OpenAI/Anthropic. Outputs use deterministic fallbacks; useful for CI or layout testing.

## Security

- Keep **`.env` out of git** (it is gitignored). Use `.env.example` as a template only.
- Do not commit API keys or paste them into issues.

## License / scope

This is a **reasoning and simulation** MVP: no production dispatch, no audio pipelines, no external ticketing integrations unless you add them yourself.
