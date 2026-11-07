"""Player statistics and session (play time) computation."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from itertools import chain
from typing import Optional


@dataclass
class Session:
    start: datetime
    end: datetime
    clean: bool = True   # False when the log ended / server stopped mid-session

    @property
    def seconds(self) -> float:
        return max((self.end - self.start).total_seconds(), 0.0)


@dataclass
class PlayerStats:
    name: str
    events: int = 0
    messages: int = 0
    commands: int = 0
    joins: int = 0
    deaths: int = 0
    advancements: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    sessions: list = field(default_factory=list)
    ips: set = field(default_factory=set)
    uuids: set = field(default_factory=set)
    command_counter: Counter = field(default_factory=Counter)

    @property
    def playtime(self) -> float:
        return sum(s.seconds for s in self.sessions)

    @property
    def top_command(self) -> str:
        if not self.command_counter:
            return ""
        cmd, n = self.command_counter.most_common(1)[0]
        return f"{cmd} ({n})"


@dataclass
class Overview:
    entries: int = 0
    players: int = 0
    messages: int = 0
    commands: int = 0
    first: Optional[datetime] = None
    last: Optional[datetime] = None


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def compute_stats(entries: list, markers: list, selected: frozenset,
                  start: Optional[datetime] = None,
                  end: Optional[datetime] = None) -> tuple:
    """Compute per-player statistics.

    ``entries``  - entries already filtered by player / time range.
    ``markers``  - all server start/stop entries (close open sessions).
    ``selected`` - restrict output to these players (empty = everyone).
    Returns (dict name -> PlayerStats, Overview).
    """
    marks = [m for m in markers
             if (start is None or m.ts >= start) and (end is None or m.ts <= end)]
    merged = sorted(chain(entries, marks), key=lambda e: e.ts) if marks else entries

    stats: dict = {}
    open_sessions: dict = {}
    overview = Overview()
    last_ts: Optional[datetime] = None

    def close_all(at: datetime, clean: bool) -> None:
        for name, began in open_sessions.items():
            stats[name].sessions.append(Session(began, at, clean))
        open_sessions.clear()

    for e in merged:
        last_ts = e.ts
        ev = e.event
        if ev == "stop":
            close_all(e.ts, False)
            continue
        if ev == "start":
            close_all(e.ts, False)
            continue
        if ev == "ready":
            continue

        if not e.players:
            continue
        if overview.first is None:
            overview.first = e.ts
        overview.last = e.ts
        overview.entries += 1
        if ev == "chat":
            overview.messages += 1
        elif ev == "command":
            overview.commands += 1

        for name in e.players:
            if selected and name not in selected:
                continue
            s = stats.get(name)
            if s is None:
                s = stats[name] = PlayerStats(name)
            s.events += 1
            if s.first_seen is None:
                s.first_seen = e.ts
            s.last_seen = e.ts
            # Only the acting player gets credit for what they did.
            acting = name == e.player
            if ev == "chat" and acting:
                s.messages += 1
            elif ev == "command" and acting:
                s.commands += 1
                word = e.message.split(None, 1)[0].lower() if e.message else ""
                if word:
                    s.command_counter[word] += 1
            elif ev == "join" and acting:
                s.joins += 1
                if name in open_sessions:  # missing leave line
                    s.sessions.append(Session(open_sessions[name], e.ts, False))
                open_sessions[name] = e.ts
            elif ev in ("leave", "disconnect") and acting:
                began = open_sessions.pop(name, None)
                if began is not None:
                    s.sessions.append(Session(began, e.ts, True))
            elif ev == "death" and acting:
                s.deaths += 1
            elif ev == "advancement" and acting:
                s.advancements += 1
            elif ev == "login" and acting and e.extra:
                s.ips.add(e.extra)
            elif ev == "uuid" and acting and e.extra:
                s.uuids.add(e.extra)

    if open_sessions and last_ts is not None:
        close_all(last_ts, False)

    overview.players = len(stats)
    return stats, overview
