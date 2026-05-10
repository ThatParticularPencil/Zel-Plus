from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from models.schemas import Incident, MemoryEntry


class MemoryStore:
    """Append-only JSON persistence for resolved incidents."""

    def __init__(self, path: Union[Path, str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict[str, Any]]:
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        return data if isinstance(data, list) else []

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    def append(self, entry: MemoryEntry) -> None:
        rows = self._read()
        rows.append(entry.model_dump())
        self._write(rows)

    def all_entries(self) -> list[MemoryEntry]:
        return [MemoryEntry.model_validate(r) for r in self._read()]


class IncidentStore:
    """Lightweight incident history JSON."""

    def __init__(self, path: Union[Path, str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict[str, Any]]:
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        return data if isinstance(data, list) else []

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    def append(self, incident: Incident) -> None:
        rows = self._read()
        rows.append(incident.model_dump())
        self._write(rows)

    def update_last_status(self, incident_id: str, status: str) -> None:
        rows = self._read()
        for r in reversed(rows):
            if r.get("incident_id") == incident_id:
                r["status"] = status
                break
        self._write(rows)

    def find_latest_active_for_channel(self, channel: str) -> Optional[Dict[str, Any]]:
        for r in reversed(self._read()):
            if r.get("status") != "active":
                continue
            for m in r.get("messages") or []:
                if isinstance(m, dict) and m.get("channel") == channel:
                    return r
        return None

    def replace_incident(self, incident: Incident) -> None:
        rows = self._read()
        for i, r in enumerate(rows):
            if r.get("incident_id") == incident.incident_id:
                rows[i] = incident.model_dump()
                self._write(rows)
                return
        raise KeyError(incident.incident_id)

    def find_by_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        for r in reversed(self._read()):
            if r.get("incident_id") == incident_id:
                return r
        return None
