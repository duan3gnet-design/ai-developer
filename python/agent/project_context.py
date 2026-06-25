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

CACHE_FILE  = Path(__file__).parent.parent / "data" / "project_context_cache.json"
IGNORE_DIRS = {
    'node_modules', '.git', 'dist', 'build', 'target', '__pycache__',
    '.idea', '.vscode', 'venv', '.venv', 'out', 'bin', 'obj',
    '.gradle', '.mvn', '.next', '.nuxt', 'coverage', '.pytest_cache',
    'generated-sources', 'generated', '.terraform', 'vendor',
}
IGNORE_EXTS = {
    '.class', '.pyc', '.pyo', '.o', '.so', '.dll', '.exe',
    '.jar', '.war', '.zip', '.tar', '.gz', '.lock', '.log',
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
    '.woff', '.woff2', '.ttf', '.eot', '.map',
}
# Chi dem SOURCE_EXTS khi thong ke ngon ngu, tranh nhieu tu .xml, .yml...
SOURCE_EXTS = {
    '.java', '.kt', '.scala',
    '.py',
    '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs',
    '.go', '.rs', '.cs', '.cpp', '.c', '.rb', '.php', '.swift',
}
MAX_FILE_PREVIEW = 60
MAX_KEY_FILES    = 12

# --- Helpers ------------------------------------------------------------------

def _file_exists(root: Path, *names) -> Optional[Path]:
    for name in names:
        p = root / name
        if p.exists():
            return p
    return None


def _build_name_index(all_files: list[Path]) -> dict[str, list[Path]]:
    """Index: ten file (lower) -> danh sach Path. Tranh O(n*m) khi tim theo ten."""
    idx: dict[str, list[Path]] = {}
    for f in all_files:
        idx.setdefault(f.name.lower(), []).append(f)
    return idx


def _read_file_safe(path: Path, max_lines: int = MAX_FILE_PREVIEW) -> Optional[str]:
    try:
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
        return '\n'.join(lines[:max_lines])
    except Exception:
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


def _project_hash(root: Path, all_files: list[Path]) -> str:
    """Hash toan bo file (khong gioi han 200). Dung ten + mtime."""
    h = hashlib.md5()
    for f in sorted(all_files):
        try:
            h.update(str(f.relative_to(root)).encode())
            h.update(str(int(f.stat().st_mtime)).encode())
        except Exception:
            pass
    return h.hexdigest()[:16]


# --- Detector: Stack ----------------------------------------------------------

