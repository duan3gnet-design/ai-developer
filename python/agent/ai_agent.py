"""
AIAgent — core AI logic, gọi Groq API với model Qwen3 32B
"""

import os
import re
import json
from typing import Optional
from groq import Groq
from agent.code_reader import CodeReader

client      = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
code_reader = CodeReader()

MODEL             = "qwen/qwen3-32b"
CONTEXT_WINDOW    = 32_000
COMPLETION_TARGET = 4_000
COMPLETION_MIN    = 512
COMPLETION_MAX    = 6_000

# Budgets (chars)
TREE_BUDGET      = 1_500   # compact tree — luôn inject
CONTEXT_BUDGET   = 2_500   # file contexts
FILE_CONTENT_MAX = 1_000   # mỗi file được nhắc
HISTORY_BUDGET   = 3_000   # history

SYSTEM_BASE = """Bạn là AI Developer Agent — senior engineer chuyên Java/Spring Boot, microservices, cloud-native.
Trả lời bằng tiếng Việt. Code phải đầy đủ, không placeholder. Giải thích WHY.
/no_think"""

SYSTEM_WITH_WRITE = SYSTEM_BASE + """

Khi tạo/sửa/xóa/đổi tên file → trả về JSON (KHÔNG text thường):
{"reply":"...","files_to_write":[{"path":"PATH_TUYỆT_ĐỐI","content":"..."}],"files_to_delete":["PATH_TUYỆT_ĐỐI"]}

Quy tắc QUAN TRỌNG:
- path PHẢI copy y chang từ FILE TREE bên dưới, không tự sửa hay viết lại
- Đổi tên file A→B: files_to_write=[B], files_to_delete=[A lấy từ FILE TREE]
- Chỉ hỏi/phân tích: files_to_write=[], files_to_delete=[]
- JSON hợp lệ, không có text ngoài JSON"""


def _safe_max_tokens(system: str, messages: list) -> int:
    prompt_chars      = len(system) + sum(len(m.get("content", "")) for m in messages)
    prompt_tokens_est = prompt_chars // 3
    available         = CONTEXT_WINDOW - prompt_tokens_est - 300
    result            = max(COMPLETION_MIN, min(COMPLETION_TARGET, available, COMPLETION_MAX))
    print(f"[Token] prompt_est={prompt_tokens_est} max_completion={result}")
    return result


def _compact_tree(project_path: str, budget: int) -> str:
    """
    Sinh file tree cực compact: chỉ in path tuyệt đối, mỗi dòng 1 path.
    Dirs được đánh dấu bằng trailing backslash.
    Ưu tiên files trước (AI cần path file để xóa), dirs sau.
    """
    root = os.path.abspath(project_path)
    lines = []
    IGNORE = {'node_modules', '.git', 'dist', 'build', 'target',
              '__pycache__', '.idea', '.vscode', 'venv', '.venv',
              'out', 'bin', 'obj', '.gradle', '.mvn'}

    for dirpath, dirnames, filenames in os.walk(root):
        # Lọc ignored dirs in-place để os.walk không đi vào
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in IGNORE and not d.startswith('.')
        )
        # In files trước
        for fname in sorted(filenames):
            full = os.path.join(dirpath, fname)
            lines.append(full)
            if sum(len(l) + 1 for l in lines) > budget:
                lines.append("...(truncated)")
                return "\n".join(lines)
        # In dir
        if dirpath != root:
            lines.insert(
                next((i for i, l in enumerate(lines) if l == dirpath), len(lines)),
                dirpath + os.sep
            )

    # Sort cuối để AI dễ tìm
    file_lines = [l for l in lines if not l.endswith(os.sep) and l != "...(truncated)"]
    dir_lines  = [l for l in lines if l.endswith(os.sep)]
    all_lines  = sorted(file_lines) + sorted(dir_lines)

    result = "\n".join(all_lines)
    if len(result) > budget:
        result = result[:budget] + "\n...(truncated)"
    return result


