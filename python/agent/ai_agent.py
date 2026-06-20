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
MAX_STEPS         = 10     # giới hạn số bước tối đa trong 1 task

TREE_BUDGET      = 1_500
CONTEXT_BUDGET   = 2_500
FILE_CONTENT_MAX = 1_000
HISTORY_BUDGET   = 3_000

SYSTEM_BASE = """Bạn là AI Developer Agent — senior engineer chuyên Java/Spring Boot, microservices, cloud-native.
Trả lời bằng tiếng Việt. Code phải đầy đủ, không placeholder. Giải thích WHY.
/no_think"""

# ── Prompt cho bước PLAN ─────────────────────────────────────────────────────
PLAN_SYSTEM = SYSTEM_BASE + """

Nhiệm vụ: Lập kế hoạch chi tiết để thực hiện yêu cầu của user.

Trả về JSON:
{
  "is_complex": true/false,
  "summary": "Mô tả ngắn gọn task sẽ làm",
  "steps": [
    {
      "id": 1,
      "title": "Tên bước ngắn gọn",
      "description": "Mô tả chi tiết bước này làm gì",
      "files": ["path tuyệt đối của file sẽ tạo/sửa trong bước này"]
    }
  ]
}

Quy tắc:
- is_complex=false nếu chỉ cần 1 file hoặc câu hỏi/phân tích → steps=[]
- is_complex=true nếu cần tạo/sửa nhiều file, nhiều module
- Mỗi step chỉ xử lý 1-3 file liên quan chặt chẽ (không nhồi quá nhiều)
- path trong steps.files lấy từ FILE TREE nếu là file cũ, hoặc path mới hoàn chỉnh nếu tạo mới
- Tối đa 10 steps"""

# ── Prompt cho bước EXECUTE ───────────────────────────────────────────────────
EXECUTE_SYSTEM = SYSTEM_BASE + """

Nhiệm vụ: Thực hiện đúng 1 bước trong kế hoạch đã lập.

Trả về JSON:
{
  "step_summary": "Tóm tắt những gì đã làm trong bước này",
  "files_to_write": [{"path": "PATH_TUYỆT_ĐỐI", "content": "toàn bộ nội dung"}],
  "files_to_delete": ["PATH_TUYỆT_ĐỐI"]
}

Quy tắc QUAN TRỌNG:
- Chỉ thực hiện đúng files được liệt kê trong bước này, không làm lố sang bước khác
- content phải là code HOÀN CHỈNH, không dùng // ... existing code
- path lấy chính xác từ FILE TREE, không tự viết lại
- JSON hợp lệ, không có text ngoài JSON"""

