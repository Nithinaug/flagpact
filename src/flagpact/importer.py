import ast
import json
import os
import pathlib
import re
import subprocess
import tempfile
from typing import Any, Callable

import semver

MAX_FILES = 2000
MAX_FILE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_ENTRIES = 20000
MAX_CLONE_BYTES = 200 * 1024 * 1024
CLONE_TIMEOUT = 60
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "env", "dist", "build", "__pycache__", "vendor", "site-packages", ".tox"}
TEST_DIRS = {"tests", "test", "__tests__", "spec"}
TEST_FILE = re.compile(r"^(?:test_.*\.py|.*_test\.py|conftest\.py|.*\.(?:test|spec)\.(?:js|jsx|ts|tsx|mjs))$")
OTHER_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".go", ".java", ".kt", ".swift", ".rb", ".php", ".cs"}
VALUE_CALLS = {"config", "get_feature_value", "get_value", "get_flag"}
OTHER_CALL = re.compile(r"\b(?:getValue|getFeatureValue|get_feature_value|GetFeatureValue|get_value|GetValue)\(\s*[\"']([A-Za-z0-9_.\- ]{1,100})[\"']")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")
VERSION_NAMES = re.compile(r"^(?:[A-Z_]*APP_)?VERSION$")
GITHUB = re.compile(r"^(?:https://)?github\.com/([A-Za-z0-9][A-Za-z0-9-]{0,38})/([A-Za-z0-9._-]{1,100}?)(?:\.git)?/?$")
BLOCKED_ROOTS = ("/etc", "/proc", "/sys", "/dev", "/boot", "/root", "/var", "/usr", "/bin", "/sbin", "/lib", "/run", "/snap")
BLOCKED_HOME = (".ssh", ".aws", ".gnupg", ".config", ".kube", ".docker", ".azure", ".gcloud")

Runner = Callable[..., subprocess.CompletedProcess]


class ScanError(Exception):
    pass


def _valid(version: str) -> bool:
    return bool(SEMVER.match(version)) and semver.Version.is_valid(version)


class _Site:
    def __init__(self, flag: str, file: str, line: int, kind: str) -> None:
        self.flag, self.file, self.line, self.kind = flag, file, line, kind


