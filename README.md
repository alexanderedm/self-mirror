# SelfMirror · 對鏡問話

> AI plays **you** so you can interview yourself.

SelfMirror is a privacy-first psychological profiling agent built on OpenBiliClaw's soul/memory infrastructure. It scans your local AI tool sessions (DSH, Claude Code, Cursor, Windsurf, Codex) to construct an initial psychological portrait, then enables **mirror dialogue** — a conversational mode where the AI speaks as you, reflecting your patterns back for self-exploration.

## 核心功能

| 功能 | 說明 |
|------|------|
| **🪞 對鏡問話** | AI 扮演你說話，幫你採訪自己的內心 |
| **🔵 隱私開關** | 三級隱私控制：安靜 / 標準 / 深度追蹤 |
| **🔍 Init 掃描** | 讀取本地 AI 工具對話，生成初始畫像 |
| **🧅 洋蔥模型** | 5 層畫像：淺層興趣 → 角色 → 價值觀 → 核心 |
| **📊 引導對話** | AI 主動提問，幫你探索自我 |

## 隱私三級制

- **🔵 安靜（OFF）** — 不收集任何瀏覽數據
- **🟡 標準（STANDARD）** — URL、標題、停留時間、搜尋詞
- **🔴 深度（DEEP）** — 標準 + 活躍視窗標題

## 快速開始

```bash
# 安裝
pip install -e ".[dev]"

# 啟動後端
selfmirror serve-api

# 掃描本地 AI 工具對話並生成初始畫像
selfmirror init

# 開始對鏡對話
selfmirror mirror
```

## API 端點

```
POST /api/mirror/events          # 隱私分類的事件攝入
POST /api/mirror/chat            # 對話（自由 / 引導模式）
GET  /api/mirror/profile         # 畫像摘要
POST /api/mirror/init-scan       # 掃描本地 AI 工具
POST /api/mirror/init-build      # 生成初始畫像
GET  /api/mirror/privacy-status  # 隱私狀態
```

## 與 OpenBiliClaw 的關係

SelfMirror fork 自 [OpenBiliClaw](https://github.com/whiteguo233/OpenBiliClaw) 的 `refactor/self-mirror` 分支，並在 `src/selfmirror/self_mirror/` 下新增了完全獨立的功能模組：

- 所有 OpenBiliClaw 原有功能（內容發現、推薦、對話）保持不變
- SelfMirror 只依賴 `soul/`、`memory/`、`llm/` 三個核心子系統
- 不拉取任何外部平台（YouTube、B站等）的瀏覽歷史

## 許可證

GPL-3.0（與 OpenBiliClaw 相同）
