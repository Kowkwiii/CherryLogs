"""Filtering of entries by player, text, level and time range."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .models import CAT_CHAT, CAT_COMMAND, CAT_SERVER


@dataclass
class Filters:
    players: frozenset = field(default_factory=frozenset)
    interactions_only: bool = False   # entries involving *every* chosen player
    text: str = ""
    level: str = "All"
    start: Optional[datetime] = None
    end: Optional[datetime] = None

    def describe(self) -> str:
        parts = []
        if self.players:
            mode = "all of" if self.interactions_only else "any of"
            parts.append(f"players ({mode}): " + ", ".join(sorted(self.players)))
        if self.text:
            parts.append(f'text contains "{self.text}"')
        if self.level != "All":
            parts.append(f"level {self.level}")
        if self.start:
            parts.append("from " + self.start.strftime("%Y-%m-%d %H:%M:%S"))
        if self.end:
            parts.append("to " + self.end.strftime("%Y-%m-%d %H:%M:%S"))
        return "; ".join(parts) if parts else "none"


@dataclass
class FilterResult:
    """Outcome of running the filter pipeline."""

    base: list        # after player + time filters (used for stats/timeline)
    everything: list  # after all filters
    server: list
    command: list
    chat: list


def apply_filters(entries: list, f: Filters) -> FilterResult:
    cur = entries

    if f.players:
        chosen = f.players
        if f.interactions_only and len(chosen) > 1:
            cur = [e for e in cur if chosen.issubset(e.players)]
        else:
            cur = [e for e in cur if not chosen.isdisjoint(e.players)]

    if f.start is not None:
        start = f.start
        cur = [e for e in cur if e.ts >= start]
    if f.end is not None:
        end = f.end
        cur = [e for e in cur if e.ts <= end]

    base = cur

    if f.level != "All":
        level = f.level
        cur = [e for e in cur if e.level == level]

    if f.text:
        needle = f.text.lower()
        cur = [e for e in cur
               if needle in e.message.lower() or needle in e.player.lower()]

    server, command, chat = [], [], []
    for e in cur:
        cat = e.category
        if cat == CAT_SERVER:
            server.append(e)
        elif cat == CAT_COMMAND:
            command.append(e)
        elif cat == CAT_CHAT:
            chat.append(e)
    return FilterResult(base, cur, server, command, chat)
