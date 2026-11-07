"""Plain data classes shared by the parser, storage, statistics and UI."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# The three "parts" every log is separated into.
CAT_SERVER = "server"
CAT_COMMAND = "command"
CAT_CHAT = "chat"

CATEGORY_LABELS = {
    CAT_SERVER: "Server",
    CAT_COMMAND: "Command",
    CAT_CHAT: "Chat",
}

EVENT_LABELS = {
    "chat": "Chat",
    "command": "Command",
    "feedback": "Command feedback",
    "join": "Joined",
    "leave": "Left",
    "login": "Login",
    "disconnect": "Disconnected",
    "uuid": "UUID",
    "death": "Death",
    "advancement": "Advancement",
    "start": "Server starting",
    "ready": "Server ready",
    "stop": "Server stopping",
    "warning": "Warning",
    "error": "Error",
    "info": "Info",
}

NO_PLAYERS: tuple = ()


@dataclass(slots=True)
class Entry:
    """One parsed log entry (a log line plus any continuation lines)."""

    ts: datetime
    category: str
    event: str
    level: str
    thread: str
    player: str
    players: tuple
    message: str
    extra: str = ""
    line_no: int = 0
    import_id: int = 0
    id: int = 0


@dataclass
class ParsedLog:
    """Result of parsing one file."""

    entries: list = field(default_factory=list)
    line_count: int = 0
    log_date: str = ""
    first_ts: str = ""
    last_ts: str = ""


@dataclass
class ImportInfo:
    """A row of the import history."""

    id: int
    name: str
    path: str
    sha256: str
    size: int
    imported_at: str
    log_date: str
    first_ts: str
    last_ts: str
    line_count: int
    entry_count: int
