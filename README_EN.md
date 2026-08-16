# SelfMirror · Mirror Dialogue

> AI plays **you** so you can interview yourself.

SelfMirror is a privacy-first psychological profiling fork of [OpenBiliClaw](https://github.com/whiteguo233/OpenBiliClaw), created by [whiteguo233](https://github.com/whiteguo233). It reuses OpenBiliClaw's soul/memory infrastructure to build a personal psychological portrait, then enables **mirror dialogue** — a conversational mode where the AI speaks as you, reflecting your patterns back for genuine self-exploration.

This project would not exist without the foundational work of the OpenBiliClaw author, who generously shares this codebase with the community. All original OpenBiliClaw capabilities remain intact in this fork.

## Core Features

| Feature | Description |
|---------|-------------|
| **🪞 Mirror Dialogue** | AI speaks as you, mirroring your patterns for self-interview |
| **🔵 Privacy Tiers** | Three-level control: Quiet / Standard / Deep tracking |
| **🔍 Init Scan** | Reads local AI tool sessions to bootstrap a psychological portrait |
| **🧅 Onion Model** | 5-layer profile: surface interests → persona → values → core self |
| **📊 Guided Dialogue** | AI asks exploratory questions to deepen self-understanding |

## Privacy Tiers

- **🔵 Quiet (OFF)** — No browsing data collected at all
- **🟡 Standard (STANDARD)** — URL, title, dwell time, search terms
- **🔴 Deep (DEEP)** — Standard + active window title

## Quick Start

```bash
# Install
pip install -e ".[dev]"          # Python 3.11+

# Start API server (port 8400, avoids conflict with OpenBiliClaw on 8420)
python serve-mirror.py

# Or use the CLI entry point (requires full OpenBiliClaw deps)
selfmirror serve-api
```

Then load the browser extension:
1. Open `chrome://extensions/`
2. Enable **Developer mode**
3. Click **Load unpacked** → select `extension/dist/`
4. Click the extension icon to open the side panel

## API Endpoints

```
POST /api/mirror/events           Privacy-tiered event ingestion
POST /api/mirror/chat            Mirror dialogue (free / guided mode)
GET  /api/mirror/profile         Profile summary
POST /api/mirror/init-scan       Scan local AI tool sessions
POST /api/mirror/init-build      Generate initial psychological portrait
GET  /api/mirror/privacy-status  Current privacy tier status
GET  /api/mirror/privacy-tier    Get / set current tier
GET  /api/mirror/guided-starter  Get guided dialogue opening question
```

## Architecture

SelfMirror lives entirely within `src/selfmirror/`:

```
src/selfmirror/
├── self_mirror/
│   ├── router.py     ← FastAPI routes for all /api/mirror/* endpoints
│   └── models.py     ← Pydantic models (PrivacyTier, MirrorMode, etc.)
├── soul/
│   ├── init_scanner.py    ← Scans local AI tool session directories
│   └── mirror_dialogue.py ← FREE / GUIDED dialogue logic
└── cli.py           ← CLI entry point (selfmirror serve-api, etc.)
```

The browser extension (`extension/`) communicates only with `/api/mirror/*` and does not touch OpenBiliClaw's content-discovery or recommendation engine.

## Local AI Session Sources

Init scan reads from these directories (when present):

| Tool | Path |
|------|------|
| DeepSeek Harness (DSH) | `~/.dsh/sessions/` |
| Claude Code | `~/.claude/` |
| Cursor Chat | `~/.cursor chat/` |
| Windsurf | `~/.windsurf/` |
| Codex | `~/.codex/` |

## Relationship with OpenBiliClaw

SelfMirror is a **direct fork** of [OpenBiliClaw](https://github.com/whiteguo233/OpenBiliClaw). The original project is the work of a single developer who chose to share it openly with the community — that generosity made this fork possible.

- All original OpenBiliClaw functionality remains unchanged
- SelfMirror only depends on the `soul/`, `memory/`, and `llm/` subsystems
- No external platform browsing history is pulled (YouTube, Bilibili, etc.)
- Both packages can coexist on the same machine (`openbiliclaw` on 8420, `selfmirror` on 8400)

## License

GPL-3.0 (same as OpenBiliClaw)
