"""
AI Developer Agent — Python Backend (FastAPI)
/chat dùng SSE để stream agentic loop events về frontend.
Mọi thao tác ghi/xóa đều bị giới hạn trong project folder.
"""

import os
import json
import shutil
from pathlib import Path
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.code_reader import CodeReader, IGNORE_DIRS
from agent.ai_agent import AIAgent

app = FastAPI(title="AI Developer Agent", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

code_reader = CodeReader()
ai_agent    = AIAgent()


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
    project_path: Optional[str] = None


# ─── Path helpers ─────────────────────────────────────────────────────────────

def normalize(p: str) -> str:
    """Chuẩn hóa separator theo OS."""
    return str(Path(p.strip().replace("/", os.sep).replace("\\", os.sep)))


def assert_within_project(path: Path, project_path: str) -> None:
    """
    Raise ValueError nếu path nằm ngoài project_path.
    Dùng Path.resolve() để chặn:
      - Path traversal: ../../etc/passwd
      - Absolute path escape: C:\\Windows\\System32
      - Symlink escape
    """
    proj_root = Path(project_path).resolve()
    try:
        path.resolve().relative_to(proj_root)
    except ValueError:
        raise ValueError(
            f"🚫 Từ chối thao tác ngoài project: '{path}' không thuộc '{proj_root}'"
        )


def resolve_path(raw: str, project_path: Optional[str] = None) -> Optional[Path]:
    """
    Tìm path thực tế từ string AI trả về.
    Thứ tự: exact → normalize sep → relative → fuzzy filename.
    """
    # 1. Exact
    for candidate in [Path(raw.strip()), Path(normalize(raw))]:
        if candidate.exists():
            return candidate

    if not project_path:
        print(f"[Resolve] ✗ not found: '{raw}'")
        return None

    proj = Path(project_path)

    # 2. Relative fallback
    c = proj / raw.strip().lstrip("/\\")
    if c.exists():
        return c
    try:
        rel = Path(raw.strip()).relative_to(proj)
        if (proj / rel).exists():
            return proj / rel
    except ValueError:
        pass

    # 3. Fuzzy: tìm theo tên file trong project tree
    name = Path(raw.strip()).name
    if name:
        for found in proj.rglob(name):
            if not any(ig in found.parts for ig in IGNORE_DIRS):
                print(f"[Resolve] fuzzy: '{raw}' → '{found}'")
                return found

    print(f"[Resolve] ✗ not found: '{raw}'")
    return None


# ─── File operations ──────────────────────────────────────────────────────────

def delete_path(raw: str, project_path: Optional[str] = None) -> dict:
    resolved = resolve_path(raw, project_path)
    if not resolved:
        return {"path": raw, "success": False, "error": f"Không tìm thấy: '{raw}'"}

    # ── BOUNDARY GUARD ────────────────────────────────────────────────────────
    if project_path:
        try:
            assert_within_project(resolved, project_path)
        except ValueError as e:
            print(f"[Guard] BLOCKED delete: {e}")
            return {"path": str(resolved), "success": False, "error": str(e)}

    try:
        if resolved.is_dir():
            shutil.rmtree(resolved)
        else:
            resolved.unlink()
        print(f"[Agent] 🗑 Deleted: {resolved}")
        return {"path": str(resolved), "success": True}
    except Exception as e:
        return {"path": str(resolved), "success": False, "error": str(e)}


def write_file_op(file_path: str, content: str,
                  project_path: Optional[str] = None) -> dict:    
    if file_path and not file_path.startswith(project_path): 
        file_path = project_path + "\\" + file_path
    p      = Path(normalize(file_path))
    action = "update" if p.exists() else "create"

    # ── BOUNDARY GUARD ────────────────────────────────────────────────────────
    if project_path:
        try:
            # Tạo parent trước để resolve() hoạt động với path mới
            p.parent.mkdir(parents=True, exist_ok=True)
            assert_within_project(p, project_path)
        except ValueError as e:
            print(f"[Guard] BLOCKED write: {e}")
            return {"path": str(p), "action": action, "success": False, "error": str(e)}

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print(f"[Agent] ✓ {action}: {p}")
        return {"path": str(p), "action": action, "success": True}
    except Exception as e:
        return {"path": str(p), "action": action, "success": False, "error": str(e)}


def apply_file_ops(files_to_write: list, files_to_delete: list,
                   project_path: Optional[str]) -> tuple[list, list]:
    """Xóa trước → ghi sau. Mọi op đều qua boundary guard."""
    deleted = [delete_path(p, project_path) for p in files_to_delete if p]
    written = []
    for f in files_to_write:
        fp      = f.get("path", "").strip()
        content = f.get("content", "")
        if not fp or content is None:
            written.append({"path": fp, "action": "unknown", "success": False,
                            "error": "Thiếu path/content"})
        else:
            written.append(write_file_op(fp, content, project_path))
    return written, deleted


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/chat")
async def chat(req: ChatRequest):
    """Stream SSE — event types: plan | step_start | step_done | done | error"""
    async def event_stream():
        try:
            async for event in ai_agent.chat_stream(
                message       = req.message,
                file_contexts = req.file_contexts,
                history       = req.conversation_history,
                project_path  = req.project_path,
            ):
                etype = event["type"]
                data  = event["data"]

                if etype in ("step_done", "done"):
                    written, deleted = apply_file_ops(
                        data.pop("files_to_write",  []),
                        data.pop("files_to_delete", []),
                        req.project_path,
                    )
                    data["files_written"] = written
                    data["files_deleted"] = deleted

                yield f"data: {json.dumps({'type': etype, 'data': data}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type':'error','data':{'message':str(e)}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.post("/analyze")
async def analyze_project(req: AnalyzeRequest):
    try:
        summary  = code_reader.summarize_project(req.project_path)
        analysis = await ai_agent.analyze_project(summary=summary, focus=req.focus)
        return {"analysis": analysis, "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/write-file")
async def write_file(req: WriteFileRequest):
    result = write_file_op(req.path, req.content, req.project_path)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    return {"success": True, "path": result["path"]}


@app.get("/read-project")
async def read_project(path: str, max_files: int = 50):
    try:
        return code_reader.read_project(path, max_files=max_files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print(f"[AI Developer Agent v2] Starting on http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