def _detect_stack(root: Path, all_files: list[Path], name_idx: dict) -> dict:
    """
    Nhan dien stack. Dung name_idx O(1), chi dem SOURCE_EXTS cho ngon ngu,
    detect Spring Boot bang noi dung file thay vi ten file.
    """
    stack = {"languages": [], "frameworks": [], "build_tools": [], "databases": [], "others": []}

    # --- Ngon ngu: chi dem source extensions ---
    ext_count: dict[str, int] = {}
    for f in all_files:
        ext = f.suffix.lower()
        if ext in SOURCE_EXTS:
            ext_count[ext] = ext_count.get(ext, 0) + 1

    lang_map = {
        '.java': 'Java', '.kt': 'Kotlin', '.scala': 'Scala',
        '.py': 'Python', '.go': 'Go', '.rs': 'Rust',
        '.ts': 'TypeScript', '.tsx': 'TypeScript/React',
        '.js': 'JavaScript', '.jsx': 'JavaScript/React',
        '.cs': 'C#', '.cpp': 'C++', '.c': 'C',
        '.rb': 'Ruby', '.php': 'PHP', '.swift': 'Swift',
    }
    seen_langs: set[str] = set()
    for ext, _ in sorted(ext_count.items(), key=lambda x: x[1], reverse=True):
        lang = lang_map.get(ext)
        if lang and lang not in seen_langs:
            stack["languages"].append(lang)
            seen_langs.add(lang)
        if len(stack["languages"]) >= 3:
            break

    # --- Build tools: uu tien file o root ---
    def at_root(*names) -> bool:
        return any(p.parent == root for n in names for p in name_idx.get(n.lower(), []))

    def anywhere(*names) -> bool:
        return any(n.lower() in name_idx for n in names)

    if at_root('pom.xml'):                           stack["build_tools"].append("Maven")
    if at_root('build.gradle', 'build.gradle.kts'):  stack["build_tools"].append("Gradle")
    if at_root('package.json'):                      stack["build_tools"].append("npm/Node")
    if at_root('cargo.toml'):                        stack["build_tools"].append("Cargo")
    if at_root('go.mod'):                            stack["build_tools"].append("Go Modules")
    if at_root('pyproject.toml', 'setup.py'):        stack["build_tools"].append("Python build")
    if at_root('requirements.txt'):                  stack["build_tools"].append("pip")
    if anywhere('makefile', 'GNUmakefile'):          stack["build_tools"].append("Make")

    # --- Spring Boot: detect bang noi dung, khong phai ten file ---
    if ext_count.get('.java', 0) + ext_count.get('.kt', 0) > 0:
        spring = False
        for cfg in ('application.yml', 'application.yaml', 'application.properties'):
            for p in sorted(name_idx.get(cfg, []), key=lambda x: len(x.parts)):
                txt = _read_file_safe(p, max_lines=5) or ''
                if 'spring:' in txt or 'server:' in txt or 'spring.' in txt:
                    spring = True; break
            if spring: break
        if not spring:
            for p in name_idx.get('pom.xml', []):
                if 'spring-boot' in (_read_file_safe(p, max_lines=60) or '').lower():
                    spring = True; break
        if spring:
            stack["frameworks"].append("Spring Boot")

    # --- FastAPI / Flask / Django ---
    if ext_count.get('.py', 0) > 0:
        found_py_fw = False
        for entry in ('main.py', 'app.py', 'server.py'):
            for p in name_idx.get(entry, []):
                txt = (_read_file_safe(p, max_lines=30) or '').lower()
                if 'fastapi' in txt:
                    stack["frameworks"].append("FastAPI"); found_py_fw = True; break
                elif 'flask' in txt:
                    stack["frameworks"].append("Flask");   found_py_fw = True; break
                elif 'django' in txt:
                    stack["frameworks"].append("Django");  found_py_fw = True; break
            if found_py_fw: break

    # --- React / Vue / Angular / Next: chi doc root package.json ---
    for p in name_idx.get('package.json', []):
        if p.parent != root: continue
        try:
            pkg  = json.loads(p.read_text(encoding='utf-8', errors='ignore'))
            deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
            if 'next'    in deps:  stack["frameworks"].append("Next.js")
            elif 'react' in deps:  stack["frameworks"].append("React")
            if 'vue'     in deps:  stack["frameworks"].append("Vue")
            if any(k.startswith('@angular') for k in deps): stack["frameworks"].append("Angular")
            for lib, label in [('vite','Vite'),('tailwindcss','Tailwind CSS'),
                                ('zustand','Zustand'),('axios','Axios'),('electron','Electron')]:
                if lib in deps: stack["others"].append(label)
        except Exception: pass
        break

    if anywhere('Dockerfile', 'dockerfile'):                  stack["others"].append("Docker")
    if anywhere('docker-compose.yml', 'docker-compose.yaml'): stack["others"].append("Docker Compose")
    if anywhere('Chart.yaml', 'values.yaml'):                 stack["others"].append("Helm/K8s")

    # --- Databases: doc config files gan root nhat ---
    config_text = ''
    for cfg in ('application.yml','application.yaml','application.properties',
                '.env','config.py','settings.py','database.py'):
        for p in sorted(name_idx.get(cfg, []), key=lambda x: len(x.parts))[:2]:
            config_text += (_read_file_safe(p, max_lines=80) or '') + '\n'

    low = config_text.lower()
    for kw, label in [('postgresql','PostgreSQL'),('postgres','PostgreSQL'),
                      ('mysql','MySQL'),('mongodb','MongoDB'),('mongo','MongoDB'),
                      ('redis','Redis'),('kafka','Kafka'),
                      ('elasticsearch','Elasticsearch'),('sqlite','SQLite')]:
        if kw in low and label not in stack["databases"]:
            stack["databases"].append(label)

    for k in stack:
        stack[k] = list(dict.fromkeys(stack[k]))
    return stack


# --- Detector: Key files ------------------------------------------------------

