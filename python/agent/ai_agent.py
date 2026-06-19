"""
AIAgent — core AI logic, gọi Groq API với model Qwen3 32B
"""

import os
import re
import json
from typing import Optional
from groq import Groq
from agent.code_reader import CodeReader

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
code_reader = CodeReader()

MODEL = "qwen/qwen3-32b"
MAX_TOKENS = 6000

SYSTEM_BASE = """Bạn là AI Developer Agent — một kỹ sư phần mềm senior chuyên Java/Spring Boot, microservices, và kiến trúc cloud-native.

Khả năng của bạn:
- Đọc và hiểu toàn bộ codebase
- Phân tích architecture, tìm bug, đề xuất cải tiến
- Viết code mới hoàn chỉnh (class, service, test, config)
- Refactor và tối ưu performance
- Tư vấn về design patterns, SOLID, DRY

Phong cách trả lời:
- Dùng tiếng Việt cho giải thích
- Code thì viết đầy đủ, không dùng placeholder
- Luôn giải thích WHY, không chỉ WHAT
/no_think
"""

SYSTEM_WITH_WRITE = SYSTEM_BASE + """
## Khả năng ghi và xóa file

Khi user yêu cầu tạo, sửa, đổi tên, di chuyển, hay xóa file/thư mục — bạn PHẢI trả về JSON theo đúng format sau:

{
  "reply": "Giải thích bằng tiếng Việt những gì bạn đã làm và tại sao",
  "files_to_write": [
    {
      "path": "đường dẫn tuyệt đối CHÍNH XÁC lấy từ PROJECT FILE TREE bên dưới",
      "content": "toàn bộ nội dung file, không được dùng placeholder"
    }
  ],
  "files_to_delete": [
    "đường dẫn tuyệt đối CHÍNH XÁC lấy từ PROJECT FILE TREE bên dưới"
  ]
}

Quy tắc bắt buộc:
- `path` trong files_to_write và files_to_delete PHẢI là đường dẫn tuyệt đối, lấy CHÍNH XÁC từ PROJECT FILE TREE được cung cấp — không được tự đoán hay viết tắt
- Khi ĐỔI TÊN file: thêm path mới vào files_to_write, thêm path CŨ (từ file tree) vào files_to_delete
- Khi ĐỔI TÊN thư mục: ghi tất cả file mới vào files_to_write, thêm đường dẫn thư mục CŨ vào files_to_delete
- content phải là code hoàn chỉnh, KHÔNG dùng "// ... existing code"
- Nếu chỉ hỏi/phân tích: trả về JSON với cả hai mảng rỗng []
- Luôn trả về JSON hợp lệ, không có text ngoài JSON
"""


class AIAgent:

    async def chat(
        self,
        message: str,
        file_contexts: list,
        history: list,
        project_path: Optional[str] = None
    ) -> dict:
        system = SYSTEM_WITH_WRITE

        # ── Inject project file tree với path tuyệt đối ──────────────────────
        if project_path:
            tree_text = code_reader.get_tree_text(project_path)
            system += f"\n\n## PROJECT FILE TREE (dùng path này khi ghi/xóa file)\n```\n{tree_text}\n```"
            system += f"\n\n**Project root:** `{project_path}`"

        # ── Inject nội dung file đang mở ─────────────────────────────────────
        if file_contexts:
            system += "\n\n## Files đang được mở:\n"
            for f in file_contexts:
                lang = f.get("language", "")
                system += f"\n### {f['name']} (`{f['path']}`)\n```{lang}\n{f['content'][:3000]}\n```\n"

        messages = self._build_messages(history, message)
        raw = self._call(system, messages)
        return self._parse_response(raw)

    async def analyze_project(self, summary: dict, focus: Optional[str] = None) -> str:
        focus_map = {
            "bugs":         "Tập trung tìm bug, lỗi logic, NullPointerException tiềm ẩn, race condition",
            "architecture": "Tập trung phân tích kiến trúc, layering, coupling, cohesion, design patterns",
            "performance":  "Tập trung tìm bottleneck, N+1 query, blocking call, memory leak"
        }
        focus_hint = focus_map.get(focus or "", "Phân tích tổng quan: architecture, code quality, và đề xuất cải tiến")

        tree_text = summary.get("tree_text", "")
        files_text = ""
        for f in summary.get("files", [])[:20]:
            files_text += f"\n### {f['relative_path']} ({f['lines']} dòng)\n```{f['language']}\n{f['content'][:1000]}\n```\n"

        prompt = f"""Phân tích project sau:

**Project:** {summary.get('name')}
**Languages:** {json.dumps(summary.get('languages', {}), ensure_ascii=False)}
**Tổng files:** {summary.get('total_files')}

## Cấu trúc thư mục (path tuyệt đối):
{tree_text}

## Nội dung files (rút gọn):
{files_text}

---
**Yêu cầu:** {focus_hint}

Hãy đưa ra phân tích chi tiết với các mục:
1. Tổng quan kiến trúc
2. Điểm mạnh
3. Vấn đề phát hiện (với path + dòng cụ thể nếu có)
4. Đề xuất cải tiến (ưu tiên theo impact)
5. Bước tiếp theo nên làm"""

        return self._call(SYSTEM_BASE, [{"role": "user", "content": prompt}])

    # ─── Private ──────────────────────────────────────────────────────────────

    def _build_messages(self, history: list, new_message: str) -> list:
        messages = []
        for h in history[-20:]:
            if h.get("role") in ("user", "assistant"):
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": new_message})
        return messages

    def _call(self, system: str, messages: list) -> str:
        try:
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_TOKENS - sum(len(s) for s in messages) - len(system) - 33,
                messages=[{"role": "system", "content": system}] + messages,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e:
            err = str(e).lower()
            if e.status_code == 401:
                return "❌ Lỗi xác thực API key. Vui lòng kiểm tra GROQ_API_KEY trong file .env"
            if e.status_code == 429:
                return json.dumps({"reply": "⏳ Rate limit. Vui lòng thử lại sau vài giây.", "files_to_write": []})
            return json.dumps({"reply": f"❌ Lỗi: {str(e)}", "files_to_write": []})

    def _parse_response(self, raw: str) -> dict:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        text = fence.group(1) if fence else raw.strip()
        try:
            data = json.loads(text)
            return {
                "reply": data.get("reply", ""),
                "files_to_write": data.get("files_to_write", []),
                "files_to_delete": data.get("files_to_delete", []),
            }
        except json.JSONDecodeError:
            return {"reply": raw, "files_to_write": [], "files_to_delete": []}
