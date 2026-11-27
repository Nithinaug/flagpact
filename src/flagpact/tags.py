import io
import os
import pathlib
import re
import subprocess
import tarfile
import tempfile
from typing import Any

import semver

from .importer import (
    CLONE_TIMEOUT, MAX_CLONE_BYTES, MAX_FILE_BYTES, OTHER_SUFFIXES, SKIP_DIRS, Runner, ScanError, _valid, scan_directory,
)

MAX_TAGS = 8
TAG = re.compile(r"^v?(\d+\.\d+\.\d+)$")
SOURCE_NAMES = {"package.json", "pyproject.toml"}


def _env(home: str) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": home,
        "XDG_CONFIG_HOME": home,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "LC_ALL": "C",
    }


def _git(repo: str, args: list[str], home: str, runner: Runner, text: bool = True) -> subprocess.CompletedProcess:
    command = [
        "git", "-C", repo,
        "-c", "protocol.allow=never",
        "-c", "protocol.https.allow=always",
        "-c", "core.symlinks=false",
        "-c", f"core.hooksPath={os.devnull}",
        "-c", "credential.helper=",
        *args,
    ]
    try:
        return runner(command, env=_env(home), capture_output=True, text=text, timeout=CLONE_TIMEOUT, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as error:
        raise ScanError(f"git took longer than {CLONE_TIMEOUT} seconds") from error
    except OSError as error:
        raise ScanError("git is not available on this machine") from error


def release_tags(repo: str, home: str, runner: Runner = subprocess.run) -> list[tuple[str, str]]:
    result = _git(repo, ["tag", "--list"], home, runner)
    if result.returncode != 0:
        return []
    found: list[tuple[str, str]] = []
    for name in result.stdout.split():
        match = TAG.match(name)
        if match and _valid(match.group(1)):
            found.append((name, match.group(1)))
    found.sort(key=lambda item: semver.Version.parse(item[1]))
    return found[-MAX_TAGS:]


def _safe_member(member: tarfile.TarInfo) -> bool:
    parts = pathlib.PurePosixPath(member.name).parts
    return member.isreg() and not member.name.startswith("/") and ".." not in parts


def extract(repo: str, ref: str, dest: str, home: str, runner: Runner = subprocess.run, only_source: bool = True) -> int:
    result = _git(repo, ["archive", "--format=tar", ref, "--"], home, runner, text=False)
    if result.returncode != 0:
        raise ScanError(f"could not read {ref} from the repository")
    written = 0
    base = pathlib.Path(dest).resolve()
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
        for member in archive:
            if not _safe_member(member) or member.size > MAX_FILE_BYTES:
                continue
            path = pathlib.PurePosixPath(member.name)
            if only_source and (
                any(part in SKIP_DIRS for part in path.parts)
                or (path.suffix != ".py" and path.suffix not in OTHER_SUFFIXES and path.name not in SOURCE_NAMES)
            ):
                continue
            written += member.size
            if written > MAX_CLONE_BYTES:
                raise ScanError("the repository is larger than 200 MB, clone it yourself and import the folder")
            target = (base / member.name).resolve()
            if base not in target.parents:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            handle = archive.extractfile(member)
            if handle is not None:
                target.write_bytes(handle.read())
    return written


def scan_tags(repo: str, tags: list[tuple[str, str]], home: str, runner: Runner = subprocess.run) -> dict[str, Any]:
    per_tag: list[tuple[str, str, dict[str, Any]]] = []
    for name, version in tags:
        with tempfile.TemporaryDirectory(prefix="flagpact-tag-") as snap:
            extract(repo, name, snap, home, runner)
            per_tag.append((name, version, scan_directory(snap)))

    merged: dict[str, dict[str, Any]] = {}
    for name, version, result in per_tag:
        for flag in result["flags"]:
            entry = merged.setdefault(flag["flag"], {"flag": flag["flag"], "sites": [], "reads": {}, "languages": []})
            if not entry["sites"]:
                entry["sites"] = flag["sites"]
            for language in flag["languages"]:
                if language not in entry["languages"]:
                    entry["languages"].append(language)
            for read in flag["reads"]:
                slot = entry["reads"].setdefault(
                    read["path"], {"path": read["path"], "required_in": set(), "default_in": set(), "places": read["places"]}
                )
                slot["required_in" if read["required"] else "default_in"].add(version)

    flags = []
    for entry in merged.values():
        reads = [
            {
                "path": r["path"],
                "required": bool(r["required_in"]),
                "required_in": sorted(r["required_in"], key=semver.Version.parse),
                "default_in": sorted(r["default_in"], key=semver.Version.parse),
                "places": r["places"],
            }
            for r in entry["reads"].values()
        ]
        flags.append({**entry, "reads": reads})
    flags.sort(key=lambda f: (-len(f["reads"]), -len(f["sites"]), f["flag"]))

    versions = [
        {"version": version, "file": "", "line": 0, "directory": f"versions/{name}", "guessed": False, "ref": name}
        for name, version, _ in per_tag
    ]
    draft = None
    if flags:
        draft = {
            "flag": flags[0]["flag"],
            "trait": "app_version",
            "contracts": "contracts",
            "versions": [{"version": v["version"], "directory": v["directory"]} for v in versions],
        }
    review = [f"Read {len(tags)} release tag(s): {', '.join(n for n, _ in tags)}. Each tag is one app version."]
    if len(flags) > 1:
        review.append(f"{len(flags)} flags found. The draft uses {flags[0]['flag']}. A flagpact.json covers one flag, so make one file per flag.")
    if not flags:
        review.append("No Flagsmith value reads were found in any tag.")
    else:
        review.append("Run flagpact import with --checkout to write each tag's files into versions/, then record contracts by running each version's tests.")
    return {
        "files_scanned": sum(r["files_scanned"] for _, _, r in per_tag),
        "languages": {
            "python": sum(r["languages"]["python"] for _, _, r in per_tag),
            "other": sum(r["languages"]["other"] for _, _, r in per_tag),
        },
        "flags": flags,
        "versions": versions,
        "draft": draft,
        "needs_review": review,
        "notes": [],
        "tags": [name for name, _ in tags],
    }


def checkout_tags(repo: str, tags: list[tuple[str, str]], out: str, home: str, runner: Runner = subprocess.run) -> list[str]:
    base = pathlib.Path(out)
    if base.exists() and any(base.iterdir()):
        raise ScanError(f"{out} is not empty, choose a new folder")
    made = []
    for name, _ in tags:
        folder = base / name
        folder.mkdir(parents=True)
        extract(repo, name, str(folder), home, runner, only_source=False)
        made.append(str(folder))
    return made


def try_tags(repo: str, home: str, runner: Runner = subprocess.run, fetch: bool = False, checkout: str | None = None) -> dict[str, Any] | None:
    if not os.path.isdir(os.path.join(repo, ".git")):
        return None
    if fetch:
        try:
            _git(repo, ["fetch", "--quiet", "--no-tags", "--depth", "1", "origin", "+refs/tags/*:refs/tags/*"], home, runner)
        except ScanError:
            return None
    tags = release_tags(repo, home, runner)
    if len(tags) < 2:
        return None
    result = scan_tags(repo, tags, home, runner)
    if checkout:
        checkout_tags(repo, tags, checkout, home, runner)
    return result