def _pick_key_files(root: Path, all_files: list[Path],
                    name_idx: dict, stack: dict) -> list[dict]:
    """
    Dung name_idx O(1). Uu tien file gan root (depth nho).
    Tranh chon nhieu file cung ten o nested folder.
    """
    priority_names = [
        'pom.xml','build.gradle','build.gradle.kts','package.json',
        'application.yml','application.yaml','application.properties',
        'docker-compose.yml','docker-compose.yaml','dockerfile',
        '.env','.env_exemple','requirements.txt','pyproject.toml',
        'main.py','app.py','server.py',
        'Main.java','Application.java',
        'index.js','index.ts','main.ts','main.js','main.jsx',
        'router.js','router.ts','routes.py','urls.py',
        'settings.py','config.py',
    ]
    chosen: list[Path] = []
    seen:   set[str]   = set()

    for name in priority_names:
        if len(chosen) >= MAX_KEY_FILES: break
        candidates = sorted(name_idx.get(name.lower(), []), key=lambda p: len(p.parts))
        if candidates:
            p = candidates[0]
            if str(p) not in seen:
                chosen.append(p); seen.add(str(p))

    if len(chosen) < MAX_KEY_FILES:
        keywords  = ['service','controller','repository','agent','gateway',
                     'handler','middleware','store','hook','filter','interceptor']
        src_files = sorted(
            [f for f in all_files if f.suffix.lower() in SOURCE_EXTS],
            key=lambda f: len(f.parts)
        )
        for f in src_files:
            if len(chosen) >= MAX_KEY_FILES: break
            if any(kw in f.name.lower() for kw in keywords) and str(f) not in seen:
                chosen.append(f); seen.add(str(f))

    result = []
    for f in chosen[:MAX_KEY_FILES]:
        txt = _read_file_safe(f, MAX_FILE_PREVIEW)
        if txt is None: continue
        try:
            total = len(f.read_text(encoding='utf-8', errors='ignore').splitlines())
            rel   = str(f.relative_to(root))
            result.append({"path": rel, "lines": total, "preview": txt})
        except Exception: pass
    return result


# --- Detector: Conventions ----------------------------------------------------

def _detect_conventions(all_files: list[Path], key_files: list[dict]) -> dict:
    conventions = {}

    indent_spaces = indent_tabs = 0
    for kf in key_files[:8]:
        for line in kf["preview"].splitlines()[:40]:
            if line.startswith('    '): indent_spaces += 1
            elif line.startswith('\t'): indent_tabs += 1
    conventions["indent"] = "4 spaces" if indent_spaces >= indent_tabs else (
        "tabs" if indent_tabs > 0 else "2 spaces"
    )

    # Kiem tra toan bo path, khong gioi han 50
    sep      = os.sep
    paths    = [str(f) for f in all_files]
    has_main = any(f'{sep}main{sep}java' in p or f'{sep}main{sep}kotlin' in p for p in paths)
    has_pkg  = any(f'{sep}com{sep}' in p or f'{sep}org{sep}' in p for p in paths)
    has_src  = any(f'{sep}src{sep}' in p for p in paths)
    conventions["structure"] = (
        "Maven/Gradle standard (src/main/java)" if has_main or has_pkg else
        "src/ based" if has_src else "flat"
    )

    java_stems = [f.stem for f in all_files if f.suffix in ('.java', '.kt')]
    naming = []
    for check, label in [
        (lambda n: 'Impl'       in n, "ServiceImpl pattern"),
        (lambda n: 'Dto' in n or 'DTO' in n, "DTO objects"),
        (lambda n: 'Entity'     in n, "Entity classes"),
        (lambda n: 'Repository' in n, "Repository pattern"),
    ]:
        if any(check(n) for n in java_stems):
            naming.append(label)
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
    root      = Path(project_path).resolve()
    cache     = _load_cache()
    key       = str(root)
    all_files = _collect_files(root)
    phash     = _project_hash(root, all_files)   # hash toan bo, khong gioi han

    if not force and key in cache:
        print(f"[ProjectContext] Cache hit: {root.name} ({len(all_files)} files)")
        return cache[key]["context"]

    print(f"[ProjectContext] Scanning: {root} ({len(all_files)} files)")
    name_idx     = _build_name_index(all_files)        # build 1 lan, dung lai
    stack        = _detect_stack(root, all_files, name_idx)
    key_files    = _pick_key_files(root, all_files, name_idx, stack)
    conventions  = _detect_conventions(all_files, key_files)
    features_raw = _describe_features(root, all_files, key_files, stack)

    features_data: dict = {}
    if features_raw:
        try: features_data = json.loads(features_raw)
        except Exception: pass

    # Chi dem SOURCE_EXTS cho ext_stats
    ext_count: dict[str, int] = {}
    for f in all_files:
        ext = f.suffix.lower()
        if ext in SOURCE_EXTS:
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
    print(f"[ProjectContext] Done: frameworks={stack['frameworks']}, features={len(features_data.get('features', []))}")
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
