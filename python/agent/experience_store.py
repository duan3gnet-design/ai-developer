"""
ExperienceStore — Lưu trữ và truy xuất kinh nghiệm người dùng
để cải thiện chất lượng sinh code của AI.

Mỗi "experience" gồm:
  - id: uuid
  - title: tên ngắn
  - context: ngữ cảnh (ngôn ngữ, framework, loại task...)
  - problem: vấn đề / yêu cầu
  - solution: giải pháp / code mẫu / quy tắc
  - tags: danh sách tag để tìm kiếm nhanh
  - created_at / updated_at
"""

import json
import uuid
import os
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


STORE_FILE = Path(__file__).parent.parent / "data" / "experiences.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> list[dict]:
    STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STORE_FILE.exists():
        return []
    try:
        return json.loads(STORE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(records: list[dict]) -> None:
    STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STORE_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def add_experience(
    title: str,
    problem: str,
    solution: str,
    context: str = "",
    tags: list[str] | None = None,
) -> dict:
    """Thêm kinh nghiệm mới, trả về record vừa tạo."""
    records = _load()
    record = {
        "id":         str(uuid.uuid4()),
        "title":      title.strip(),
        "context":    context.strip(),
        "problem":    problem.strip(),
        "solution":   solution.strip(),
        "tags":       [t.lower().strip() for t in (tags or []) if t.strip()],
        "created_at": _now(),
        "updated_at": _now(),
    }
    records.append(record)
    _save(records)
    return record


def update_experience(exp_id: str, **fields) -> Optional[dict]:
    """Cập nhật một số trường của experience. Trả về None nếu không tìm thấy."""
    records = _load()
    allowed = {"title", "context", "problem", "solution", "tags"}
    for i, r in enumerate(records):
        if r["id"] == exp_id:
            for k, v in fields.items():
                if k in allowed:
                    records[i][k] = v
            records[i]["updated_at"] = _now()
            _save(records)
            return records[i]
    return None


def delete_experience(exp_id: str) -> bool:
    """Xóa experience theo id. Trả về True nếu xóa được."""
    records = _load()
    new_records = [r for r in records if r["id"] != exp_id]
    if len(new_records) == len(records):
        return False
    _save(new_records)
    return True


def get_all_experiences() -> list[dict]:
    """Lấy toàn bộ danh sách, mới nhất trước."""
    records = _load()
    return sorted(records, key=lambda r: r.get("updated_at", ""), reverse=True)


def get_experience(exp_id: str) -> Optional[dict]:
    for r in _load():
        if r["id"] == exp_id:
            return r
    return None


# ─── Search & Inject ──────────────────────────────────────────────────────────

def search_experiences(query: str, tags: list[str] | None = None, top_k: int = 5) -> list[dict]:
    """
    Tìm kiếm kinh nghiệm liên quan bằng keyword matching đơn giản.
    Trả về top_k kết quả theo điểm relevance.
    """
    records = _load()
    if not records:
        return []

    q_words = set(query.lower().split())
    q_tags  = {t.lower() for t in (tags or [])}
    scored  = []

    for r in records:
        score = 0
        text  = " ".join([
            r.get("title", ""),
            r.get("context", ""),
            r.get("problem", ""),
            r.get("solution", ""),
        ]).lower()
        r_tags = set(r.get("tags", []))

        # Điểm theo keyword trong text
        for word in q_words:
            if len(word) >= 3 and word in text:
                score += 1

        # Bonus: khớp tag
        if q_tags:
            tag_hits = len(q_tags & r_tags)
            score += tag_hits * 2

        # Bonus: từ khóa xuất hiện trong title/problem
        title_problem = (r.get("title","") + " " + r.get("problem","")).lower()
        for word in q_words:
            if len(word) >= 3 and word in title_problem:
                score += 1  # cộng thêm nếu khớp title/problem

        if score > 0:
            scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:top_k]]


# ─── Auto-extract ────────────────────────────────────────────────────────────

