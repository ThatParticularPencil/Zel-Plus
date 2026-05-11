from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks
from pydantic import BaseModel

from engine.incident_router import IncidentRouter
from engine.memory import IncidentStore, MemoryStore
from engine.message_ingestor import BufferedMessage, MessageIngestor
from engine.processor import process_message_llm
from models.schemas import Incident, MemoryEntry, ProcessedMessage
from services.embedding_client import EmbeddingClient
from services.llm_client import LLMClient

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]


def _storage_dir() -> Path:
    return Path(os.getenv("IIE_STORAGE_DIR", str(ROOT / "storage")))


def _make_llm() -> Optional[LLMClient]:
    if os.getenv("IIE_OFFLINE", "").lower() in ("1", "true", "yes"):
        return None
    prov = (os.getenv("IIE_LLM_PROVIDER") or "gemini").lower()
    if prov == "openai" and not os.getenv("OPENAI_API_KEY"):
        return None
    if prov == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        return None
    if prov == "gemini" and not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        return None
    if prov == "groq" and not os.getenv("GROQ_API_KEY"):
        return None
    return LLMClient()


def _memory_signature_from_incident(incident: Incident) -> str:
        return f"{incident.incident_type}\n{incident.summary}\nentities:{','.join(incident.entities)}"

def _resolution_from_tasks(tasks: list[dict]) -> str:
    parts = [str(t.get("action", "")) for t in tasks if t.get("action")]
    return "_".join(parts) if parts else "unknown"


@dataclass
class IncidentEmit:
    incident: Incident
    manager_summary: str
    memory_matches: list[MemoryEntry] = field(default_factory=list)


class IncidentEngine:
    """Operational reasoning pipeline over streamed messages."""

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        *,
        auto_resolve: Optional[bool] = None,
    ) -> None:
        if storage_dir is None:
            self.storage_dir = _storage_dir()
        else:
            self.storage_dir = Path(storage_dir)
        if auto_resolve is None:
            auto_resolve = os.getenv("IIE_AUTO_RESOLVE", "false").lower() in ("1", "true", "yes")
        self.auto_resolve = auto_resolve
        self.llm = _make_llm()
        self.embedder = EmbeddingClient()
        self.ingestor = MessageIngestor()
        self.memory_store = MemoryStore(self.storage_dir / "memory_store.json")
        self.incident_store = IncidentStore(self.storage_dir / "incident_store.json")
        self.router = IncidentRouter(self.incident_store, self.llm, self.embedder)
        self._dashboard_messages: list[dict[str, Any]] = []
        self._dashboard_incidents: dict[str, dict[str, Any]] = {}
        self._semantic_feed: list[dict[str, Any]] = []
        self._pipeline_lock = threading.Lock()

    def _record_semantic(self, buf: BufferedMessage, processed: ProcessedMessage) -> None:
        record = {
            "id": str(uuid.uuid4()),
            "timestamp": buf.message.timestamp,
            "channel": buf.message.channel,
            "speaker": buf.message.speaker,
            "message": buf.message.message,
            "event_type": processed.event_type,
            "urgency": processed.urgency,
            "topic": processed.topic,
            "entities": list(processed.entities),
        }
        if processed.raw_response is not None:
            record["raw_response"] = processed.raw_response
        self._semantic_feed.append(record)
        if len(self._semantic_feed) > 400:
            self._semantic_feed = self._semantic_feed[-400:]

    def _record_dashboard_message(self, buf: BufferedMessage, processed: ProcessedMessage) -> None:
        record = {
            "id": str(uuid.uuid4()),
            "timestamp": buf.message.timestamp,
            "channel": buf.message.channel,
            "speaker": buf.message.speaker,
            "message": buf.message.message,
            "urgency": processed.urgency,
            "event_type": processed.event_type,
            "topic": processed.topic,
            "entities": list(processed.entities),
        }
        if processed.raw_response is not None:
            record["raw_response"] = processed.raw_response
        self._dashboard_messages.append(record)
        if len(self._dashboard_messages) > 400:
            self._dashboard_messages = self._dashboard_messages[-400:]

    def _record_dashboard_emits(self, emits: list[IncidentEmit]) -> None:
        for e in emits:
            self._dashboard_incidents[e.incident.incident_id] = {
                "incident": e.incident.model_dump(),
                "manager_summary": e.manager_summary,
                "memory_matches": [m.model_dump() for m in e.memory_matches],
            }
        if len(self._dashboard_incidents) > 120:
            # Keep the most recent incidents by updated_at when the dashboard becomes large.
            ordered = sorted(
                self._dashboard_incidents.values(),
                key=lambda item: item["incident"]["updated_at"],
                reverse=True,
            )[:120]
            self._dashboard_incidents = {
                item["incident"]["incident_id"]: item for item in reversed(ordered)
            }

    def ingest_message(self, raw: dict) -> BufferedMessage:
        return self.ingestor.ingest_message(raw)

    def _route_incident(
        self,
        buf: BufferedMessage,
        processed: ProcessedMessage,
    ) -> Optional[IncidentEmit]:
        incident = self.router.route_message(buf.message, processed)
        if incident is None:
            return None

        if incident.status == "resolved" and self.auto_resolve:
            self._resolve_to_memory(incident, list(incident.tasks))

        return IncidentEmit(
            incident=incident,
            manager_summary=incident.summary,
            memory_matches=[],
        )

    def process_pipeline(self, raw: dict, *, background_tasks: Optional[Any] = None) -> dict:
        """Ingest → semantic extraction → incident routing."""
        with self._pipeline_lock:
            buf = self.ingest_message(raw)
            processed = process_message_llm(self.llm, buf.message)
            self.ingestor.add_to_buffer(buf, processed)
            emit = self._route_incident(buf, processed)
            self._record_dashboard_message(buf, processed)
            self._record_semantic(buf, processed)

            if emit is None:
                return {
                    "processed": processed.model_dump(),
                    "incidents": [],
                }

            self._record_dashboard_emits([emit])
            return {
                "processed": processed.model_dump(),
                "incidents": [
                    {
                        "incident": emit.incident.model_dump(),
                        "manager_summary": emit.manager_summary,
                        "memory_matches": [m.model_dump() for m in emit.memory_matches],
                    }
                ],
            }

    def flush_eof(self) -> dict:
        return {"incidents": []}

    def _resolve_to_memory(self, incident: Incident, tasks: list[dict]) -> None:
        incident.status = "resolved"
        ts = incident.messages[-1].timestamp if incident.messages else 0
        entry = MemoryEntry(
            incident_type=incident.incident_type,
            context_signature=_memory_signature_from_incident(incident),
            resolution=_resolution_from_tasks(tasks),
            outcome="success",
            timestamp=ts,
        )
        self.memory_store.append(entry)
        self.incident_store.update_last_status(incident.incident_id, "resolved")

    def resolve_incident(self, incident_id: str, outcome: str = "success") -> bool:
        target = self.incident_store.find_by_id(incident_id)
        if not target:
            return False
        inc = Incident.model_validate(target)
        entry = MemoryEntry(
            incident_type=inc.incident_type,
            context_signature=_memory_signature_from_incident(inc),
            resolution=_resolution_from_tasks(inc.tasks),
            outcome=outcome,
            timestamp=inc.messages[-1].timestamp if inc.messages else 0,
        )
        self.memory_store.append(entry)
        self.incident_store.update_last_status(incident_id, "resolved")
        return True


