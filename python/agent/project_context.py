"""
ProjectContext - Phan tich du an de xay dung context giau thong tin:
  - Ngon ngu, framework, build tool, dependencies
  - Cau truc thu muc, naming conventions
  - Cac file quan trong (config, entry-point, interface chinh)
  - Coding style hien tai (indent, package/module structure)
  - Tinh nang chinh cua du an (do LLM phan tich tu README + code)

Context nay duoc inject vao moi system prompt de AI sinh code
nhat quan voi phong cach & kien truc hien co cua du an.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional

try:
    from groq import Groq as _Groq
except ImportError:
    _Groq = None

# --- Config -------------------------------------------------------------------

CACHE_FILE   = Path(__file__).parent.parent / "data" / "project_context_cache.json"
IGNORE_DIRS  = {
    'node_modules', '.git', 'dist', 'build', 'target', '__pycache__',
    '.idea', '.vscode', 'venv', '.venv', 'out', 'bin', 'obj',
    '.gradle', '.mvn', '.next', '.nuxt', 'coverage', '.pytest_cache',
}
IGNORE_EXTS  = {'.class', '.pyc', '.pyo', '.o', '.so', '.dll', '.exe',
                '.jar', '.war', '.zip', '.tar', '.gz', '.lock', '.log'}
MAX_FILE_PREVIEW = 60
MAX_KEY_FILES    = 12

# --- Helpers ------------------------------------------------------------------

def _file_exists(root: Path, *names) -> Optional[Path]:
    for name in names:
        p = root / name
        if p.exists():
            return p
    return None


def _read_first_match(all_files: list[Path], names: list[str], lines: int = MAX_FILE_PREVIEW) -> Optional[str]:
    for name in names:
        for f in all_files:
            if f.name.lower() == name.lower():
                try:
                    content = f.read_text(encoding='utf-8', errors='ignore')
                    return '\n'.join(content.splitlines()[:lines])
                except Exception:
                    pass
    return None


def _collect_files(root: Path) -> list[Path]:
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in IGNORE_DIRS and not d.startswith('.')
        ]
        for fname in filenames:
            p = Path(dirpath) / fname
            if p.suffix.lower() not in IGNORE_EXTS:
                result.append(p)
    return result


def _project_hash(root: Path) -> str:
    files = sorted(_collect_files(root))[:200]
    h = hashlib.md5()
    for f in files:
        try:
            h.update(f.name.encode())
            h.update(str(int(f.stat().st_mtime)).encode())
        except Exception:
            pass
    return h.hexdigest()[:12]


# --- Detector: Stack ----------------------------------------------------------

def _detect_stack(root: Path, all_files: list[Path]) -> dict:
    names = {f.name.lower() for f in all_files}
    stack = {
        "languages":   [],
        "frameworks":  [],
        "build_tools": [],
        "databases":   [],
        "others":      [],
    }

    ext_count: dict[str, int] = {}
    for f in all_files:
        ext = f.suffix.lower()
        if ext and ext not in IGNORE_EXTS:
            ext_count[ext] = ext_count.get(ext, 0) + 1

    lang_map = {
        '.java': 'Java', '.kt': 'Kotlin', '.scala': 'Scala',
        '.py':   'Python', '.go': 'Go', '.rs': 'Rust',
        '.ts':   'TypeScript', '.tsx': 'TypeScript/React',
        '.js':   'JavaScript', '.jsx': 'JavaScript/React',
        '.cs':   'C#', '.cpp': 'C++', '.c': 'C',
        '.rb':   'Ruby', '.php': 'PHP', '.swift': 'Swift',
    }
    sorted_exts = sorted(ext_count.items(), key=lambda x: x[1], reverse=True)
    seen_langs: set[str] = set()
    for ext, _ in sorted_exts:
        lang = lang_map.get(ext)
        if lang and lang not in seen_langs:
            stack["languages"].append(lang)
            seen_langs.add(lang)
        if len(stack["languages"]) >= 3:
            break

    if 'pom.xml' in names:
        stack["build_tools"].append("Maven")
    if 'build.gradle' in names or 'build.gradle.kts' in names:
        stack["build_tools"].append("Gradle")
    if 'package.json' in names:
        stack["build_tools"].append("npm/Node")
    if 'cargo.toml' in names:
        stack["build_tools"].append("Cargo")
    if 'go.mod' in names:
        stack["build_tools"].append("Go Modules")
    if 'pyproject.toml' in names or 'setup.py' in names:
        stack["build_tools"].append("Python build")
    if 'requirements.txt' in names:
        stack["build_tools"].append("pip")
    if 'makefile' in names:
        stack["build_tools"].append("Make")

    if any(('spring' in f.name.lower()
            or f.name.lower() in ('application.yml', 'application.properties'))
           for f in all_files):
        if '.java' in ext_count or '.kt' in ext_count:
            stack["frameworks"].append("Spring Boot")

    if '.py' in ext_count:
        src = _read_first_match(all_files, ['main.py', 'app.py', 'server.py'], lines=30)
        if src:
            low = src.lower()
            if 'fastapi' in low:
                stack["frameworks"].append("FastAPI")
            elif 'flask' in low:
                stack["frameworks"].append("Flask")
            elif 'django' in low:
                stack["frameworks"].append("Django")

    pkg = _file_exists(root, 'package.json')
    if pkg:
        try:
            pkg_data = json.loads(pkg.read_text(encoding='utf-8', errors='ignore'))
            deps = {**pkg_data.get('dependencies', {}), **pkg_data.get('devDependencies', {})}
            if 'next' in deps:
                stack["frameworks"].append("Next.js")
            elif 'react' in deps:
                stack["frameworks"].append("React")
            if 'vue' in deps:
                stack["frameworks"].append("Vue")
            if '@angular' in ' '.join(deps):
                stack["frameworks"].append("Angular")
            if 'vite' in deps:
                stack["others"].append("Vite")
            if 'tailwindcss' in deps:
                stack["others"].append("Tailwind CSS")
            if 'zustand' in deps:
                stack["others"].append("Zustand")
            if 'axios' in deps:
                stack["others"].append("Axios")
        except Exception:
            pass

    if 'dockerfile' in names:
        stack["others"].append("Docker")
    if any('docker-compose' in n for n in names):
        stack["others"].append("Docker Compose")
    if any('helm' in str(f).lower() or 'chart.yaml' in f.name.lower() for f in all_files):
        stack["others"].append("Helm/K8s")

    config_text = _read_first_match(
        all_files,
        ['application.yml', 'application.yaml', 'application.properties',
         '.env', 'config.py', 'settings.py'],
        lines=80,
    ) or ''
    low = config_text.lower()
    if 'postgresql' in low or 'postgres' in low: stack["databases"].append("PostgreSQL")
    if 'mysql' in low:                           stack["databases"].append("MySQL")
    if 'mongodb' in low or 'mongo' in low:       stack["databases"].append("MongoDB")
    if 'redis' in low:                           stack["databases"].append("Redis")
    if 'kafka' in low:                           stack["databases"].append("Kafka")
    if 'elasticsearch' in low:                   stack["databases"].append("Elasticsearch")

    for k in stack:
        stack[k] = list(dict.fromkeys(stack[k]))

    return stack


# --- Detector: Key files ------------------------------------------------------

def _pick_key_files(root: Path, all_files: list[Path], stack: dict) -> list[dict]:
    priority_names = [
        'pom.xml', 'build.gradle', 'build.gradle.kts', 'package.json',
        'application.yml', 'application.yaml', 'application.properties',
        'docker-compose.yml', 'docker-compose.yaml', 'dockerfile',
        '.env_exemple', 'requirements.txt', 'pyproject.toml',
        'main.py', 'app.py', 'server.py', 'main.java', 'application.java',
        'index.js', 'index.ts', 'main.ts', 'main.js',
        'router.js', 'router.ts', 'routes.py',
    ]

    chosen: list[Path] = []
    seen: set[str] = set()

    for name in priority_names:
        for f in all_files:
            if f.name.lower() == name.lower() and str(f) not in seen:
                chosen.append(f)
                seen.add(str(f))
        if len(chosen) >= MAX_KEY_FILES // 2:
            break

    keywords = ['service', 'controller', 'repository', 'agent', 'config',
                'gateway', 'handler', 'middleware', 'store', 'hook']
    for f in all_files:
        if len(chosen) >= MAX_KEY_FILES:
            break
        if any(kw in f.name.lower() for kw in keywords) and str(f) not in seen:
            chosen.append(f)
            seen.add(str(f))

    result = []
    for f in chosen[:MAX_KEY_FILES]:
        try:
            file_lines = f.read_text(encoding='utf-8', errors='ignore').splitlines()
            preview    = '\n'.join(file_lines[:MAX_FILE_PREVIEW])
            rel        = str(f.relative_to(root))
            result.append({"path": rel, "lines": len(file_lines), "preview": preview})
        except Exception:
            pass

    return result


# --- Detector: Conventions ----------------------------------------------------

def _detect_conventions(all_files: list[Path], key_files: list[dict]) -> dict:
    conventions = {}

    indent_spaces = indent_tabs = 0
    for kf in key_files[:6]:
        for line in kf["preview"].splitlines()[:30]:
            if line.startswith('    '): indent_spaces += 1
            elif line.startswith('\t'): indent_tabs += 1
    conventions["indent"] = "4 spaces" if indent_spaces >= indent_tabs else (
        "tabs" if indent_tabs > 0 else "2 spaces"
    )

    has_src = any('src' in str(f) for f in all_files[:50])
    has_pkg = any('com.' in str(f) or 'org.' in str(f) for f in all_files[:50])
    conventions["structure"] = (
        "Maven/Gradle standard (src/main/java)" if has_pkg else
        "src/ based" if has_src else
        "flat"
    )

    java_stems = [f.stem for f in all_files if f.suffix in ('.java', '.kt')][:30]
    naming = []
    if any('Impl' in n for n in java_stems):            naming.append("ServiceImpl pattern")
    if any('Dto' in n or 'DTO' in n for n in java_stems): naming.append("DTO objects")
    if any('Vo' in n or 'VO' in n for n in java_stems):   naming.append("Value Objects")
    if naming:
        conventions["naming"] = ", ".join(naming)

    return conventions


# --- LLM: Feature description -------------------------------------------------

def _describe_features(root: Path, all_files: list[Path], key_files: list[dict], stack: dict) -> str:
    """
    Dung LLM de tom tat cac tinh nang chinh cua project.
    Uu tien doc README, sau do dung key files lam context.
    Tra ve JSON string. Khong raise - tra ve "" neu loi.
    """
    if _Groq is None:
        return ""

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return ""

    sections: list[str] = []

    # 1. README
    for readme_name in ['readme.md', 'readme.txt', 'readme.rst', 'readme']:
        for f in all_files:
            if f.name.lower() == readme_name:
                try:
                    txt = f.read_text(encoding='utf-8', errors='ignore')[:3000]
                    sections.append("## README:\n" + txt)
                    break
                except Exception:
                    pass
        if sections:
            break

    # 2. Key files (service, controller, router...)
    code_snippets: list[str] = []
    priority_kw = ['service', 'controller', 'router', 'routes', 'agent', 'handler', 'api']
    for kf in key_files:
        if any(kw in kf['path'].lower() for kw in priority_kw):
            code_snippets.append("### " + kf['path'] + ":\n" + kf['preview'][:500])
        if len(code_snippets) >= 5:
            break

    if code_snippets:
        sections.append("## Code snippets:\n" + "\n\n".join(code_snippets))

    stack_info = ", ".join(
        stack.get("frameworks", []) +
        stack.get("languages", []) +
        stack.get("databases", [])
    )
    sections.append("## Tech stack: " + stack_info)
    sections.append("## Ten project: " + root.name)

    context_text = "\n\n".join(sections)[:4000]

    print(f"[ProjectContext] Generating feature description for {root.name}...")
    try:
        client = _Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="qwen/qwen3-32b",
            max_tokens=600,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ban la ky su phan tich code. "
                        "Dua vao README va code, mo ta ngan gon cac tinh nang chinh cua project bang tieng Viet. "
                        'Tra ve JSON: {"description": "1 cau tom tat", '
                        '"features": ["tinh nang 1", "tinh nang 2", ...] (toi da 8), '
                        '"domain": "linh vuc (VD: e-commerce, DevTool, SaaS...)"}. '
                        "Chi JSON, khong text khac. /no_think"
                    ),
                },
                {
                    "role": "user",
                    "content": context_text,
                },
            ],
            response_format={"type": "json_object"},
        )
        raw  = resp.choices[0].message.content
        data = json.loads(raw)
        description = data.get("description", "")
        features    = data.get("features", [])
        domain      = data.get("domain", "")
        print(f"[ProjectContext] Features: {features}")
        return json.dumps(
            {"description": description, "features": features, "domain": domain},
            ensure_ascii=False,
        )
    except Exception as e:
        print(f"[ProjectContext] Feature description error: {e}")
        return ""


# --- Cache --------------------------------------------------------------------

def _load_cache() -> dict:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')


# --- Public API ---------------------------------------------------------------

def scan_project(project_path: str, force: bool = False) -> dict:
    """
    Scan project va tra ve context dict. Co cache theo project hash.
    force=True de re-scan du cache con hop le.
    """
    root  = Path(project_path).resolve()
    cache = _load_cache()
    key   = str(root)
    phash = _project_hash(root)

    if not force and key in cache and cache[key].get("hash") == phash:
        print(f"[ProjectContext] Cache hit: {root.name}")
        return cache[key]["context"]

    print(f"[ProjectContext] Scanning: {root}")
    all_files    = _collect_files(root)
    stack        = _detect_stack(root, all_files)
    key_files    = _pick_key_files(root, all_files, stack)
    conventions  = _detect_conventions(all_files, key_files)
    features_raw = _describe_features(root, all_files, key_files, stack)

    features_data: dict = {}
    if features_raw:
        try:
            features_data = json.loads(features_raw)
        except Exception:
            pass

    ext_count: dict[str, int] = {}
    for f in all_files:
        ext = f.suffix.lower()
        if ext:
            ext_count[ext] = ext_count.get(ext, 0) + 1

    ctx = {
        "project_name": root.name,
        "project_root": str(root),
        "total_files":  len(all_files),
        "stack":        stack,
        "conventions":  conventions,
        "features":     features_data,
        "key_files":    key_files,
        "ext_stats":    dict(sorted(ext_count.items(), key=lambda x: x[1], reverse=True)[:10]),
    }

    cache[key] = {"hash": phash, "context": ctx}
    _save_cache(cache)
    print(f"[ProjectContext] Done: {len(all_files)} files, frameworks={stack['frameworks']}, features={len(features_data.get('features', []))}")
    return ctx


def build_context_prompt(ctx: dict, budget: int = 2500) -> str:
    """
    Chuyen project context thanh doan text inject vao system prompt.
    Thu tu: features -> stack -> conventions -> key files.
    budget: gioi han ky tu toi da.
    """
    if not ctx:
        return ""

    lines: list[str] = []
    stack = ctx.get("stack", {})
    conv  = ctx.get("conventions", {})
    feat  = ctx.get("features", {})

    # Header
    lines.append(f"\n\n## PROJECT CONTEXT: {ctx.get('project_name', 'Unknown')}")
    lines.append(f"Root: {ctx.get('project_root', '')} | Files: {ctx.get('total_files', 0)}")

    # --- Features: inject truoc de AI hieu muc dich project ---
    if feat:
        if feat.get("domain"):
            lines.append(f"Linh vuc: {feat['domain']}")
        if feat.get("description"):
            lines.append(f"Mo ta: {feat['description']}")
        if feat.get("features"):
            lines.append("Tinh nang chinh: " + " | ".join(feat["features"]))

    # --- Stack ---
    if stack.get("languages"):   lines.append("Ngon ngu: "  + ", ".join(stack["languages"]))
    if stack.get("frameworks"):  lines.append("Framework: " + ", ".join(stack["frameworks"]))
    if stack.get("build_tools"): lines.append("Build: "     + ", ".join(stack["build_tools"]))
    if stack.get("databases"):   lines.append("DB/Infra: "  + ", ".join(stack["databases"]))
    if stack.get("others"):      lines.append("Khac: "      + ", ".join(stack["others"]))

    # --- Conventions ---
    if conv:
        conv_parts = []
        if conv.get("indent"):    conv_parts.append("indent=" + conv["indent"])
        if conv.get("structure"): conv_parts.append("structure=" + conv["structure"])
        if conv.get("naming"):    conv_parts.append(conv["naming"])
        if conv_parts:
            lines.append("Conventions: " + " | ".join(conv_parts))

    lines.append("\nKey files (preview):")

    # --- Key files preview ---
    used      = sum(len(l) for l in lines)
    key_files = ctx.get("key_files", [])
    for idx, kf in enumerate(key_files):
        chunk = f"\n[{kf['path']} ({kf['lines']} lines)]\n```\n{kf['preview'][:400]}\n```"
        if used + len(chunk) > budget:
            lines.append(f"\n(+{len(key_files) - idx} files nua, da dat gioi han)")
            break
        lines.append(chunk)
        used += len(chunk)

    return "\n".join(lines)


def invalidate_cache(project_path: str) -> None:
    """Xoa cache cua project (goi khi user muon force re-scan)."""
    cache = _load_cache()
    key   = str(Path(project_path).resolve())
    if key in cache:
        del cache[key]
        _save_cache(cache)
