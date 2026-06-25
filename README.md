# 🤖 AI Developer Agent

Desktop app hỗ trợ lập trình với AI — Electron + React + Python FastAPI.

Thay vì dùng một LLM đơn giản trả lời câu hỏi, AI Developer Agent hoạt động như một **agentic loop**: tự lập kế hoạch, thực thi từng bước, đọc/ghi file trực tiếp vào project, và học hỏi tích lũy từ các lần tương tác trước.

---

## Stack

| Layer | Tech | Ghi chú |
|-------|------|---------|
| Desktop shell | Electron 42 | IPC bridge, filesystem access |
| UI | React 18 + Vite 8 | SPA nhúng trong Electron |
| Code editor | Monaco Editor | Tương tự VS Code |
| State | Zustand | Global store cho messages, file contexts |
| AI backend | Python FastAPI | SSE stream, agentic loop |
| LLM | Groq · `qwen/qwen3-32b` | Planning, execution, extraction |
| Data | JSON files | Experiences store, project context cache |

---

## Kiến trúc

```
┌─────────────────────────────────────────────┐
│                Electron Shell                │
│  ┌─────────────────────────────────────────┐ │
│  │           React Frontend (Vite)          │ │
│  │  ┌──────────┐ ┌────────┐ ┌───────────┐  │ │
│  │  │ ChatPanel│ │ Editor │ │ Experience│  │ │
│  │  │(SSE stream│ │Monaco  │ │  Panel    │  │ │
│  │  │ + plan UI)│ │        │ │(CRUD + AI)│  │ │
│  │  └────┬─────┘ └────────┘ └───────────┘  │ │
│  └───────┼─────────────────────────────────┘ │
└──────────┼──────────────────────────────────┘
           │ HTTP (localhost:8765)
┌──────────▼──────────────────────────────────┐
│           FastAPI Backend (Python)           │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │              AIAgent                  │   │
│  │  PLAN → EXECUTE(steps) → DONE        │   │
│  │  - agentic loop, max 10 bước         │   │
│  │  - đọc/ghi file qua boundary guard   │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌─────────────┐  ┌────────────────────┐    │
│  │ProjectContext│  │  ExperienceStore   │    │
│  │ scan + cache │  │  CRUD + auto-      │    │
│  │ stack detect │  │  extract + inject  │    │
│  └─────────────┘  └────────────────────┘    │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │     Groq API (qwen/qwen3-32b)        │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## Cấu trúc thư mục

```
ai-developer/
├── electron/
│   ├── main.js          # Electron main process, IPC handlers, filesystem bridge
│   └── preload.js       # Context bridge (expose electronAPI ra renderer)
│
├── src/                 # React frontend
│   ├── App.jsx          # Root component, topbar, tab navigation, New Chat
│   ├── main.jsx         # React entry point
│   ├── components/
│   │   ├── ChatPanel.jsx      # Chat UI, SSE consumer, AgentPlan, FileOpsBadge, ExperienceToast
│   │   ├── CodeEditor.jsx     # Monaco editor với tabs, lưu file qua IPC
│   │   ├── Sidebar.jsx        # File explorer, duyệt project, mở file vào editor/context
│   │   ├── AnalyzePanel.jsx   # Phân tích toàn bộ project (bugs / architecture / performance)
│   │   └── ExperiencePanel.jsx# Quản lý kinh nghiệm: CRUD, tìm kiếm, xem chi tiết
│   ├── hooks/
│   │   └── useAgent.js  # Axios client + SSE stream helper cho Python API
│   ├── store/
│   │   └── appStore.js  # Zustand: messages, fileContexts, openFiles, projectPath
│   ├── helpers/
│   │   └── helpers.js   # readTreeRecursive, utils
│   └── styles/
│       └── global.css   # CSS variables (theme, spacing, fonts)
│
├── python/
│   ├── server.py        # FastAPI app, tất cả routes, file ops với boundary guard
│   ├── requirements.txt
│   ├── .env             # GROQ_API_KEY, PORT (gitignored)
│   ├── .env_exemple     # Template cấu hình
│   ├── agent/
│   │   ├── ai_agent.py       # Agentic loop: PLAN → EXECUTE → DONE, path fix, token budget
│   │   ├── project_context.py # Scan project: stack detect, key files, LLM feature description, cache
│   │   ├── experience_store.py# CRUD kinh nghiệm, keyword search, auto-extract qua LLM
│   │   └── code_reader.py    # Đọc project từ filesystem, build file tree, detect languages
│   └── data/
│       ├── experiences.json          # Kho kinh nghiệm tích lũy (tự tạo khi chạy)
│       └── project_context_cache.json # Cache kết quả scan project
│
├── package.json
├── vite.config.js
└── index.html
```

---

## Tính năng

### 💬 Chat với Agentic Loop
- **Lập kế hoạch (PLAN)**: AI phân tích yêu cầu, quyết định `is_complex` và chia thành các bước nếu cần.
- **Thực thi (EXECUTE)**: Với task phức tạp, AI thực thi từng bước, mỗi bước đọc file hiện có trước khi ghi để không ghi đè mất code cũ.
- **Ghi file trực tiếp**: AI tạo/sửa/xóa file trong project — mọi thao tác đều qua **boundary guard** (chặn path traversal, path ngoài project root).
- **Stream real-time**: Frontend nhận SSE events `plan → step_start → step_done → done`, hiển thị tiến trình từng bước.
- **Hủy giữa chừng**: Nút Cancel ngắt stream SSE ngay lập tức.
- **Retry**: Gửi lại tin nhắn nếu AI trả lời sai hoặc lỗi.

### 📚 Experience System (Học tích lũy)
- **Auto-extract**: Sau mỗi response đủ dài, AI tự phân tích cặp (user_message, ai_reply) và lưu các pattern/giải pháp tái dùng được vào kho kinh nghiệm.
- **Inject vào system prompt**: Khi chat, AI tìm kiếm kinh nghiệm liên quan và inject vào context để sinh code nhất quán với quy tắc đã học.
- **CRUD thủ công**: Thêm/sửa/xóa kinh nghiệm qua tab Experience, kèm tìm kiếm keyword và phân loại bằng tags.
- **Toast notification**: Khi AI tự lưu kinh nghiệm mới, hiện toast ở góc phải màn hình.

### 🧠 Project Context
- **Tự động scan**: Detect ngôn ngữ, framework, build tool, database từ cấu trúc project.
- **Feature description**: Dùng LLM đọc README + code để mô tả tính năng chính của project.
- **Cache thông minh**: Hash toàn bộ file (tên + mtime) để invalidate cache khi project thay đổi.
- **Inject vào prompt**: Stack, conventions, key file previews được đưa vào system prompt để AI hiểu context project.

### </> Monaco Editor
- Mở nhiều file dạng tabs.
- Syntax highlighting theo ngôn ngữ.
- Lưu file qua Electron IPC (không cần backend).

### 📊 Analyze Project
- Gửi toàn bộ project (tối đa 30 file) lên AI để phân tích tổng quan.
- Ba focus mode: **Tìm bug**, **Kiến trúc**, **Performance**.

### 📁 File Explorer (Sidebar)
- Duyệt cây thư mục, mở file vào Editor hoặc đính kèm vào Chat context.
- Context chip hiển thị file đang được AI "thấy" khi chat.

---

## Cài đặt & chạy

### Yêu cầu
- Node.js ≥ 18
- Python ≥ 3.11
- Groq API Key (đăng ký miễn phí tại [console.groq.com](https://console.groq.com))

### 1. Cài Node dependencies

```bash
cd E:\Projects\ai-developer
npm install
```

### 2. Cài Python dependencies

```bash
cd python
pip install -r requirements.txt
```

### 3. Cấu hình API key

Tạo file `python/.env` từ template:

```bash
cp python/.env_exemple python/.env
```

Sửa nội dung:

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxx
PORT=8765
```

