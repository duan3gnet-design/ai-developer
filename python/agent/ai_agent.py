"""
AIAgent — Agentic loop với multi-step execution
Flow: PLAN → EXECUTE (nhiều steps) → DONE
"""

import os
import re
import json
import asyncio
from typing import Optional, AsyncGenerator
from groq import Groq
from agent.code_reader import CodeReader

client      = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
code_reader = CodeReader()

MODEL             = "qwen/qwen3-32b"
CONTEXT_WINDOW    = 32_000
COMPLETION_TARGET = 4_000
COMPLETION_MIN    = 512
COMPLETION_MAX    = 6_000
MAX_STEPS         = 10

TREE_BUDGET      = 1_500
CONTEXT_BUDGET   = 2_500
FILE_CONTENT_MAX = 1_000
HISTORY_BUDGET   = 3_000

SYSTEM_BASE = """Bạn là AI Developer Agent — senior engineer chuyên Java/Spring Boot, microservices, cloud-native.
Trả lời bằng tiếng Việt. Code phải đầy đủ, không placeholder. Giải thích WHY.
/no_think"""


def _plan_system(root: str) -> str:
    sep = os.sep
    example = root + sep + "src" + sep + "main" + sep + "java" + sep + "NewService.java"
    return SYSTEM_BASE + f"""

PROJECT_ROOT: {root}

Nhiệm vụ: Lập kế hoạch thực hiện yêu cầu của user.

Trả về JSON:
{{
  "is_complex": true/false,
  "summary": "Mô tả ngắn task",
  "steps": [
    {{
      "id": 1,
      "title": "Tên bước",
      "description": "Chi tiết",
      "files": ["{example}"]
    }}
  ]
}}

QUY TẮC PATH (BẮT BUỘC):
- Mọi path PHẢI bắt đầu bằng PROJECT_ROOT="{root}"
- File cũ: copy y chang từ FILE TREE bên dưới
- File mới: "{root}{sep}sub{sep}dir{sep}FileName.java" (ghép PROJECT_ROOT + đường dẫn con)
- TUYỆT ĐỐI không dùng relative path, không slash ở đầu, không drive letter khác
- is_complex=false nếu chỉ hỏi/phân tích hoặc 1 file → steps=[]
- Mỗi step 1-3 file, tối đa 10 steps"""


def _execute_system(root: str) -> str:
    sep = os.sep
    example_w = root + sep + "src" + sep + "NewFile.java"
    example_d = root + sep + "src" + sep + "OldFile.java"
    return SYSTEM_BASE + f"""

PROJECT_ROOT: {root}

Nhiệm vụ: Thực hiện đúng 1 bước trong kế hoạch.

Trả về JSON:
{{
  "step_summary": "Tóm tắt bước này",
  "files_to_write": [{{"path": "{example_w}", "content": "toàn bộ nội dung"}}],
  "files_to_delete": ["{example_d}"]
}}

QUY TẮC PATH (BẮT BUỘC):
- Mọi path PHẢI bắt đầu bằng PROJECT_ROOT="{root}"
- File cũ cần xóa: copy y chang từ FILE TREE
- File mới: ghép "{root}{sep}" + đường dẫn con
- TUYỆT ĐỐI không relative path, không path ngoài PROJECT_ROOT
- content HOÀN CHỈNH, không dùng // ... existing code
- JSON hợp lệ, không text ngoài JSON"""