class _Reader(ast.NodeVisitor):
    def __init__(self, relative: str) -> None:
        self.relative = relative
        self.scopes: list[dict[str, tuple[str, tuple[str, ...]]]] = [{}]
        self.sites: list[_Site] = []
        self.reads: list[dict[str, Any]] = []
        self.versions: list[dict[str, Any]] = []

    def lookup(self, name: str) -> tuple[str, tuple[str, ...]] | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def flag_call(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "loads":
            if node.args:
                return self.flag_call(node.args[0])
            return None
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in VALUE_CALLS
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            return node.args[0].value
        return None

    def resolve(self, node: ast.AST) -> tuple[str, tuple[str, ...], bool] | None:
        flag = self.flag_call(node)
        if flag is not None:
            return flag, (), False
        if isinstance(node, ast.Name):
            found = self.lookup(node.id)
            return (found[0], found[1], False) if found else None
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            base = self.resolve(node.value)
            return (base[0], base[1] + (node.slice.value,), False) if base else None
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            base = self.resolve(node.func.value)
            if base:
                return base[0], base[1] + (node.args[0].value,), len(node.args) > 1 or bool(node.keywords)
        return None

    def note(self, node: ast.AST) -> None:
        found = self.resolve(node)
        if found and found[1]:
            self.reads.append({
                "flag": found[0], "path": ".".join(found[1]), "has_default": found[2],
                "file": self.relative, "line": getattr(node, "lineno", 0),
            })

    def visit_Call(self, node: ast.Call) -> None:
        flag = self.flag_call(node)
        if flag is not None and not (isinstance(node.func, ast.Attribute) and node.func.attr == "loads"):
            self.sites.append(_Site(flag, self.relative, node.lineno, node.func.attr if isinstance(node.func, ast.Attribute) else "call"))
        self.note(node)
        self.version_from_call(node)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.note(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scopes.append({})
        self.generic_visit(node)
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        found = self.resolve(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                if found:
                    self.scopes[-1][target.id] = (found[0], found[1])
                if (
                    VERSION_NAMES.match(target.id)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                    and _valid(node.value.value)
                ):
                    self.versions.append({"version": node.value.value, "file": self.relative, "line": node.lineno})

    def version_from_call(self, node: ast.Call) -> None:
        args = node.args
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if (
            name == "setdefault"
            and len(args) == 2
            and isinstance(args[0], ast.Constant)
            and args[0].value == "FLAGPACT_APP_VERSION"
            and isinstance(args[1], ast.Constant)
            and isinstance(args[1].value, str)
            and _valid(args[1].value)
        ):
            self.versions.append({"version": args[1].value, "file": self.relative, "line": node.lineno})
        if (
            name == "FlagpactClient"
            and len(args) >= 2
            and isinstance(args[1], ast.Constant)
            and isinstance(args[1].value, str)
            and _valid(args[1].value)
        ):
            self.versions.append({"version": args[1].value, "file": self.relative, "line": node.lineno})


def _walk(root: pathlib.Path) -> tuple[list[pathlib.Path], list[str]]:
    files: list[pathlib.Path] = []
    notes: list[str] = []
    skipped_tests = 0
    entries = 0
    total = 0
    base = root.resolve()
    for current, dirs, names in os.walk(base, followlinks=False):
        skipped_tests += sum(1 for d in dirs if d in TEST_DIRS)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and d not in TEST_DIRS and not os.path.islink(os.path.join(current, d)))
        for name in sorted(names):
            if TEST_FILE.match(name):
                skipped_tests += 1
                continue
            entries += 1
            if entries > MAX_ENTRIES:
                notes.append(f"stopped after {MAX_ENTRIES} entries")
                return files, notes
            path = pathlib.Path(current) / name
            if path.is_symlink() or not path.is_file():
                continue
            if path.suffix != ".py" and path.suffix not in OTHER_SUFFIXES and name not in ("package.json", "pyproject.toml"):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_FILE_BYTES:
                notes.append(f"skipped {path.relative_to(base)}: larger than {MAX_FILE_BYTES // 1024} KB")
                continue
            total += size
            if len(files) >= MAX_FILES or total > MAX_TOTAL_BYTES:
                notes.append("stopped early: the project is larger than the scan limits")
                return files, notes
            files.append(path)
    if skipped_tests:
        notes.append(f"left out {skipped_tests} test file or folder(s), they are not app code")
    return files, notes


def _owner(file: str, versions: list[dict[str, Any]]) -> str:
    best: dict[str, Any] | None = None
    for item in versions:
        folder = item["directory"]
        if folder == "." or file == folder or file.startswith(folder + "/"):
            if best is None or len(folder) > len(best["directory"]):
                best = item
    return best["version"] if best else "unknown"


def _prune(reads: list[dict[str, Any]], versions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    owned = [{**r, "owner": _owner(r["file"], versions)} for r in reads]
    paths = {(r["flag"], r["owner"], r["path"]) for r in owned}
    kept = [r for r in owned if not any(f == r["flag"] and o == r["owner"] and p.startswith(r["path"] + ".") for f, o, p in paths)]
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for read in kept:
        entry = merged.setdefault((read["flag"], read["path"]), {
            "flag": read["flag"], "path": read["path"], "places": [], "required_in": set(), "default_in": set(),
        })
        entry["places"].append(f"{read['file']}:{read['line']}")
        entry["default_in" if read["has_default"] else "required_in"].add(read["owner"])
    return list(merged.values())


def scan_directory(root: str | pathlib.Path) -> dict[str, Any]:
    base = pathlib.Path(root).resolve()
    files, notes = _walk(base)
    sites: list[_Site] = []
    reads: list[dict[str, Any]] = []
    versions: list[dict[str, Any]] = []
    other: dict[str, list[tuple[str, int]]] = {}
    guessed: list[dict[str, Any]] = []
    counts = {"python": 0, "other": 0}
    for path in files:
        relative = str(path.relative_to(base))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if path.suffix in (".py",) or path.suffix in OTHER_SUFFIXES:
            lowered = text.lower()
            if "flagsmith" not in lowered and "flagpact" not in lowered:
                continue
        if path.suffix == ".py":
            counts["python"] += 1
            try:
                tree = ast.parse(text)
            except (SyntaxError, ValueError, RecursionError, MemoryError):
                notes.append(f"could not parse {relative}")
                continue
            reader = _Reader(relative)
            reader.visit(tree)
            sites.extend(reader.sites)
            reads.extend(reader.reads)
            versions.extend(reader.versions)
        elif path.suffix in OTHER_SUFFIXES:
            counts["other"] += 1
            for number, line in enumerate(text.splitlines(), 1):
                for match in OTHER_CALL.finditer(line):
                    other.setdefault(match.group(1), []).append((relative, number))
        elif path.name == "package.json":
            try:
                data = json.loads(text)
            except ValueError:
                continue
            version = data.get("version") if isinstance(data, dict) else None
            if isinstance(version, str) and _valid(version):
                guessed.append({"version": version, "file": relative, "line": 1})
        elif path.name == "pyproject.toml":
            match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
            if match and _valid(match.group(1)):
                guessed.append({"version": match.group(1), "file": relative, "line": 1})

    found: dict[tuple[str, str], dict[str, Any]] = {}
    for item in versions:
        directory = str(pathlib.PurePosixPath(item["file"]).parent)
        found.setdefault((item["version"], directory), {**item, "directory": directory, "guessed": False})
    if not found:
        for item in guessed:
            directory = str(pathlib.PurePosixPath(item["file"]).parent)
            found.setdefault((item["version"], directory), {**item, "directory": directory, "guessed": True})
    version_list = sorted(found.values(), key=_version_key)

    flags: dict[str, dict[str, Any]] = {}
    for site in sites:
        entry = flags.setdefault(site.flag, {"flag": site.flag, "sites": [], "reads": [], "languages": []})
        entry["sites"].append({"file": site.file, "line": site.line, "call": site.kind})
        if "python" not in entry["languages"]:
            entry["languages"].append("python")
    for read in _prune(reads, version_list):
        if read["flag"] in flags:
            flags[read["flag"]]["reads"].append({
                "path": read["path"],
                "required": bool(read["required_in"]),
                "required_in": sorted(read["required_in"]),
                "default_in": sorted(read["default_in"]),
                "places": read["places"][:5],
            })
    for name, places in other.items():
        entry = flags.setdefault(name, {"flag": name, "sites": [], "reads": [], "languages": []})
        entry["sites"].extend({"file": f, "line": n, "call": "getValue"} for f, n in places)
        if "other" not in entry["languages"]:
            entry["languages"].append("other")

    ordered = sorted(flags.values(), key=lambda f: (-len(f["reads"]), -len(f["sites"]), f["flag"]))
    review: list[str] = []
    if not ordered:
        review.append("No Flagsmith value reads were found. flagpact scans Python (config, get_feature_value) and a few other languages for getValue-style calls.")
    if len(ordered) > 1:
        review.append(f"{len(ordered)} flags found. The draft uses {ordered[0]['flag']}. A flagpact.json covers one flag, so make one file per flag.")
    if ordered and any("other" in f["languages"] and not f["reads"] for f in ordered):
        review.append("Fields are only read from Python. For other languages the flag is listed but the fields it reads need review.")
    if ordered and not version_list:
        review.append("No app version was found. Add each version with the folder that holds its tests.")
    if version_list and all(v["guessed"] for v in version_list):
        review.append("The version comes from a package file, not from the app. Confirm it is the value the app sends as app_version.")
    if ordered:
        review.append("Version folders are relative to the scanned folder, so save the draft in that folder.")
        review.append("Import only reads source code. Contracts still have to be recorded by running each version's tests with flagpact's recorder.")

    draft: dict[str, Any] | None = None
    if ordered:
        draft = {
            "flag": ordered[0]["flag"],
            "trait": "app_version",
            "contracts": "contracts",
            "versions": [{"version": v["version"], "directory": v["directory"]} for v in version_list],
        }
    return {
        "files_scanned": len(files),
        "languages": counts,
        "flags": ordered,
        "versions": version_list,
        "draft": draft,
        "needs_review": review,
        "notes": notes,
    }


def _version_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    parsed = semver.Version.parse(item["version"])
    return parsed.major, parsed.minor, parsed.patch, item["directory"]


def parse_github_url(text: str) -> str:
    match = GITHUB.match(text.strip())
    if match is None or match.group(2) in (".", ".."):
        raise ScanError("use a public repository URL such as https://github.com/owner/repo")
    return f"https://github.com/{match.group(1)}/{match.group(2)}.git"


def _tree_bytes(root: str) -> int:
    total = 0
    for current, _, names in os.walk(root, followlinks=False):
        for name in names:
            try:
                total += os.lstat(os.path.join(current, name)).st_size
            except OSError:
                continue
    return total


def clone_public(url: str, dest: str, runner: Runner = subprocess.run) -> None:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": dest,
        "XDG_CONFIG_HOME": dest,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "LC_ALL": "C",
    }
    command = [
        "git",
        "-c", "protocol.allow=never",
        "-c", "protocol.https.allow=always",
        "-c", "core.symlinks=false",
        "-c", f"core.hooksPath={os.devnull}",
        "-c", "credential.helper=",
        "clone", "--depth", "1", "--single-branch", "--no-tags", "--no-recurse-submodules",
        "--", url, os.path.join(dest, "repo"),
    ]
    try:
        result = runner(command, env=env, capture_output=True, text=True, timeout=CLONE_TIMEOUT, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as error:
        raise ScanError(f"cloning took longer than {CLONE_TIMEOUT} seconds") from error
    except OSError as error:
        raise ScanError("git is not available on this machine") from error
    if result.returncode == 0 and _tree_bytes(os.path.join(dest, "repo")) > MAX_CLONE_BYTES:
        raise ScanError("the repository is larger than 200 MB, clone it yourself and import the folder")
    if result.returncode != 0:
        raise ScanError("could not clone the repository. It must exist and be public, private repositories are not supported")


def resolve_local(text: str) -> pathlib.Path:
    path = pathlib.Path(text).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ScanError("that folder does not exist") from error
    if not resolved.is_dir():
        raise ScanError("that path is not a folder")
    text_path = str(resolved)
    if text_path == "/" or any(text_path == r or text_path.startswith(r + "/") for r in BLOCKED_ROOTS):
        raise ScanError("that folder is not a project folder")
    home = pathlib.Path.home().resolve()
    if resolved == home:
        raise ScanError("choose a project folder, not your whole home folder")
    try:
        inside = resolved.relative_to(home).parts
    except ValueError:
        inside = ()
    if inside and inside[0] in BLOCKED_HOME:
        raise ScanError("that folder is not a project folder")
    return resolved


def scan_source(source: str, runner: Runner = subprocess.run, github_only: bool = False, checkout: str | None = None) -> dict[str, Any]:
    from .tags import try_tags

    text = (source or "").strip()
    if not text or len(text) > 300 or "\x00" in text or "\n" in text:
        raise ScanError("enter a local folder or a public GitHub repository URL")
    lowered = text.lower()
    if lowered.startswith(("https://", "github.com/")):
        url = parse_github_url(text)
        with tempfile.TemporaryDirectory(prefix="flagpact-import-") as tmp:
            clone_public(url, tmp, runner)
            repo = os.path.join(tmp, "repo")
            result = try_tags(repo, tmp, runner, fetch=True, checkout=checkout) or scan_directory(repo)
        if checkout and "tags" not in result:
            raise ScanError("this repository has fewer than two release tags, so there is nothing to check out")
        result["source"] = url.removesuffix(".git")
        result["kind"] = "github"
        return result
    if github_only:
        raise ScanError("enter a public GitHub repository URL such as https://github.com/owner/repo")
    if "://" in text or lowered.startswith(("git@", "ssh:", "file:", "ext:")) or "::" in text:
        raise ScanError("only a local folder or a public https://github.com URL is supported")
    root = resolve_local(text)
    with tempfile.TemporaryDirectory(prefix="flagpact-import-") as home:
        result = try_tags(str(root), home, runner, checkout=checkout) or scan_directory(root)
    if checkout and "tags" not in result:
        raise ScanError("this folder has fewer than two release tags, so there is nothing to check out")
    result["source"] = root.name
    result["kind"] = "local"
    return result