def _panel(title: str, body: str) -> None:
    w = 72
    print("\n" + "=" * w)
    print(f" {title}")
    print("=" * w)
    print(body.rstrip() or "(empty)")


def run_inject_cli(args: argparse.Namespace) -> None:
    """POST messages to a running API (streamlined alternative to curl)."""
    import httpx

    msg = (args.message or "").strip() or (
        " ".join(args.ingest_words).strip() if args.ingest_words else ""
    )
    url = f"{args.api_url.rstrip('/')}/ingest"

    def post_one(text: str) -> None:
        payload = {
            "channel": args.channel,
            "timestamp": int(time.time()),
            "speaker": args.speaker,
            "message": text.strip(),
        }
        with httpx.Client(timeout=300.0) as client:
            r = client.post(url, json=payload)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            print(e.response.text, file=sys.stderr)
            raise
        data = r.json()
        if args.quiet:
            print("ok", file=sys.stderr)
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))

    if msg:
        post_one(msg)
        return
    if not sys.stdin.isatty():
        for line in sys.stdin:
            t = line.strip()
            if t:
                post_one(t)
        return
    print("inject: type a message, Enter sends, empty line quits", file=sys.stderr)
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        t = line.strip()
        if not t:
            break
        post_one(t)


def run_demo_cli() -> None:
    engine = IncidentEngine()
    eof_flush = os.getenv("IIE_EOF_FLUSH", "true").lower() in ("1", "true", "yes")
    print("IIE demo — paste JSON lines (Message). Ctrl-D to finish.\n")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
            continue
        out = engine.process_pipeline(raw)
        _panel(
            "INPUT STREAM (processed)",
            json.dumps(out["processed"], indent=2, ensure_ascii=False),
        )
        for block in out["incidents"]:
            inc = block["incident"]
            _panel("INCIDENT", json.dumps(inc, indent=2, ensure_ascii=False))
            _panel("TASKS", json.dumps(inc.get("tasks", []), indent=2, ensure_ascii=False))
            _panel("MANAGER SUMMARY", block.get("manager_summary", ""))
            _panel(
                "MEMORY MATCHES (RAG)",
                json.dumps(block.get("memory_matches", []), indent=2, ensure_ascii=False),
            )
        if not out["incidents"]:
            _panel("INCIDENTS", "No incident emitted for this message (noise, window, or buffer state).")
    if eof_flush:
        flushed = engine.flush_eof()
        if flushed["incidents"]:
            _panel(
                "EOF FLUSH (remaining buffer)",
                json.dumps(flushed["incidents"], indent=2, ensure_ascii=False),
            )