def _trim_history(history: list, budget: int) -> list:
    if not history:
        return []
    result = []
    used   = 0
    for msg in reversed(history):
        role    = msg.get("role", "")
        content = msg.get("content", "")
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
    msg_lower = message.lower()
    parts     = []
    used      = 0
    for f in file_contexts:
        name    = f.get("name", "")
        path    = f.get("path", "")
        content = f.get("content", "")
        lang    = f.get("language", "")
        lines   = content.splitlines()

        mentioned = name.lower() in msg_lower or path.lower() in msg_lower
        if mentioned:
            snippet = "\n".join(lines[:FILE_CONTENT_MAX // 50])
            chunk   = f"\n### {name} (`{path}`)\n```{lang}\n{snippet}\n```"
        else:
            preview = "\n".join(lines[:4])
            chunk   = f"\n### {name} ({len(lines)} dòng) `{path}`\n```{lang}\n{preview}\n...\n```"

        if used + len(chunk) > budget:
            rest = file_contexts[file_contexts.index(f):]
            parts.append(f"\n_+{len(rest)} file: {', '.join(x.get('name','') for x in rest)}_")
            break
        parts.append(chunk)
        used += len(chunk)
    return "".join(parts)


class AIAgent:

    async def chat(
        self,
        message: str,
        file_contexts: list,
        history: list,
        project_path: Optional[str] = None,
    ) -> dict:
        system = SYSTEM_WITH_WRITE

        # ── Luôn inject file tree compact — AI cần path để write/delete ──────
        if project_path:
            tree = _compact_tree(project_path, TREE_BUDGET)
            system += f"\n\n## FILE TREE (copy path y chang khi dùng):\n{tree}"

        # ── File contexts ─────────────────────────────────────────────────────
        ctx_str = _trim_file_contexts(file_contexts, CONTEXT_BUDGET, message)
        if ctx_str:
            system += f"\n\n## Files đang mở:{ctx_str}"

        # ── History ───────────────────────────────────────────────────────────
        trimmed_history = _trim_history(history, HISTORY_BUDGET)
        messages        = trimmed_history + [{"role": "user", "content": message}]

        raw = self._call(system, messages)
        return self._parse_response(raw)

    async def analyze_project(self, summary: dict, focus: Optional[str] = None) -> str:
        focus_hint = {
            "bugs":         "Tìm bug, lỗi logic, NPE, race condition",
            "architecture": "Kiến trúc, layering, coupling, design patterns",
            "performance":  "Bottleneck, N+1 query, blocking call, memory leak",
        }.get(focus or "", "Tổng quan: architecture, code quality, đề xuất cải tiến")

        files_text = ""
        for f in summary.get("files", [])[:12]:
            files_text += f"\n### {f['relative_path']}\n```{f['language']}\n{f['content'][:500]}\n```\n"

        prompt = (
            f"Project: {summary.get('name')} | Files: {summary.get('total_files')} | "
            f"Languages: {json.dumps(summary.get('languages',{}), ensure_ascii=False)}\n\n"
            f"## Cấu trúc:\n{summary.get('tree_text','')[:TREE_BUDGET]}\n\n"
            f"## Code:\n{files_text}\n\n"
            f"Yêu cầu: {focus_hint}\n"
            f"Phân tích: 1.Kiến trúc 2.Điểm mạnh 3.Vấn đề(path+dòng) 4.Đề xuất 5.Bước tiếp"
        )
        return self._call(SYSTEM_BASE, [{"role": "user", "content": prompt}])

    def _call(self, system: str, messages: list) -> str:
        max_tok = _safe_max_tokens(system, messages)
        try:
            resp = client.chat.completions.create(
                model           = MODEL,
                max_tokens      = max_tok,
                messages        = [{"role": "system", "content": system}] + messages,
                response_format = {"type": "json_object"},
            )
            u = resp.usage
            print(f"[Token] prompt={u.prompt_tokens} completion={u.completion_tokens} total={u.total_tokens}/{CONTEXT_WINDOW}")
            return resp.choices[0].message.content
        except Exception as e:
            err = str(e).lower()
            if e.status_code == 401:
                msg = "❌ Lỗi xác thực GROQ_API_KEY. Kiểm tra file .env"
            elif e.status_code == 429:
                msg = "⏳ Rate limit. Thử lại sau vài giây."
            elif e.status_code == 413:
                msg = "⚠️ Prompt quá dài. Đóng bớt file context hoặc nhấn New Chat."
            else:
                msg = f"❌ Lỗi: {e}"
            return json.dumps({"reply": msg, "files_to_write": [], "files_to_delete": []})

    def _parse_response(self, raw: str) -> dict:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        text  = fence.group(1) if fence else raw.strip()
        try:
            data = json.loads(text)
            return {
                "reply":           data.get("reply", ""),
                "files_to_write":  data.get("files_to_write", []),
                "files_to_delete": data.get("files_to_delete", []),
            }
        except json.JSONDecodeError:
            return {"reply": raw, "files_to_write": [], "files_to_delete": []}
