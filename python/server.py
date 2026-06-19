"""
AI Developer Agent — Python Backend (FastAPI)
Chạy trên port 8765, nhận request từ Electron renderer qua axios
"""

import os
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.code_reader import CodeReader, IGNORE_DIRS
from agent.ai_agent import AIAgent

app = FastAPI(title="AI Developer Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


# ─── Path resolver ───────────────────────────────────────────────────────────

def normalize(p: str) -> str:
    """Chuẩn hóa path: thay / thành \\ trên Windows, strip spaces."""
    return str(Path(p.strip().replace("/", os.sep).replace("\\", os.sep)))


def resolve_path(raw: str, project_path: Optional[str] = None) -> Optional[Path]:
    """
    Tìm path thực tế trên filesystem từ path AI trả về.
    Thử theo thứ tự:
      1. Path tuyệt đối chính xác
      2. Path sau khi normalize dấu /\\
      3. Ghép project_path + phần cuối của raw path (relative fallback)
      4. Fuzzy: tìm file/dir có tên khớp trong project tree
    """
    # 1. Thử trực tiếp
    p = Path(raw.strip())
    if p.exists():
        return p

    # 2. Normalize separator
    p2 = Path(normalize(raw))
    if p2.exists():
        return p2

    # 3. Relative fallback — ghép project_path
    if project_path:
        proj = Path(project_path)
        # Thử coi raw là relative path
        candidate = proj / raw.strip().lstrip("/\\")
        if candidate.exists():
            return candidate

        # Thử lấy phần sau project_path nếu AI lặp lại root
        try:
            rel = Path(raw.strip()).relative_to(proj)
            candidate2 = proj / rel
            if candidate2.exists():
                return candidate2
        except ValueError:
            pass

        # 4. Fuzzy: lấy tên file/dir cuối rồi tìm trong project tree
        target_name = Path(raw.strip()).name
        if target_name:
            for found in Path(project_path).rglob(target_name):
                # Bỏ qua ignored dirs
                if not any(ig in found.parts for ig in IGNORE_DIRS):
                    print(f"[Resolve] fuzzy matched '{raw}' → '{found}'")
                    return found

    print(f"[Resolve] ✗ Cannot resolve: '{raw}'")
    return None


# ─── File operations ─────────────────────────────────────────────────────────

def delete_path(raw_path: str, project_path: Optional[str] = None) -> dict:
    """Xóa file hoặc thư mục với fuzzy path resolution."""
    resolved = resolve_path(raw_path, project_path)
    if resolved is None:
        return {
            "path": raw_path, "success": False,
            "error": f"Không tìm thấy: '{raw_path}'"
        }
    try:
        if resolved.is_dir():
            shutil.rmtree(resolved)
            print(f"[Agent] 🗑 Deleted dir : {resolved}")
        else:
            resolved.unlink()
            print(f"[Agent] 🗑 Deleted file: {resolved}")
        return {"path": str(resolved), "success": True}
    except Exception as e:
        print(f"[Agent] ✗ Failed to delete {resolved}: {e}")
        return {"path": str(resolved), "success": False, "error": str(e)}


def write_path(file_path: str, content: str) -> dict:
    """Ghi nội dung vào file, tự phát hiện create/update."""
    p = Path(normalize(file_path))
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
    Thứ tự: xóa trước → ghi sau (đúng với rename/move).
    """
    try:
        result = await ai_agent.chat(
            message=req.message,
            file_contexts=req.file_contexts,
            history=req.conversation_history,
            project_path=req.project_path
        )

        reply           = result.get("reply", "")
        files_to_write  = result.get("files_to_write", [])
        files_to_delete = result.get("files_to_delete", [])

        # 1️⃣ Xóa trước
        files_deleted = [
            delete_path(p, req.project_path)
            for p in files_to_delete if p
        ]

        # 2️⃣ Ghi sau
        files_written = []
        for f in files_to_write:
            file_path = f.get("path", "").strip()
            content   = f.get("content", "")
            if not file_path or content is None:
                files_written.append({
                    "path": file_path, "action": "unknown",
                    "success": False, "error": "Thiếu path hoặc content"
                })
                continue
            files_written.append(write_path(file_path, content))

        return {"reply": reply, "files_written": files_written, "files_deleted": files_deleted}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        return code_reader.read_project(path, max_files=max_files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print(f"[AI Developer Agent] Starting on http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