# ── Prompt cho single-step (is_complex=false) ─────────────────────────────────
SINGLE_SYSTEM = SYSTEM_BASE + """

Khi tạo/sửa/xóa/đổi tên file → trả về JSON:
{"reply":"...","files_to_write":[{"path":"PATH_TUYỆT_ĐỐI","content":"..."}],"files_to_delete":["PATH_TUYỆT_ĐỐI"]}

Quy tắc:
- path copy y chang từ FILE TREE
- content đầy đủ, không placeholder
- Chỉ hỏi/phân tích: files_to_write=[], files_to_delete=[]"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

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
        if e.status_code == 401:
            msg = "❌ Lỗi xác thực GROQ_API_KEY. Kiểm tra file .env"
        elif e.status_code == 429:
            msg = "⏳ Rate limit. Thử lại sau vài giây."
        elif e.status_code == 413:
            msg = "⚠️ Prompt quá dài. Đóng bớt file context hoặc nhấn New Chat."
        else:
            msg = f"❌ Lỗi: {str(e)}"
        return json.dumps({"reply": msg, "files_to_write": [], "files_to_delete": []})


def _parse(raw: str) -> dict:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    text  = fence.group(1) if fence else raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"reply": raw, "files_to_write": [], "files_to_delete": []}


def _build_base_system(project_path: Optional[str], file_contexts: list,
                        history: list, message: str, system_template: str) -> tuple:
    """Build system prompt + messages chung cho mọi loại call."""
    system = system_template
    if project_path:
        tree = _compact_tree(project_path, TREE_BUDGET)
        system += f"\n\n## FILE TREE:\n{tree}"
    ctx = _trim_file_contexts(file_contexts, CONTEXT_BUDGET, message)
    if ctx:
        system += f"\n\n## Files đang mở:{ctx}"
    msgs = _trim_history(history, HISTORY_BUDGET) + [{"role":"user","content":message}]
    return system, msgs


# ─── AIAgent ──────────────────────────────────────────────────────────────────

class AIAgent:

    async def chat_stream(
        self,
        message: str,
        file_contexts: list,
        history: list,
        project_path: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Agentic loop — yield từng event về cho server để stream SSE:
          {"type":"plan",    "data": {summary, steps}}
          {"type":"step_start", "data": {step_id, title, description}}
          {"type":"step_done",  "data": {step_id, files_written, files_deleted, summary}}
          {"type":"done",    "data": {reply, total_files_written, total_files_deleted}}
          {"type":"error",   "data": {message}}
        """
        # ── PHASE 1: PLAN ─────────────────────────────────────────────────────
        plan_system, plan_msgs = _build_base_system(
            project_path, file_contexts, history, message, PLAN_SYSTEM
        )
        plan_raw  = _call(plan_system, plan_msgs)
        plan_data = _parse(plan_raw)

        is_complex = plan_data.get("is_complex", False)
        steps      = plan_data.get("steps", [])
        summary    = plan_data.get("summary", message)

        # Simple request → single call, không cần loop
        if not is_complex or not steps:
            yield {"type": "plan", "data": {"summary": summary, "steps": [], "is_complex": False}}
            single_system, single_msgs = _build_base_system(
                project_path, file_contexts, history, message, SINGLE_SYSTEM
            )
            raw  = _call(single_system, single_msgs)
            data = _parse(raw)
            yield {
                "type": "done",
                "data": {
                    "reply":               data.get("reply", ""),
                    "files_to_write":      data.get("files_to_write", []),
                    "files_to_delete":     data.get("files_to_delete", []),
                    "total_files_written": len(data.get("files_to_write", [])),
                }
            }
            return

        # ── PHASE 2: EXECUTE từng step ────────────────────────────────────────
        yield {"type": "plan", "data": {"summary": summary, "steps": steps, "is_complex": True}}

        all_written  = []
        all_deleted  = []
        step_summaries = []

        for step in steps[:MAX_STEPS]:
            step_id = step.get("id", 0)
            title   = step.get("title", f"Bước {step_id}")
            desc    = step.get("description", "")
            files   = step.get("files", [])

            yield {"type": "step_start", "data": {"step_id": step_id, "title": title, "description": desc}}

            # Build execute prompt với context của step này
            step_context = (
                f"Kế hoạch tổng thể: {summary}\n\n"
                f"Các bước đã hoàn thành:\n" +
                ("\n".join(f"- Bước {i+1}: {s}" for i, s in enumerate(step_summaries)) or "  (chưa có)") +
                f"\n\nBước hiện tại ({step_id}/{len(steps)}): {title}\n{desc}\n"
                f"Files cần xử lý trong bước này: {', '.join(files) or 'xem mô tả'}"
            )

            exec_system, _ = _build_base_system(
                project_path, file_contexts, [], step_context, EXECUTE_SYSTEM
            )
            # Thêm original message để AI có đủ context
            exec_msgs = [{"role": "user", "content":
                f"Yêu cầu gốc: {message}\n\n{step_context}"}]

            raw      = _call(exec_system, exec_msgs)
            exec_data = _parse(raw)

            step_written  = exec_data.get("files_to_write", [])
            step_deleted  = exec_data.get("files_to_delete", [])
            step_summary  = exec_data.get("step_summary", title)

            all_written.extend(step_written)
            all_deleted.extend(step_deleted)
            step_summaries.append(step_summary)

            yield {
                "type": "step_done",
                "data": {
                    "step_id":       step_id,
                    "title":         title,
                    "files_to_write":  step_written,
                    "files_to_delete": step_deleted,
                    "summary":       step_summary,
                }
            }

            # Nhỏ delay để tránh rate limit
            await asyncio.sleep(0.3)

        # ── PHASE 3: DONE ─────────────────────────────────────────────────────
        final_reply = (
            f"✅ Hoàn thành: **{summary}**\n\n"
            + "\n".join(f"**Bước {i+1}:** {s}" for i, s in enumerate(step_summaries))
            + f"\n\n📁 Tổng cộng: {len(all_written)} file ghi, {len(all_deleted)} file xóa."
        )

        yield {
            "type": "done",
            "data": {
                "reply":           final_reply,
                "files_to_write":  all_written,
                "files_to_delete": all_deleted,
                "total_files_written": len(all_written),
            }
        }

    async def chat(self, message, file_contexts, history, project_path=None) -> dict:
        """Wrapper non-stream cho backward compat (analyze panel, etc.)"""
        result = {"reply": "", "files_to_write": [], "files_to_delete": []}
        async for event in self.chat_stream(message, file_contexts, history, project_path):
            if event["type"] == "done":
                d = event["data"]
                result["reply"]           = d.get("reply", "")
                result["files_to_write"]  = d.get("files_to_write", [])
                result["files_to_delete"] = d.get("files_to_delete", [])
            elif event["type"] == "error":
                result["reply"] = event["data"].get("message", "❌ Lỗi")
        return result

    async def analyze_project(self, summary: dict, focus: Optional[str] = None) -> str:
        focus_hint = {
            "bugs":         "Tìm bug, lỗi logic, NPE, race condition",
            "architecture": "Kiến trúc, layering, coupling, design patterns",
            "performance":  "Bottleneck, N+1 query, blocking call, memory leak",
        }.get(focus or "", "Tổng quan: architecture, code quality, đề xuất cải tiến")

        files_text = "".join(
            f"\n### {f['relative_path']}\n```{f['language']}\n{f['content'][:500]}\n```\n"
            for f in summary.get("files", [])[:12]
        )
        prompt = (
            f"Project: {summary.get('name')} | Files: {summary.get('total_files')} | "
            f"Languages: {json.dumps(summary.get('languages',{}), ensure_ascii=False)}\n\n"
            f"## Cấu trúc:\n{summary.get('tree_text','')[:TREE_BUDGET]}\n\n"
            f"## Code:\n{files_text}\n\n"
            f"Yêu cầu: {focus_hint}\n"
            f"Phân tích: 1.Kiến trúc 2.Điểm mạnh 3.Vấn đề(path+dòng) 4.Đề xuất 5.Bước tiếp"
        )
        raw = _call(SYSTEM_BASE, [{"role":"user","content":prompt}])
        data = _parse(raw)
        return data.get("reply", raw)
