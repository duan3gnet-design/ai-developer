"""
AI Developer Agent — Python Backend (FastAPI)
Chạy trên port 8765, nhận request từ Electron renderer qua axios
"""

import os
import json
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


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "agent": "AI Developer v1.0"}


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Chat với AI — tự động ghi file nếu AI quyết định cần thiết.
    Response: { reply, files_written: [{ path, action, success, error? }] }
    """
    try:
        result = await ai_agent.chat(
            message=req.message,
            file_contexts=req.file_contexts,
            history=req.conversation_history,
            project_path=req.project_path
        )

        reply = result.get("reply", "")
        files_to_write = result.get("files_to_write", [])
        files_written = []

        # Ghi từng file AI yêu cầu
        for f in files_to_write:
            file_path = f.get("path", "").strip()
            content = f.get("content", "")
            action = f.get("action", "create")

            if not file_path or not content:
                files_written.append({"path": file_path, "action": action, "success": False, "error": "Thiếu path hoặc content"})
                continue

            try:
                path_obj = Path(file_path)
                path_obj.parent.mkdir(parents=True, exist_ok=True)
                path_obj.write_text(content, encoding="utf-8")
                files_written.append({"path": file_path, "action": action, "success": True})
                print(f"[Agent] {'✓ Wrote' if action == 'create' else '✓ Updated'}: {file_path}")
            except Exception as e:
                files_written.append({"path": file_path, "action": action, "success": False, "error": str(e)})
                print(f"[Agent] ✗ Failed to write {file_path}: {e}")

        return {"reply": reply, "files_written": files_written}

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
        path = Path(req.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(req.content, encoding="utf-8")
        return {"success": True, "path": str(path)}
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