def _single_system(root: str) -> str:
    sep = os.sep
    example = root + sep + "src" + sep + "File.java"
    return SYSTEM_BASE + f"""

PROJECT_ROOT: {root}

Khi tạo/sửa/xóa file → trả về JSON:
{{"reply":"...","files_to_write":[{{"path":"{example}","content":"..."}}],"files_to_delete":["{example}"]}}

QUY TẮC PATH (BẮT BUỘC):
- Mọi path PHẢI bắt đầu bằng PROJECT_ROOT="{root}"
- File cũ: copy từ FILE TREE. File mới: "{root}{sep}" + đường dẫn con
- content đầy đủ. Chỉ hỏi/phân tích: files_to_write=[], files_to_delete=[]"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fix_paths(items, project_root: str) -> list:
    """
    Hậu xử lý path AI trả về:
    - Nếu là relative → prefix project_root
    - Nếu bắt đầu bằng drive letter khác → cảnh báo (server sẽ guard)
    - Normalize separator
    """
    root = os.path.abspath(project_root)
    fixed = []
    for item in items:
        # item có thể là str (files_to_delete) hoặc dict (files_to_write)
        if isinstance(item, str):
            fixed.append(_fix_one_path(item, root))
        elif isinstance(item, dict):
            item = dict(item)
            item["path"] = _fix_one_path(item.get("path", ""), root)
            fixed.append(item)
    return fixed


def _fix_one_path(raw: str, root: str) -> str:
    if not raw:
        return raw
    # Normalize slashes
    p = raw.strip().replace("/", os.sep).replace("\\", os.sep)
    # Nếu là relative path (không có drive letter trên Windows, không bắt đầu bằng /)
    if not os.path.isabs(p):
        p = os.path.join(root, p.lstrip(os.sep))
    return p


def _safe_max_tokens(system: str, messages: list) -> int:
    chars     = len(system) + sum(len(m.get("content", "")) for m in messages)
    est       = chars // 3
    available = CONTEXT_WINDOW - est - 300
    result    = max(COMPLETION_MIN, min(COMPLETION_TARGET, available, COMPLETION_MAX))
    print(f"[Token] prompt_est={est} max_completion={result}")
    return result


def _compact_tree(project_path: str, budget: int) -> str:
    root   = os.path.abspath(project_path)
    lines  = []
    IGNORE = {'node_modules','.git','dist','build','target',
              '__pycache__','.idea','.vscode','venv','.venv',
              'out','bin','obj','.gradle','.mvn'}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE and not d.startswith('.'))
        for fname in sorted(filenames):
            lines.append(os.path.join(dirpath, fname))
    lines.sort()
    result = "\n".join(lines)
    if len(result) > budget:
        result = result[:budget] + "\n...(truncated)"
    return result


def _trim_history(history: list, budget: int) -> list:
    result, used = [], 0
    for msg in reversed(history):
        role, content = msg.get("role",""), msg.get("content","")
        if role == "assistant" and len(content) > 350:
            content = content[:350] + " ...[rút gọn]"
        if used + len(content) > budget and result:
            break
        result.insert(0, {"role": role, "content": content})
        used += len(content)
    return result


def _trim_file_contexts(file_contexts: list, budget: int, message: str) -> str:
    if not file_contexts:
        return ""
    msg_lower, parts, used = message.lower(), [], 0
    for f in file_contexts:
        name, path = f.get("name",""), f.get("path","")
        content, lang = f.get("content",""), f.get("language","")
        lines = content.splitlines()
        mentioned = name.lower() in msg_lower or path.lower() in msg_lower
        if mentioned:
            snippet = "\n".join(lines[:FILE_CONTENT_MAX//50])
            chunk   = f"\n### {name} (`{path}`)\n```{lang}\n{snippet}\n```"
        else:
            chunk = f"\n### {name} ({len(lines)} dòng) `{path}`\n```{lang}\n{chr(10).join(lines[:4])}\n...\n```"
        if used + len(chunk) > budget:
            rest = file_contexts[file_contexts.index(f):]
            parts.append(f"\n_+{len(rest)} file: {', '.join(x.get('name','') for x in rest)}_")
            break
        parts.append(chunk); used += len(chunk)
    return "".join(parts)


def _call(system: str, messages: list) -> str:
    max_tok = _safe_max_tokens(system, messages)
    try:
        resp = client.chat.completions.create(
            model=MODEL, max_tokens=max_tok,
            messages=[{"role":"system","content":system}] + messages,
            response_format={"type":"json_object"},
        )
        u = resp.usage
        print(f"[Token] prompt={u.prompt_tokens} completion={u.completion_tokens} total={u.total_tokens}")
        return resp.choices[0].message.content
    except Exception as e:
        err = str(e).lower()
        if "401" in err or "auth" in err:
            msg = "❌ Lỗi xác thực GROQ_API_KEY"
        elif "429" in err or "rate" in err:
            msg = "⏳ Rate limit. Thử lại sau vài giây."
        elif "413" in err or "context" in err or "length" in err:
            msg = "⚠️ Prompt quá dài. Đóng bớt file context hoặc nhấn New Chat."
        else:
            msg = f"❌ Lỗi: {e}"
        return json.dumps({"reply": msg, "files_to_write": [], "files_to_delete": []})


def _parse(raw: str) -> dict:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    text  = fence.group(1) if fence else raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"reply": raw, "files_to_write": [], "files_to_delete": []}


def _build_system(project_path: Optional[str], file_contexts: list,
                  message: str, system_fn) -> tuple:
    """Build system + messages, inject tree + file contexts."""
    root   = os.path.abspath(project_path) if project_path else None
    system = system_fn(root) if root else SYSTEM_BASE
    if root:
        tree = _compact_tree(root, TREE_BUDGET)
        system += f"\n\n## FILE TREE (toàn bộ path tuyệt đối):\n{tree}"
    ctx = _trim_file_contexts(file_contexts, CONTEXT_BUDGET, message)
    if ctx:
        system += f"\n\n## Files đang mở:{ctx}"
    return system, root


# ─── AIAgent ──────────────────────────────────────────────────────────────────

class AIAgent:

    async def chat_stream(
        self,
        message: str,
        file_contexts: list,
        history: list,
        project_path: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:

        root = os.path.abspath(project_path) if project_path else None

        # ── PHASE 1: PLAN ─────────────────────────────────────────────────────
        plan_sys, _ = _build_system(root, file_contexts, message, _plan_system)
        plan_msgs   = _trim_history(history, HISTORY_BUDGET) + [{"role":"user","content":message}]
        plan_data   = _parse(_call(plan_sys, plan_msgs))

        is_complex = plan_data.get("is_complex", False)
        steps      = plan_data.get("steps", [])
        summary    = plan_data.get("summary", message)

        # ── Simple: single call ───────────────────────────────────────────────
        if not is_complex or not steps:
            yield {"type":"plan","data":{"summary":summary,"steps":[],"is_complex":False}}
            single_sys, _ = _build_system(root, file_contexts, message, _single_system)
            single_msgs   = _trim_history(history, HISTORY_BUDGET) + [{"role":"user","content":message}]
            data = _parse(_call(single_sys, single_msgs))
            # Fix paths trước khi trả về
            if root:
                data["files_to_write"]  = _fix_paths(data.get("files_to_write", []),  root)
                data["files_to_delete"] = _fix_paths(data.get("files_to_delete", []), root)
            yield {"type":"done","data":{
                "reply":           data.get("reply",""),
                "files_to_write":  data.get("files_to_write",[]),
                "files_to_delete": data.get("files_to_delete",[]),
            }}
            return

        # ── Complex: agentic loop ─────────────────────────────────────────────
        yield {"type":"plan","data":{"summary":summary,"steps":steps,"is_complex":True}}

        all_written, all_deleted, step_summaries = [], [], []

        for step in steps[:MAX_STEPS]:
            step_id = step.get("id", 0)
            title   = step.get("title", f"Bước {step_id}")
            desc    = step.get("description", "")
            files   = step.get("files", [])

            yield {"type":"step_start","data":{"step_id":step_id,"title":title,"description":desc}}

            step_context = (
                f"Kế hoạch: {summary}\n"
                f"Đã xong: {'; '.join(step_summaries) or 'chưa có'}\n"
                f"Bước hiện tại ({step_id}/{len(steps)}): {title} — {desc}\n"
                f"Files bước này: {', '.join(files) or 'xem mô tả'}"
            )
            exec_sys, _ = _build_system(root, file_contexts, step_context, _execute_system)
            exec_msgs   = [{"role":"user","content":f"Yêu cầu gốc: {message}\n\n{step_context}"}]

            exec_data    = _parse(_call(exec_sys, exec_msgs))
            step_written = exec_data.get("files_to_write", [])
            step_deleted = exec_data.get("files_to_delete", [])
            step_summary = exec_data.get("step_summary", title)

            # Fix paths ngay sau mỗi step
            if root:
                step_written = _fix_paths(step_written, root)
                step_deleted = _fix_paths(step_deleted, root)

            all_written.extend(step_written)
            all_deleted.extend(step_deleted)
            step_summaries.append(step_summary)

            yield {"type":"step_done","data":{
                "step_id":       step_id,
                "title":         title,
                "files_to_write":  step_written,
                "files_to_delete": step_deleted,
                "summary":       step_summary,
            }}

            await asyncio.sleep(0.3)

        yield {"type":"done","data":{
            "reply": (
                f"✅ Hoàn thành: **{summary}**\n\n"
                + "\n".join(f"**Bước {i+1}:** {s}" for i,s in enumerate(step_summaries))
                + f"\n\n📁 {len(all_written)} file ghi, {len(all_deleted)} file xóa."
            ),
            "files_to_write":  all_written,
            "files_to_delete": all_deleted,
        }}

    async def chat(self, message, file_contexts, history, project_path=None) -> dict:
        result = {"reply":"","files_to_write":[],"files_to_delete":[]}
        async for event in self.chat_stream(message, file_contexts, history, project_path):
            if event["type"] == "done":
                d = event["data"]
                result.update({"reply":d.get("reply",""),"files_to_write":d.get("files_to_write",[]),"files_to_delete":d.get("files_to_delete",[])})
            elif event["type"] == "error":
                result["reply"] = event["data"].get("message","❌ Lỗi")
        return result

    async def analyze_project(self, summary: dict, focus: Optional[str] = None) -> str:
        focus_hint = {
            "bugs":         "Tìm bug, lỗi logic, NPE, race condition",
            "architecture": "Kiến trúc, layering, coupling, design patterns",
            "performance":  "Bottleneck, N+1 query, blocking call, memory leak",
        }.get(focus or "", "Tổng quan: architecture, code quality, đề xuất cải tiến")

        files_text = "".join(
            f"\n### {f['relative_path']}\n```{f['language']}\n{f['content'][:500]}\n```\n"
            for f in summary.get("files",[])[:12]
        )
        prompt = (
            f"Project: {summary.get('name')} | Files: {summary.get('total_files')} | "
            f"Languages: {json.dumps(summary.get('languages',{}),ensure_ascii=False)}\n\n"
            f"## Cấu trúc:\n{summary.get('tree_text','')[:TREE_BUDGET]}\n\n"
            f"## Code:\n{files_text}\n\n"
            f"Yêu cầu: {focus_hint}\n"
            f"Phân tích: 1.Kiến trúc 2.Điểm mạnh 3.Vấn đề(path+dòng) 4.Đề xuất 5.Bước tiếp"
        )
        raw  = _call(SYSTEM_BASE, [{"role":"user","content":prompt}])
        data = _parse(raw)
        return data.get("reply", raw)
