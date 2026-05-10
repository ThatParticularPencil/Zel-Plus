from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import List, Optional

from models.schemas import Message, ProcessedMessage


@dataclass
class BufferedMessage:
    internal_id: str
    channel: str
    message: Message
    processed: Optional[ProcessedMessage] = None
    embedding_msg: Optional[List[float]] = None
    embedding_topic: Optional[List[float]] = None


class MessageIngestor:
    """Validate messages and maintain per-channel buffers."""

    def __init__(self) -> None:
        self._buffers: dict[str, list[BufferedMessage]] = {}

    def ingest_message(self, raw: dict) -> BufferedMessage:
        msg = Message.model_validate(raw)
        bid = str(uuid.uuid4())
        buf = BufferedMessage(internal_id=bid, channel=msg.channel, message=msg)
        self._buffers.setdefault(msg.channel, []).append(buf)
        return buf

    def add_to_buffer(self, buf: BufferedMessage, processed: ProcessedMessage) -> None:
        buf.processed = processed

    def buffer_for(self, channel: str) -> list[BufferedMessage]:
        return list(self._buffers.get(channel, []))

    def channels(self) -> list[str]:
        return list(self._buffers.keys())

    def remove_internal_ids(self, channel: str, ids: set[str]) -> None:
        self._buffers[channel] = [b for b in self.buffer_for(channel) if b.internal_id not in ids]
