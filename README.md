# AI Developer Agent

Desktop app hỗ trợ lập trình với AI — Electron + React + Python FastAPI.

## Stack

| Layer | Tech |
|-------|------|
| Desktop shell | Electron 31 |
| UI | React 18 + Vite |
| Code editor | Monaco Editor |
| State | Zustand |
| AI backend | Python FastAPI |
| AI model | Claude Sonnet (Anthropic) |

## Cấu trúc

```
ai-developer/
├── electron/
│   ├── main.js          # Electron main process, IPC handlers, filesystem bridge
│   └── preload.js       # Context bridge (expose electronAPI)
├── src/
│   ├── App.jsx           # Root component, layout, tab navigation
│   ├── main.jsx          # React entry
│   ├── components/
│   │   ├── Sidebar.jsx   # File tree, project explorer
│   │   ├── ChatPanel.jsx # AI chat interface
│   │   ├── CodeEditor.jsx# Monaco editor với tabs
│   │   └── AnalyzePanel.jsx # Project analyzer
│   ├── store/
│   │   └── appStore.js   # Zustand global store
│   ├── hooks/
│   │   └── useAgent.js   # Axios client cho Python API
│   └── styles/
│       └── global.css
├── python/
│   ├── server.py         # FastAPI app, routes
│   ├── requirements.txt
│   ├── .env              # ANTHROPIC_API_KEY
│   └── agent/
│       ├── ai_agent.py   # Claude API calls, prompt engineering
│       └── code_reader.py# Filesystem reader, project parser
├── package.json
├── vite.config.js
└── index.html
```

## Cài đặt & chạy

### 1. Cài dependencies Node.js

```bash
cd E:\Projects\ai-developer
npm install
```

### 2. Cài dependencies Python

```bash
cd python
pip install -r requirements.txt
```

### 3. Cấu hình API key

Sửa `python/.env`:

```
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### 4. Chạy development

Terminal 1 — Python backend:
```bash
cd python
python server.py
```

Terminal 2 — Electron + React:
```bash
npm run dev
```

## Tính năng

- **💬 Chat** — Hỏi AI về code với context file được chọn
- **</> Editor** — Monaco editor đầy đủ, lưu file qua Electron IPC
- **📊 Analyze** — Phân tích toàn bộ project (bug / architecture / performance)
- **📁 Explorer** — Duyệt filesystem, mở file vào editor & chat context
- **Quick actions** — Phân tích, tìm bug, tạo test chỉ 1 click
