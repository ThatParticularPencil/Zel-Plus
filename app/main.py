from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel

from engine.clustering import cluster_messages
from engine.incident_builder import build_incident_llm
from engine.memory import IncidentStore, MemoryStore
from engine.message_ingestor import BufferedMessage, MessageIngestor
from engine.processor import process_message_llm
from engine.retrieval import format_rag_lines, retrieve_similar_memories
from engine.summarizer import generate_summary_llm
from engine.task_generator import generate_tasks_llm
from models.schemas import ClusterMeta, Incident, MemoryEntry
from services.embedding_client import EmbeddingClient
from services.llm_client import LLMClient

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]


def _storage_dir() -> Path:
    return Path(os.getenv("IIE_STORAGE_DIR", str(ROOT / "storage")))


def _emit_min_messages() -> int:
    """Minimum messages in a cluster before creating an incident (tune for batching)."""
    return max(1, int(os.getenv("IIE_EMIT_MIN_MESSAGES", "2")))


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
    return LLMClient()


def _context_signature(channel: str, buffers: list[BufferedMessage]) -> str:
    topics: list[str] = []
    ents: list[str] = []
    for b in buffers:
        if b.processed:
            topics.append(b.processed.topic.strip().lower())
            ents.extend(b.processed.entities)
    raw = f"{channel}|{sorted(set(topics))}|{sorted(set(ents))}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _memory_signature_from_incident(incident: Incident) -> str:
    ch = incident.messages[0].channel if incident.messages else ""
    raw = f"{ch}|{incident.incident_type}|{incident.summary}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


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
        self.storage_dir = storage_dir or _storage_dir()
        if auto_resolve is None:
            auto_resolve = os.getenv("IIE_AUTO_RESOLVE", "true").lower() in ("1", "true", "yes")
        self.auto_resolve = auto_resolve
        self.llm = _make_llm()
        self.embedder = EmbeddingClient()
        self.ingestor = MessageIngestor()
        self.memory_store = MemoryStore(self.storage_dir / "memory_store.json")
        self.incident_store = IncidentStore(self.storage_dir / "incident_store.json")

    def ingest_message(self, raw: dict) -> BufferedMessage:
        return self.ingestor.ingest_message(raw)

    def _emit_clusters(
        self,
        channel: str,
        buffer: list[BufferedMessage],
        clusters: list[ClusterMeta],
        *,
        min_sz: int,
    ) -> tuple[list[IncidentEmit], set[str]]:
        emits: list[IncidentEmit] = []
        to_remove: set[str] = set()
        for cl in clusters:
            bufs = [b for b in buffer if b.internal_id in set(cl.message_ids)]
            if not bufs:
                continue
            if len(bufs) < min_sz:
                continue

            built = build_incident_llm(self.llm, bufs)
            sig = _context_signature(channel, bufs)
            memories = self.memory_store.all_entries()
            matches = retrieve_similar_memories(
                self.embedder,
                memories,
                incident_type=built.incident_type,
                context_signature=sig,
                top_k=3,
            )
            rag = format_rag_lines(matches)

            inc = Incident(
                incident_id=cl.incident_id,
                incident_type=built.incident_type,
                severity=built.severity,
                summary=built.summary,
                status="active",
                messages=[b.message for b in bufs],
                tasks=[],
            )
            tasks = generate_tasks_llm(
                self.llm,
                inc,
                [b.message for b in bufs],
                built.severity,
                rag,
            )
            inc.tasks = tasks
            mgr = generate_summary_llm(self.llm, inc)
            emits.append(IncidentEmit(incident=inc, manager_summary=mgr, memory_matches=matches))
            to_remove |= set(cl.message_ids)
        return emits, to_remove

    def _persist_emits(self, emits: list[IncidentEmit]) -> None:
        for em in emits:
            self.incident_store.append(em.incident)
            if self.auto_resolve:
                self._resolve_to_memory(em.incident, em.incident.tasks)

    def process_pipeline(self, raw: dict) -> dict:
        """Full per-message execution: ingest → process → cluster → incidents."""
        buf = self.ingest_message(raw)
        processed = process_message_llm(self.llm, buf.message)
        self.ingestor.add_to_buffer(buf, processed)

        channel = buf.channel
        buffer = self.ingestor.buffer_for(channel)
        clusters = cluster_messages(buffer, self.embedder)

        emits, to_remove = self._emit_clusters(
            channel, buffer, clusters, min_sz=_emit_min_messages()
        )

        if to_remove:
            self.ingestor.remove_internal_ids(channel, to_remove)

        self._persist_emits(emits)

        return {
            "processed": processed.model_dump(),
            "incidents": [
                {
                    "incident": e.incident.model_dump(),
                    "manager_summary": e.manager_summary,
                    "memory_matches": [m.model_dump() for m in e.memory_matches],
                }
                for e in emits
            ],
        }

    def flush_eof(self) -> dict:
        """Emit remaining clustered messages (min cluster size 1). Used at CLI EOF."""
        all_incidents: list[dict] = []
        for channel in self.ingestor.channels():
            buffer = self.ingestor.buffer_for(channel)
            if not buffer:
                continue
            clusters = cluster_messages(buffer, self.embedder)
            emits, to_remove = self._emit_clusters(channel, buffer, clusters, min_sz=1)
            if to_remove:
                self.ingestor.remove_internal_ids(channel, to_remove)
            self._persist_emits(emits)
            all_incidents.extend(
                {
                    "incident": e.incident.model_dump(),
                    "manager_summary": e.manager_summary,
                    "memory_matches": [m.model_dump() for m in e.memory_matches],
                }
                for e in emits
            )
        return {"incidents": all_incidents}

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
    from fastapi.responses import RedirectResponse

    app = FastAPI(title="Incident Intelligence Engine", version="0.1.0")
    engine = IncidentEngine()

    @app.get("/")
    def root():
        return RedirectResponse(url="/docs", status_code=307)

    @app.post("/ingest")
    def ingest(body: IngestBody):
        return engine.process_pipeline(body.model_dump())

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
    parser.add_argument("mode", choices=["demo", "serve"], nargs="?", default="demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--open",
        "-o",
        action="store_true",
        help="Open /docs in the default browser (serve mode only)",
    )
    args = parser.parse_args()
    if args.mode == "serve":
        import uvicorn

        _notify_serve_urls(args.host, args.port, open_browser=args.open)
        uvicorn.run("app.main:app", host=args.host, port=args.port, reload=False)
    else:
        run_demo_cli()


if __name__ == "__main__":
    main()
