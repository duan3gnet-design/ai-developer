"""
CodeReader — đọc và parse project từ filesystem
"""

import os
import json
from pathlib import Path
from typing import Optional

# Extensions được coi là text/code
TEXT_EXTENSIONS = {
    '.java', '.py', '.js', '.ts', '.tsx', '.jsx', '.kt',
    '.xml', '.yml', '.yaml', '.json', '.properties',
    '.sql', '.md', '.txt', '.gradle', '.sh', '.env',
    '.html', '.css', '.scss', '.rs', '.go', '.toml'
}

# Thư mục bỏ qua
IGNORE_DIRS = {
    'node_modules', '.git', 'dist', 'build', 'target',
    '__pycache__', '.idea', '.vscode', 'venv', '.venv',
    'out', 'bin', 'obj', '.gradle', '.mvn'
}

MAX_FILE_SIZE = 500_000  # 500KB


class CodeReader:

    def read_project(self, root_path: str, max_files: int = 50) -> dict:
        root = Path(root_path)
        if not root.exists():
            return {"error": f"Path không tồn tại: {root_path}"}
        tree = self._build_tree(root)
        files = self._collect_files(root, max_files)
        return {
            "root": str(root),
            "name": root.name,
            "tree": tree,
            "files": files,
            "total_files": len(files),
            "languages": self._detect_languages(files)
        }

    def summarize_project(self, root_path: str) -> dict:
        data = self.read_project(root_path, max_files=30)
        if "error" in data:
            return data
        summarized_files = []
        for f in data["files"]:
            content = f.get("content", "")
            lines = content.splitlines()
            truncated = len(lines) > 200
            summarized_files.append({
                "path": f["path"],
                "name": f["name"],
                "relative_path": f["relative_path"],
                "language": f["language"],
                "lines": len(lines),
                "content": "\n".join(lines[:200]) + ("\n... (truncated)" if truncated else "")
            })
        return {
            "root": data["root"],
            "name": data["name"],
            "total_files": data["total_files"],
            "languages": data["languages"],
            "files": summarized_files,
            # tree_text giờ in path tuyệt đối để AI biết chính xác cần xóa/sửa file nào
            "tree_text": self._tree_to_text(data["tree"])
        }

    def get_tree_text(self, root_path: str) -> str:
        """Chỉ lấy cây thư mục dạng text (dùng để inject vào system prompt)."""
        root = Path(root_path)
        if not root.exists():
            return f"(Không tìm thấy: {root_path})"
        tree = self._build_tree(root)
        return self._tree_to_text(tree)

    def read_file(self, file_path: str) -> dict:
        path = Path(file_path)
        if not path.exists():
            return {"error": "File không tồn tại"}
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return {
                "path": str(path),
                "name": path.name,
                "content": content,
                "lines": len(content.splitlines()),
                "language": self._detect_language(path.suffix)
            }
        except Exception as e:
            return {"error": str(e)}

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _build_tree(self, root: Path, depth: int = 0, max_depth: int = 6) -> list:
        if depth > max_depth:
            return []
        items = []
        try:
            for entry in sorted(root.iterdir(), key=lambda e: (e.is_file(), e.name)):
                if entry.name in IGNORE_DIRS or entry.name.startswith('.'):
                    continue
                if entry.is_dir():
                    items.append({
                        "name": entry.name,
                        "type": "dir",
                        "path": str(entry),
                        "children": self._build_tree(entry, depth + 1, max_depth)
                    })
                else:
                    items.append({
                        "name": entry.name,
                        "type": "file",
                        "path": str(entry),
                        "ext": entry.suffix
                    })
        except PermissionError:
            pass
        return items

    def _collect_files(self, root: Path, max_files: int) -> list:
        files = []
        for path in root.rglob("*"):
            if len(files) >= max_files:
                break
            if path.is_file() and path.suffix in TEXT_EXTENSIONS:
                if any(part in IGNORE_DIRS for part in path.parts):
                    continue
                if path.stat().st_size > MAX_FILE_SIZE:
                    continue
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    files.append({
                        "path": str(path),
                        "name": path.name,
                        "relative_path": str(path.relative_to(root)),
                        "content": content,
                        "lines": len(content.splitlines()),
                        "language": self._detect_language(path.suffix)
                    })
                except Exception:
                    continue
        return files

    def _detect_language(self, ext: str) -> str:
        mapping = {
            ".java": "java", ".py": "python", ".js": "javascript",
            ".ts": "typescript", ".tsx": "tsx", ".jsx": "jsx",
            ".kt": "kotlin", ".xml": "xml", ".yml": "yaml",
            ".yaml": "yaml", ".json": "json", ".sql": "sql",
            ".md": "markdown", ".gradle": "groovy", ".sh": "bash",
            ".html": "html", ".css": "css", ".rs": "rust", ".go": "go"
        }
        return mapping.get(ext.lower(), "text")

    def _detect_languages(self, files: list) -> dict:
        langs = {}
        for f in files:
            lang = f.get("language", "text")
            langs[lang] = langs.get(lang, 0) + 1
        return dict(sorted(langs.items(), key=lambda x: -x[1]))

    def _tree_to_text(self, tree: list, indent: int = 0) -> str:
        """In cây thư mục với PATH TUYỆT ĐỐI để AI biết chính xác đường dẫn."""
        lines = []
        for item in tree:
            pad = "  " * indent
            if item["type"] == "dir":
                lines.append(f"{pad}[DIR]  {item['path']}")
                child_text = self._tree_to_text(item.get("children", []), indent + 1)
                if child_text:
                    lines.append(child_text)
            else:
                lines.append(f"{pad}[FILE] {item['path']}")
        return "\n".join(lines)