class IngestBody(BaseModel):
    channel: str
    timestamp: int
    speaker: str
    message: str


def create_app():
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import RedirectResponse

    app = FastAPI(title="Incident Intelligence Engine", version="0.1.0")
    engine = IncidentEngine()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root():
        return RedirectResponse(url="/docs", status_code=307)

    @app.get("/dashboard/state")
    def dashboard_state():
        return {
            "messages": engine._dashboard_messages,
            "semantic": engine._semantic_feed,
            "incidents": sorted(
                list(engine._dashboard_incidents.values()),
                key=lambda item: item["incident"]["updated_at"],
            ),
        }

    @app.post("/ingest")
    def ingest(body: IngestBody, background_tasks: BackgroundTasks):
        return engine.process_pipeline(body.model_dump(), background_tasks=background_tasks)

    @app.post("/resolve/{incident_id}")
    def resolve(incident_id: str, outcome: str = "success"):
        ok = engine.resolve_incident(incident_id, outcome=outcome)
        return {"ok": ok}

    @app.get("/memory")
    def memory():
        return {"entries": [e.model_dump() for e in engine.memory_store.all_entries()]}

    return app


app = create_app()


def _browser_open_url(host: str, port: int, path: str = "/docs") -> str:
    """Host string suitable for opening in a browser (avoid bind-only addresses)."""
    if host in ("0.0.0.0", "::", "[::]"):
        display_host = "127.0.0.1"
    else:
        display_host = host
    return f"http://{display_host}:{port}{path}"


def _notify_serve_urls(host: str, port: int, *, open_browser: bool) -> None:
    docs = _browser_open_url(host, port, "/docs")
    redoc = _browser_open_url(host, port, "/redoc")
    root = _browser_open_url(host, port, "/")
    print("\n  Incident Intelligence Engine — API\n")
    print(f"    Interactive docs:  {docs}")
    print(f"    ReDoc:             {redoc}")
    print(f"    Root (→ /docs):    {root}")
    dash = _browser_open_url("127.0.0.1", 5173, "/")
    print(f"    Dashboard (Vite):  {dash}  (run: cd frontend && npm run dev)\n")
    print("\n  Tip: Cmd+click (Mac) or Ctrl+click (Windows/Linux) the http:// link above.\n")
    if open_browser:
        import threading
        import time
        import webbrowser

        def _open() -> None:
            time.sleep(0.8)
            webbrowser.open(docs)

        threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Incident Intelligence Engine")
    parser.add_argument(
        "mode",
        choices=["demo", "serve", "inject"],
        nargs="?",
        default="demo",
        help="demo=stdin JSON lines; serve=API; inject=POST /ingest client",
    )
    parser.add_argument(
        "ingest_words",
        nargs="*",
        default=[],
        help="inject: message text (joined with spaces); optional if using -m or stdin/REPL",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--open",
        "-o",
        action="store_true",
        help="Open /docs in the default browser (serve mode only)",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("IIE_API_URL", "http://127.0.0.1:8000"),
        help="inject: base URL of running API",
    )
    parser.add_argument(
        "--channel",
        "-c",
        default=os.getenv("IIE_INJECT_CHANNEL", "sim_channel"),
        help="inject: message channel",
    )
    parser.add_argument(
        "--speaker",
        "-s",
        default=os.getenv("IIE_INJECT_SPEAKER", "worker_1"),
        help="inject: speaker id",
    )
    parser.add_argument(
        "-m",
        "--message",
        default=None,
        help="inject: single message body",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="inject: only print ok on success",
    )
    args = parser.parse_args()
    if args.mode != "inject" and args.ingest_words:
        parser.error(
            f"Unexpected arguments for mode '{args.mode}': {' '.join(args.ingest_words)}"
        )
    if args.mode == "serve":
        import uvicorn

        _notify_serve_urls(args.host, args.port, open_browser=args.open)
        uvicorn.run("app.main:app", host=args.host, port=args.port, reload=False)
    elif args.mode == "inject":
        run_inject_cli(args)
    else:
        run_demo_cli()


if __name__ == "__main__":
    main()
