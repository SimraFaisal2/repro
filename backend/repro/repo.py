"""Repository acquisition + static analysis.

Acquisition: clone a GitHub URL, copy an uploaded/local directory.
Analysis: language/framework/package-manager/test-framework detection,
file counts, a pruned structure tree, and a module import graph —
all derived from real static inspection, never fabricated.
"""
from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

from .config import cfg

IGNORE_DIRS = {".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "env",
               "node_modules", "dist", "build", ".next", ".pytest_cache",
               ".mypy_cache", ".ruff_cache", "htmlcov", ".idea", ".vscode",
               ".repro", "target", ".tox"}
IGNORE_FILES = {"*.pyc", "*.pyo", ".DS_Store", "*.egg-info", ".coverage"}


# ------------------------------------------------------------------ acquire
def clone_repo(url: str, dest: Path) -> None:
    """Shallow clone a git repository. Raises on failure."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1", "--quiet", url, str(dest)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"git clone failed: {proc.stderr.strip()[:500]}")


def copy_dir(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _ignore(directory: str, names: list[str]) -> list[str]:
        ignored = []
        for n in names:
            p = Path(directory) / n
            if p.is_dir() and n in IGNORE_DIRS:
                ignored.append(n)
            elif n.endswith(".pyc") or n in (".DS_Store",):
                ignored.append(n)
        return ignored

    shutil.copytree(src, dest, ignore=_ignore, dirs_exist_ok=True)


# ----------------------------------------------------------------- analysis
def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _walk(root: Path) -> list[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in filenames:
            if f.endswith((".pyc", ".pyo")) or f == ".DS_Store":
                continue
            out.append(Path(dirpath) / f)
    return out


def _is_test_path(p: Path, root: Path) -> bool:
    rel = str(p.relative_to(root)).replace("\\", "/")
    return ("/test" in rel or "/tests" in rel or rel.startswith("test") or
            rel.startswith("tests") or p.name.startswith("test_") or p.name.startswith("tests_"))


def detect_python_version(root: Path) -> str:
    pf = root / ".python-version"
    if pf.exists():
        v = _read(pf).strip()
        if v:
            return v
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        m = re.search(r'requires-python\s*=\s*["\']([^"\']+)', _read(pyproject))
        if m:
            return m.group(1)
    return "3.11"


def detect_package_manager(root: Path) -> str:
    if (root / "uv.lock").exists():
        return "uv"
    if (root / "poetry.lock").exists():
        return "poetry"
    if (root / "Pipfile").exists():
        return "pipenv"
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        return "pip"
    return "none"


def detect_framework(root: Path) -> str:
    imports: set[str] = set()
    for p in _walk(root):
        if p.suffix != ".py":
            continue
        try:
            tree = ast.parse(_read(p))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.add(node.names[0].name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
    for fw, sig in [("FastAPI", "fastapi"), ("Flask", "flask"), ("Django", "django"),
                    ("PyTorch", "torch"), ("TensorFlow", "tensorflow"),
                    ("pandas", "pandas"), ("asyncio", "asyncio")]:
        if sig in imports:
            return fw
    return "plain-python"


def detect_test_framework(root: Path) -> str:
    for name in ("pytest.ini", "conftest.py", "tox.ini"):
        if (root / name).exists():
            return "pytest"
    pyproject = root / "pyproject.toml"
    if pyproject.exists() and "[tool.pytest" in _read(pyproject):
        return "pytest"
    has_unittest = any(p.name.startswith("test_") for p in _walk(root))
    return "unittest" if has_unittest else "none"


def structure_tree(root: Path, max_depth: int = 4) -> list[str]:
    lines: list[str] = []
    root_name = root.name

    def rec(d: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        entries = sorted([p for p in d.iterdir() if p.name not in IGNORE_DIRS and not p.name.startswith(".")],
                         key=lambda p: (not p.is_dir(), p.name.lower()))
        # cap directory breadth to keep the tree readable
        dirs = [p for p in entries if p.is_dir()]
        files = [p for p in entries if not p.is_dir() and p.suffix in (".py", ".txt", ".toml", ".md", ".cfg", ".ini", ".json", ".yml", ".yaml")]
        for i, p in enumerate(dirs + files[:40]):
            is_last = (i == len(dirs) + min(len(files), 40) - 1)
            branch = "└── " if is_last else "├── "
            lines.append(prefix + branch + (p.name + "/" if p.is_dir() else p.name))
            if p.is_dir():
                rec(p, prefix + ("    " if is_last else "│   "), depth + 1)

    lines.append(f"{root_name}/")
    rec(root, "", 1)
    return lines


def module_graph(root: Path) -> dict:
    """Map of module file -> list of project-internal modules it imports."""
    py_files = [p for p in _walk(root) if p.suffix == ".py"]
    rel_of = {p: str(p.relative_to(root)).replace("\\", "/") for p in py_files}

    def module_name(rel: str) -> str:
        if rel.endswith("/__init__.py"):
            return rel[: -len("/__init__.py")].replace("/", ".")
        return rel[: -len(".py")].replace("/", ".")

    by_name: dict[str, Path] = {}
    for p in py_files:
        by_name[module_name(rel_of[p])] = p

    edges: list[tuple[str, str]] = []
    for p in py_files:
        src = _read(p)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        me = module_name(rel_of[p])
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                base = node.module.split(".")[0]
            elif isinstance(node, ast.Import):
                base = node.names[0].name.split(".")[0]
            else:
                continue
            if base in by_name and base != me:
                edges.append((me, base))
    return {"modules": sorted(by_name.keys()), "edges": edges}


def analyze_project(root) -> dict:
    root = Path(root)
    py_files = [p for p in _walk(root) if p.suffix == ".py"]
    test_files = [p for p in py_files if _is_test_path(p, root)]
    req = root / "requirements.txt"
    dependencies: list[str] = []
    if req.exists():
        for line in _read(req).splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                dependencies.append(line.split("==")[0].split(">=")[0].split("~=")[0].split("<")[0].strip())
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        m = re.search(r'\[project\]\s+dependencies\s*=\s*\[(.*?)\]', _read(pyproject), re.S)
        if m:
            for dep in re.findall(r'["\']([^"\']+)["\']', m.group(1)):
                dependencies.append(dep.split("==")[0].split(">=")[0].strip())
    dependencies = sorted(set(d for d in dependencies if d))

    overview = {
        "language": "Python",
        "python_version": detect_python_version(root),
        "framework": detect_framework(root),
        "package_manager": detect_package_manager(root),
        "test_framework": detect_test_framework(root),
        "files": len(_walk(root)),
        "python_files": len(py_files),
        "tests_files": len(test_files),
        "dependencies": dependencies,
        "dependencies_count": len(dependencies),
        "has_requirements": req.exists() or pyproject.exists(),
        "tree": structure_tree(root),
        "graph": module_graph(root),
        "root": str(root),
    }
    return overview