### 4. Chạy development

**Terminal 1** — Python backend:
```bash
cd python
python server.py
```

**Terminal 2** — Electron + React:
```bash
npm run dev
```

Hoặc dùng script tiện lợi (chạy cả 2 cùng lúc):
```bash
# Xem package.json scripts
npm run python   # chỉ chạy backend
```

### 5. Build production

```bash
npm run build
```

Output: `dist-electron/` (Windows: `.exe`, macOS: `.dmg`, Linux: `.AppImage`)

---

## API Endpoints (Python Backend)

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/health` | Health check, version |
| POST | `/chat` | **SSE stream** — agentic loop, trả về events `plan/step_start/step_done/done/error` |
| POST | `/analyze` | Phân tích toàn bộ project |
| POST | `/write-file` | Ghi file thủ công |
| GET | `/read-project` | Đọc cây thư mục + nội dung file |
| POST | `/project-context/scan` | Scan + cache project context |
| POST | `/project-context/invalidate` | Xóa cache để force re-scan |
| GET | `/experiences` | Lấy/tìm kiếm kinh nghiệm (`?q=keyword&tag=tag`) |
| POST | `/experiences` | Thêm kinh nghiệm mới |
| GET | `/experiences/{id}` | Lấy chi tiết |
| PUT | `/experiences/{id}` | Cập nhật |
| DELETE | `/experiences/{id}` | Xóa |
| POST | `/experiences/auto-extract` | Tự động trích xuất kinh nghiệm từ cặp message/reply |

---

## Bảo mật

- **Boundary guard**: Mọi thao tác ghi/xóa file đều kiểm tra path có nằm trong `project_path` không — ngăn path traversal (`../../etc`) và absolute path escape.
- API key (`GROQ_API_KEY`) lưu trong `.env`, không commit lên git.
- Backend bind `127.0.0.1` (localhost only), không expose ra mạng.

---

## Biến môi trường

| Biến | Mô tả | Ví dụ |
|------|-------|-------|
| `GROQ_API_KEY` | API key từ Groq Console | `gsk_xxx...` |
| `PORT` | Port cho FastAPI backend | `8765` |
