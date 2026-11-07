# 🌸 CherryLogs

A cherry blossom themed Windows 11 app that loads Minecraft server logs
(`.log`, `.txt`, `.gz`) and splits them into **Server Logs**, **Commands** and
**Chat**, so you can investigate what any player (or several players) did.

## Run it

1. Install Python 3.10+ from python.org (tick "Add python.exe to PATH").
2. Double-click **run.bat**. The first run creates a virtual environment and
   installs PySide6; after that it just starts the app.

Or manually: `pip install -r requirements.txt` then `python main.py`.

To build a standalone `CherryLogs.exe`: double-click **build_exe.bat**
(output: `dist\CherryLogs.exe`).

## Using it

- **Drag and drop** files (or whole folders) onto the window, or press
  *Import logs…* (Ctrl+O). Supported: `latest.log`, `debug.log`, `*.log.gz`.
- **Players** tab: players are detected automatically. Tick one or more to
  investigate them. Right-click any row → *Investigate <player>*.
- **History** tab: every import is saved to a local database. Tick several
  logs to investigate multiple days together; select + Delete to remove.
- **Filters**: text search, log level, time range, and "only events involving
  every selected player" (interactions such as kills).
- **Tabs**: Server Logs · Commands · Chat · All Activity (everything a player
  did, in order) · Timeline · Statistics.
- **Export** (Ctrl+E): current tab / all filtered activity as TXT or CSV, and
  player statistics as CSV.
- **Dark / light** mode: Ctrl+D (remembered between runs).

Data is stored in `%APPDATA%\CherryLogs\cherrylogs.db`.

if you want you can add more stuff to it.
