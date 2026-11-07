"""Minecraft log parser.

Understands vanilla, Spigot, Paper, Purpur, Forge and Fabric style logs, both
plain ``.log``/``.txt`` files and gzip compressed ``.log.gz`` archives.

Every log line is classified into one of three parts (server, command, chat)
and tagged with the players it concerns, which powers player filtering.
"""
from __future__ import annotations

import gzip
import io
import os
import re
from datetime import date, datetime, timedelta
from typing import Callable, Iterable, Optional

from .models import (CAT_CHAT, CAT_COMMAND, CAT_SERVER, NO_PLAYERS, Entry,
                     ParsedLog)

# --------------------------------------------------------------------------
# Regular expressions
# --------------------------------------------------------------------------
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\u00a7[0-9a-fk-orA-FK-OR]")

# [12:34:56] [Server thread/INFO]: message     (vanilla, Paper, Forge, Fabric)
RE_MODERN = re.compile(
    r"^\[(?:(\d{4}-\d{2}-\d{2}|\d{1,2}[A-Za-z]{3}\d{4}) )?"
    r"(\d{2}):(\d{2}):(\d{2})(?:[.,]\d+)?\] "
    r"\[([^\]/]+)/([A-Za-z]+)\](?: \[[^\]]*\])?:? ?(.*)$"
)
# [12:34:56 INFO]: message                     (older Spigot / Bukkit)
RE_LEGACY = re.compile(
    r"^\[(\d{2}):(\d{2}):(\d{2})(?:[.,]\d+)? ([A-Za-z]+)\]:? ?(.*)$"
)
# 2024-05-12 12:34:56 [INFO] message           (very old Bukkit / Beta)
RE_DATED = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}):(\d{2})(?:[.,]\d+)? "
    r"\[([A-Za-z]+)\]:? ?(.*)$"
)

NAME = r"[A-Za-z0-9_.]{2,32}"
CHAT_RE = re.compile(r"^(?:\[Not Secure\] )?<([^<>]{1,48})> (.*)$")
SERVERSAY_RE = re.compile(r"^\[(Server|Rcon)\] (.*)$")
CMD_RE = re.compile(r"^(\S{1,40}) issued server command: (.*)$")
FEEDBACK_RE = re.compile(r"^\[(" + NAME + r"|@): (.*)\]$")
JOIN_RE = re.compile(r"^(" + NAME + r") joined the game$")
LEAVE_RE = re.compile(r"^(" + NAME + r") left the game$")
LOGIN_RE = re.compile(
    r"^(" + NAME + r")\[/?([^\]]*)\] logged in with entity id \d+ at "
)
LOST_RE = re.compile(r"^(" + NAME + r") lost connection: (.*)$")
UUID_RE = re.compile(r"^UUID of player (" + NAME + r") is ([0-9a-fA-F-]{32,36})$")
ADV_RE = re.compile(
    r"^(" + NAME + r") has (?:made the advancement|completed the challenge|"
    r"reached the goal) \[.*\]$"
)
DEATH_RE = re.compile(
    r"^(" + NAME + r") (?:was (?:slain|shot|killed|blown|pricked|squashed|"
    r"squished|impaled|fireballed|pummeled|doomed|struck|burnt|skewered|"
    r"stung|poked|obliterated|speared|lanced|roasted|set on fire|knocked)|"
    r"fell|drowned|burned|blew|hit|died|starved|suffocated|tried|withered|"
    r"went|walked|experienced|froze|discovered|didn't|left|got)"
    r"(?=\s|$)"
)
TOKEN_RE = re.compile(r"[A-Za-z0-9_.]{2,32}")
PLAYER_NAME_RE = re.compile(r"^\.?[A-Za-z0-9_]{2,16}$")
NAME_TOKEN_RE = re.compile(r"[A-Za-z0-9_.]+")
FILE_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

NON_PLAYERS = {"server", "rcon", "console", "minecraft", "@"}
LEVEL_MAP = {"WARNING": "WARN", "SEVERE": "ERROR", "FATAL": "ERROR",
             "CRITICAL": "ERROR", "ERR": "ERROR"}

ProgressCb = Callable[[float], None]


