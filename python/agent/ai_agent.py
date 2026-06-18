"""
AIAgent — core AI logic, gọi Groq API với model Qwen3 32B
"""

import os
import re
import json
from typing import Optional
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

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

# System prompt đặc biệt cho chat có khả năng ghi file
SYSTEM_WITH_WRITE = SYSTEM_BASE + """
## Khả năng ghi file

Khi user yêu cầu tạo file mới, sửa file, implement tính năng, refactor, hay bất kỳ thao tác nào cần thay đổi code — bạn PHẢI trả về JSON theo đúng format sau, KHÔNG trả về plain text:

```json
{
  "reply": "Giải thích bằng tiếng Việt những gì bạn đã làm, tại sao, và hướng dẫn bước tiếp theo",
  "files_to_write": [
    {
      "path": "đường dẫn tuyệt đối đến file, ví dụ: E:\\\\Projects\\\\myapp\\\\src\\\\main\\\\java\\\\com\\\\example\\\\Service.java",
      "content": "toàn bộ nội dung file, không được bỏ sót dòng nào",
      "action": "create" hoặc "update"
    }
  ]
}
```

Quy tắc bắt buộc:
- `files_to_write` phải là mảng, có thể chứa nhiều file cùng lúc
- `content` phải là code hoàn chỉnh, KHÔNG dùng comment placeholder như `// ... existing code`
- `path` phải là đường dẫn tuyệt đối dựa trên project_path được cung cấp
- Nếu câu hỏi chỉ là hỏi/phân tích, KHÔNG cần ghi file → trả về JSON với `"files_to_write": []`
- Luôn trả về JSON hợp lệ, không có text ngoài JSON block
"""


class AIAgent:

    async def chat(
        self,
        message: str,
        file_contexts: list,
        history: list,
        project_path: Optional[str] = None
    ) -> dict:
        """
        Chat với khả năng tự ghi file.
        Trả về: { reply: str, files_to_write: [{ path, content, action }] }
        """
        system = SYSTEM_WITH_WRITE

        if file_contexts:
            system += "\n\n## Files đang được mở:\n"
            for f in file_contexts:
                lang = f.get("language", "")
                system += f"\n### {f['name']} (`{f['path']}`)\n```{lang}\n{f['content'][:3000]}\n```\n"

        if project_path:
            system += f"\n\n**Project đang làm việc:** `{project_path}`\nDùng đường dẫn này làm gốc khi tạo file mới."

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

## Cấu trúc thư mục:
{tree_text}

## Nội dung files (rút gọn):
{files_text}

---
**Yêu cầu:** {focus_hint}

Hãy đưa ra phân tích chi tiết, có cấu trúc rõ ràng với các mục:
1. Tổng quan kiến trúc
2. Điểm mạnh
3. Vấn đề phát hiện (với file + dòng cụ thể nếu có)
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
        """Parse JSON response từ model, fallback về plain text nếu không parse được"""
        # Thử extract JSON từ markdown fences nếu có
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        text = fence.group(1) if fence else raw.strip()

        try:
            data = json.loads(text)
            return {
                "reply": data.get("reply", ""),
                "files_to_write": data.get("files_to_write", [])
            }
        except json.JSONDecodeError:
            # Model không trả về JSON đúng format — coi là plain text chat
            return {"reply": raw, "files_to_write": []}