def auto_extract(user_message: str, ai_reply: str) -> list[dict]:
    """
    Dùng Groq/LLM để phân tích cặp (user_message, ai_reply) và tự động
    trích xuất các kinh nghiệm đáng lưu. Trả về list các record vừa tạo.
    Không raise — trả về [] nếu không có gì hoặc lỗi.
    """
    import os
    from groq import Groq

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return []

    # Bỏ qua các turn chỉ hỏi thông thường, không có code/giải pháp
    if len(ai_reply.strip()) < 200:
        return []

    client = Groq(api_key=api_key)
    system = """Bạn là assistant phân tích hội thoại lập trình để trích xuất kinh nghiệm tái sử dụng.

Nhiệm vụ: Đọc cặp (câu hỏi của user, câu trả lời của AI) và quyết định xem có pattern/giải pháp nào
ĐÁNG LƯU LẠI để dùng cho các lần sinh code tương lai không.

ChỈ trích xuất khi trả lời của AI chứa:
- Giải pháp kỹ thuật cụ thể (code, config, design pattern)
- Quy tắc coding / best practice rõ ràng
- Fix bug với nguyên nhân + cách giải
- Kiến trúc / cấu trúc module cụ thể

KHÔNG trích xuất khi:
- Chỉ giải thích lý thuyết chung chung
- Câu trả lời quá ngắn hoặc chỉ là hỏi thêm thông tin
- Nội dung quá project-specific, không tái dùng được

Trả về JSON (và chỉ JSON, không text khác):
{
  "should_save": true/false,
  "experiences": [
    {
      "title": "Tên ngắn gọn, rõ ràng (max 80 ký tự)",
      "context": "Ngôn ngữ/framework/công nghệ liên quan",
      "problem": "Mô tả vấn đề / pattern (2-4 câu)",
      "solution": "Giải pháp cốt lõi — giữ code quan trọng, bỏ boilerplate thừa (tối đa ~600 ký tự)",
      "tags": ["tag1", "tag2"]
    }
  ]
}

Nếu should_save=false thì experiences=[].
Tối đa 2 experiences mỗi lần."""

    user_prompt = f"""## Câu hỏi của user:
{user_message[:800]}

## Câu trả lời của AI:
{ai_reply[:2000]}

Hãy phân tích và trả về JSON."""

    try:
        resp = client.chat.completions.create(
            model="qwen/qwen3-32b",
            max_tokens=1000,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)
    except Exception as e:
        print(f"[AutoExtract] LLM error: {e}")
        return []

    if not data.get("should_save"):
        return []

    saved = []
    for exp in data.get("experiences", [])[:2]:
        title    = (exp.get("title") or "").strip()
        problem  = (exp.get("problem") or "").strip()
        solution = (exp.get("solution") or "").strip()
        if not title or not problem or not solution:
            continue
        record = add_experience(
            title=title,
            problem=problem,
            solution=solution,
            context=exp.get("context", ""),
            tags=exp.get("tags", []),
        )
        saved.append(record)
        print(f"[AutoExtract] Saved: '{title}'")

    return saved


def build_experience_prompt(query: str, tags: list[str] | None = None) -> str:
    """
    Tạo đoạn text inject vào system prompt chứa các kinh nghiệm liên quan.
    Trả về chuỗi rỗng nếu không có kinh nghiệm nào phù hợp.
    """
    hits = search_experiences(query, tags=tags, top_k=4)
    if not hits:
        return ""

    lines = ["\n\n## 📚 KINH NGHIỆM TÍCH LŨY (ưu tiên áp dụng):"]
    for i, exp in enumerate(hits, 1):
        lines.append(f"\n### [{i}] {exp['title']}")
        if exp.get("context"):
            lines.append(f"**Ngữ cảnh:** {exp['context']}")
        lines.append(f"**Vấn đề:** {exp['problem']}")
        lines.append(f"**Giải pháp:**\n{exp['solution']}")
        if exp.get("tags"):
            lines.append(f"**Tags:** {', '.join(exp['tags'])}")

    return "\n".join(lines)