class Cancelled(Exception):
    """Raised when the user cancels an import."""


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def is_player(name: str) -> bool:
    return bool(name) and name.lower() not in NON_PLAYERS and \
        bool(PLAYER_NAME_RE.match(name))


def clean_name(raw: str) -> str:
    """Reduce '[Admin] ~Steve' or 'Steve' to the bare player name."""
    tokens = NAME_TOKEN_RE.findall(raw)
    return tokens[-1] if tokens else raw.strip()


def _parse_explicit_date(text: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%d%b%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def base_date_for(path: str) -> tuple:
    """Date a log file belongs to.

    Returns (date, from_mtime). Archived logs usually contain the date in
    their file name (2024-05-12-1.log.gz); latest.log does not, so the file's
    modification time is used instead.
    """
    m = FILE_DATE_RE.search(os.path.basename(path))
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3])), False
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(os.path.getmtime(path)).date(), True
    except OSError:
        return date.today(), True


def classify(msg: str, level: str) -> tuple:
    """Classify a message.

    Returns (category, event, player, extra, text) where ``text`` is the
    message to display (e.g. the chat text without the ``<name>`` prefix).
    """
    m = CHAT_RE.match(msg)
    if m:
        return CAT_CHAT, "chat", clean_name(m[1]), "", m[2]

    m = SERVERSAY_RE.match(msg)
    if m:
        return CAT_CHAT, "chat", m[1], "", m[2]

    m = CMD_RE.match(msg)
    if m:
        cmd = m[2].strip()
        if not cmd.startswith("/"):
            cmd = "/" + cmd
        return CAT_COMMAND, "command", clean_name(m[1]), "", cmd

    if level == "INFO":
        m = FEEDBACK_RE.match(msg)
        if m:
            who = "" if m[1] == "@" else m[1]
            return CAT_COMMAND, "feedback", who, "", m[2]

    m = JOIN_RE.match(msg)
    if m:
        return CAT_SERVER, "join", m[1], "", msg
    m = LEAVE_RE.match(msg)
    if m:
        return CAT_SERVER, "leave", m[1], "", msg
    m = LOGIN_RE.match(msg)
    if m:
        ip = m[2]
        if ip.count(":") == 1 or (ip.count(".") == 3 and ":" in ip):
            ip = ip.rsplit(":", 1)[0]
        elif ":" in ip and ip.rsplit(":", 1)[1].isdigit() and ip.count(":") > 1:
            ip = ip.rsplit(":", 1)[0]
        return CAT_SERVER, "login", m[1], ip, msg
    m = LOST_RE.match(msg)
    if m:
        return CAT_SERVER, "disconnect", m[1], "", msg
    m = UUID_RE.match(msg)
    if m:
        return CAT_SERVER, "uuid", m[1], m[2].lower(), msg
    m = ADV_RE.match(msg)
    if m:
        return CAT_SERVER, "advancement", m[1], "", msg
    m = DEATH_RE.match(msg)
    if m:
        return CAT_SERVER, "death", m[1], "", msg

    if msg.startswith("Starting minecraft server version"):
        return CAT_SERVER, "start", "", "", msg
    if msg.startswith("Done (") and "For help" in msg:
        return CAT_SERVER, "ready", "", "", msg
    if msg.startswith("Stopping server") or msg.startswith("Stopping the server"):
        return CAT_SERVER, "stop", "", "", msg

    if level == "WARN":
        return CAT_SERVER, "warning", "", "", msg
    if level == "ERROR":
        return CAT_SERVER, "error", "", "", msg
    return CAT_SERVER, "info", "", "", msg


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
def parse_lines(lines: Iterable, base_date: date, from_mtime: bool = False,
                progress: Optional[Callable[[], None]] = None,
                cancel: Optional[Callable[[], bool]] = None) -> ParsedLog:
    """Parse an iterable of text lines into a ParsedLog."""
    entries: list = []
    day = base_date
    prev_secs: Optional[int] = None
    rollovers = 0
    used_explicit = False
    line_no = 0
    last: Optional[Entry] = None

    for raw in lines:
        line_no += 1
        if progress is not None and line_no % 5000 == 0:
            progress()
            if cancel is not None and cancel():
                raise Cancelled()

        line = ANSI_RE.sub("", raw.rstrip("\r\n"))
        if not line.strip():
            continue

        hit = None
        c0 = line[0]
        if c0 == "[":
            m = RE_MODERN.match(line)
            if m:
                hit = (m[1], m[2], m[3], m[4], m[5], m[6], m[7])
            else:
                m = RE_LEGACY.match(line)
                if m:
                    hit = (None, m[1], m[2], m[3], "", m[4], m[5])
        elif c0.isdigit():
            m = RE_DATED.match(line)
            if m:
                hit = (m[1], m[2], m[3], m[4], "", m[5], m[6])

        if hit is None:
            # Continuation line (stack trace, multi-line message ...)
            if last is not None:
                last.message += "\n" + line
            continue

        dtext, hh, mm, ss, thread, level, msg = hit
        hh, mm, ss = int(hh), int(mm), int(ss)
        secs = hh * 3600 + mm * 60 + ss
        explicit = _parse_explicit_date(dtext) if dtext else None
        if explicit is not None:
            day = explicit
            prev_secs = None
            used_explicit = True
        elif prev_secs is not None and secs < prev_secs - 6 * 3600:
            day += timedelta(days=1)
            rollovers += 1
        prev_secs = secs
        try:
            ts = datetime(day.year, day.month, day.day, hh, mm, ss)
        except ValueError:
            continue

        level = level.upper()
        level = LEVEL_MAP.get(level, level)
        category, event, player, extra, text = classify(msg, level)
        players = (player,) if player and is_player(player) else NO_PLAYERS
        last = Entry(ts=ts, category=category, event=event, level=level,
                     thread=thread, player=player, players=players,
                     message=text, extra=extra, line_no=line_no)
        entries.append(last)

    # latest.log has no date in its name: the modification date is the *end*
    # of the log, so walk back over any midnight rollovers we detected.
    if from_mtime and not used_explicit and rollovers:
        shift = timedelta(days=rollovers)
        for e in entries:
            e.ts -= shift

    _tag_mentions(entries)

    result = ParsedLog(entries=entries, line_count=line_no)
    if entries:
        result.first_ts = entries[0].ts.isoformat(sep=" ")
        result.last_ts = entries[-1].ts.isoformat(sep=" ")
        result.log_date = entries[0].ts.strftime("%Y-%m-%d")
    return result


