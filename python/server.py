"""
AI Developer Agent — Python Backend (FastAPI)
Chạy trên port 8765, nhận request từ Electron renderer qua axios
"""

import os
import shutil
from pathlib import Path
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.code_reader import CodeReader
from agent.ai_agent import AIAgent

app = FastAPI(title="AI Developer Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

code_reader = CodeReader()
ai_agent = AIAgent()


# ─── Models ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    file_contexts: List[dict] = []
    conversation_history: List[dict] = []
    project_path: Optional[str] = None

class AnalyzeRequest(BaseModel):
    project_path: str
    focus: Optional[str] = None

class WriteFileRequest(BaseModel):
    path: str
    content: str


# ─── Helpers ─────────────────────────────────────────────────────────────────

def delete_path(raw_path: str) -> dict:
    """Xóa file hoặc thư mục, trả về kết quả."""
    p = Path(raw_path.strip())
    if not p.exists():
        return {"path": str(p), "success": False, "error": "Không tìm thấy"}
    try:
        if p.is_dir():
            shutil.rmtree(p)
            print(f"[Agent] 🗑 Deleted dir : {p}")
        else:
            p.unlink()
            print(f"[Agent] 🗑 Deleted file: {p}")
        return {"path": str(p), "success": True}
    except Exception as e:
        print(f"[Agent] ✗ Failed to delete {p}: {e}")
        return {"path": str(p), "success": False, "error": str(e)}


def write_path(file_path: str, content: str) -> dict:
    """Ghi nội dung vào file, tự phát hiện create/update."""
    p = Path(file_path.strip())
    actual_action = "update" if p.exists() else "create"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print(f"[Agent] ✓ {'Updated' if actual_action == 'update' else 'Created'}: {p}")
        return {"path": str(p), "action": actual_action, "success": True}
    except Exception as e:
        print(f"[Agent] ✗ Failed to write {p}: {e}")
        return {"path": str(p), "action": actual_action, "success": False, "error": str(e)}


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "agent": "AI Developer v1.0"}


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Chat với AI — tự động ghi/xóa file nếu AI quyết định cần thiết.
    Thứ tự: xóa file cũ trước → ghi file mới sau (đúng với rename/move).
    Response: { reply, files_written, files_deleted }
    """
    try:
        result = await ai_agent.chat(
            message=req.message,
            file_contexts=req.file_contexts,
            history=req.conversation_history,
            project_path=req.project_path
        )

        reply         = result.get("reply", "")
        files_to_write  = result.get("files_to_write", [])
        files_to_delete = result.get("files_to_delete", [])

        # 1️⃣ Xóa trước — để tránh conflict khi đổi tên thư mục
        files_deleted = [delete_path(p) for p in files_to_delete if p]

        # 2️⃣ Ghi sau
        files_written = []
        for f in files_to_write:
            file_path = f.get("path", "").strip()
            content   = f.get("content", "")
            if not file_path or content is None:
                files_written.append({"path": file_path, "action": "unknown", "success": False, "error": "Thiếu path hoặc content"})
                continue
            files_written.append(write_path(file_path, content))

        return {"reply": reply, "files_written": files_written, "files_deleted": files_deleted}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze")
async def analyze_project(req: AnalyzeRequest):
    try:
        project_summary = code_reader.summarize_project(req.project_path)
        analysis = await ai_agent.analyze_project(
            summary=project_summary,
            focus=req.focus
        )
        return {"analysis": analysis, "summary": project_summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/write-file")
async def write_file(req: WriteFileRequest):
    try:
        result = write_path(req.path, req.content)
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error"))
        return {"success": True, "path": result["path"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/read-project")
async def read_project(path: str, max_files: int = 50):
    try:
        result = code_reader.read_project(path, max_files=max_files)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print(f"[AI Developer Agent] Starting on http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
