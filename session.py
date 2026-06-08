"""Persistent session storage for mybot."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SessionSummary:
    key: str
    title: str
    first_user_message: str
    message_count: int
    updated_at: str


@dataclass(slots=True)
class Session:
    key: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    title: str = ""

    def add_message(self, role: str, content: str, **extra: Any) -> None:
        self.messages.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                **extra,
            }
        )
        self.updated_at = datetime.now().isoformat()

    def get_history(self, max_messages: int) -> list[dict[str, Any]]:
        if max_messages <= 0:
            return list(self.messages)
        return list(self.messages[-max_messages:])

    def rename(self, title: str) -> None:
        self.title = title.strip()
        self.updated_at = datetime.now().isoformat()

    @property
    def first_user_message(self) -> str:
        for message in self.messages:
            if message.get("role") == "user":
                return str(message.get("content") or "")
        return ""


class SessionStore:
    """Simple JSON-backed session store."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def get_or_create(self, key: str) -> Session:
        path = self._path_for(key)
        if not path.exists():
            return Session(key=key)
        data = json.loads(path.read_text(encoding="utf-8"))
        return Session(
            key=data["key"],
            messages=data.get("messages", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            title=data.get("title", ""),
        )

    def save(self, session: Session) -> None:
        path = self._path_for(session.key)
        temp = path.with_suffix(".tmp")
        payload = {
            "key": session.key,
            "messages": session.messages,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "title": session.title,
        }
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)

    def list_sessions(self) -> list[SessionSummary]:
        summaries: list[SessionSummary] = []
        for path in self.root.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                session = Session(
                    key=data["key"],
                    messages=data.get("messages", []),
                    created_at=data.get("created_at", datetime.now().isoformat()),
                    updated_at=data.get("updated_at", datetime.now().isoformat()),
                    title=data.get("title", ""),
                )
            except Exception:
                continue
            summaries.append(
                SessionSummary(
                    key=session.key,
                    title=session.title,
                    first_user_message=session.first_user_message,
                    message_count=len(session.messages),
                    updated_at=session.updated_at,
                )
            )
        return sorted(summaries, key=lambda item: item.updated_at, reverse=True)

    def _path_for(self, key: str) -> Path:
        safe = key.replace("/", "_").replace(":", "__")
        return self.root / f"{safe}.json"