def _tag_mentions(entries: list) -> None:
    """Automatic player detection, second pass.

    Players are first discovered from chat, commands, joins, deaths ... Server
    lines that merely mention one of those names ("Steve moved too quickly!",
    "Steve was slain by Alex") are then attributed to them as well, so a player
    filter really shows *everything* that concerns that player.
    """
    known = set()
    for e in entries:
        if e.players:
            known.update(e.players)
    if not known:
        return
    for e in entries:
        if e.category != CAT_SERVER or e.event in ("start", "ready", "stop"):
            continue
        found = [t for t in dict.fromkeys(TOKEN_RE.findall(e.message))
                 if t in known]
        if not found:
            continue
        if e.player and e.players and e.players[0] in found:
            found.remove(e.players[0])
            found.insert(0, e.players[0])
        e.players = tuple(found)
        if not e.player:
            e.player = found[0]


def open_text_stream(path: str):
    """Open a .log/.txt/.gz file as text. Returns (text_stream, raw_file).

    gzip is detected from the file header, not just the extension.
    """
    raw = open(path, "rb")
    magic = raw.read(2)
    raw.seek(0)
    stream = gzip.GzipFile(fileobj=raw) if magic == b"\x1f\x8b" else raw
    return io.TextIOWrapper(stream, encoding="utf-8", errors="replace",
                            newline=None), raw


def parse_file(path: str, progress: Optional[ProgressCb] = None,
               cancel: Optional[Callable[[], bool]] = None) -> ParsedLog:
    """Parse a log file from disk. ``progress`` receives 0.0 .. 1.0."""
    base, from_mtime = base_date_for(path)
    size = max(os.path.getsize(path), 1)
    text, raw = open_text_stream(path)
    try:
        def tick() -> None:
            if progress is not None:
                progress(min(raw.tell() / size, 1.0))

        result = parse_lines(text, base, from_mtime, tick, cancel)
    finally:
        text.close()
        raw.close()
    if progress is not None:
        progress(1.0)
    return result
