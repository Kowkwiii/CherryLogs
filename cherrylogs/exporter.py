"""Export entries and statistics as TXT or CSV."""
from __future__ import annotations

import csv
from datetime import datetime

from . import __app_name__, __version__
from .models import CAT_CHAT, CAT_COMMAND, EVENT_LABELS
from .stats import format_duration

TS_FMT = "%Y-%m-%d %H:%M:%S"


def entry_line(e) -> str:
    """Render an entry as a readable single log line."""
    ts = e.ts.strftime(TS_FMT)
    if e.category == CAT_CHAT:
        return f"[{ts}] <{e.player or '?'}> {e.message}"
    if e.category == CAT_COMMAND:
        if e.event == "feedback":
            return f"[{ts}] [{e.player or 'Server'}: {e.message}]"
        return f"[{ts}] {e.player or '?'} issued command: {e.message}"
    src = f"{e.thread}/{e.level}" if e.thread else e.level
    return f"[{ts}] [{src}]: {e.message}"


def export_txt(path: str, entries: list, title: str, filters: str,
               sources: dict) -> None:
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(f"{__app_name__} {__version__} - {title}\n")
        f.write(f"Exported: {datetime.now().strftime(TS_FMT)}\n")
        f.write(f"Entries:  {len(entries):,}\n")
        f.write(f"Filters:  {filters}\n")
        if sources:
            f.write("Sources:  " + ", ".join(sorted(set(sources.values()))) + "\n")
        f.write("=" * 78 + "\n")
        for e in entries:
            f.write(entry_line(e) + "\n")


def export_csv(path: str, entries: list, sources: dict) -> None:
    # utf-8-sig so Excel opens non-ASCII player names / chat correctly.
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "part", "event", "level", "thread", "player",
                    "involved_players", "message", "source_file", "line"])
        for e in entries:
            w.writerow([e.ts.strftime(TS_FMT), e.category,
                        EVENT_LABELS.get(e.event, e.event), e.level, e.thread,
                        e.player, ", ".join(e.players), e.message,
                        sources.get(e.import_id, ""), e.line_no])


def export_stats_csv(path: str, stats: dict) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["player", "events", "messages", "commands", "joins",
                    "deaths", "advancements", "sessions", "playtime_seconds",
                    "playtime", "first_seen", "last_seen", "top_command",
                    "ip_addresses", "uuids"])
        for s in sorted(stats.values(), key=lambda s: -s.events):
            w.writerow([
                s.name, s.events, s.messages, s.commands, s.joins, s.deaths,
                s.advancements, len(s.sessions), int(s.playtime),
                format_duration(s.playtime),
                s.first_seen.strftime(TS_FMT) if s.first_seen else "",
                s.last_seen.strftime(TS_FMT) if s.last_seen else "",
                s.top_command, "; ".join(sorted(s.ips)),
                "; ".join(sorted(s.uuids))])
