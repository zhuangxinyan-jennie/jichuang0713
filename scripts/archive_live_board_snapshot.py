from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import PurePosixPath
from stat import S_ISDIR, S_ISREG

import paramiko


HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PASS = os.environ["BOARD_PASS"]

SNAPSHOT_ROOT = "archive/live_board_snapshot_20260818"

REMOTE_DIRS = {
    "/home/HwHiAiUser/pre_on_board/board_deploy": "pre_on_board/board_deploy",
    "/home/HwHiAiUser/jichuang": "jichuang",
    "/home/HwHiAiUser/bear_agent_cloud": "bear_agent_cloud",
    "/home/HwHiAiUser/HGBO/scripts": "HGBO/scripts",
    "/home/HwHiAiUser/HGBO/README.md": "HGBO/README.md",
    "/home/HwHiAiUser/HGBO/config": "HGBO/config",
}

ALLOW_SUFFIXES = {
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".service",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

ALLOW_FILENAMES = {"README", "Makefile"}

EXCLUDE_PARTS = {
    "__pycache__",
    ".cache",
    ".git",
    ".pytest_cache",
    ".venv",
    "outputs",
    "output",
    "logs",
    "app_gateway_certs",
    "data",
}

EXCLUDE_SUFFIXES = {
    ".data",
    ".engine",
    ".log",
    ".npz",
    ".om",
    ".onnx",
    ".pem",
    ".pid",
    ".pt",
    ".pyc",
    ".tar",
    ".gz",
    ".bz2",
    ".wav",
    ".zip",
}

EXCLUDE_FILENAMES = {
    "board_env.sh",
    "config.py",
    "env.local",
    "app_gateway.env",
    "key.pem",
    "cert.pem",
}

SANITIZE_PATTERNS = [
    (re.compile(re.escape(PASS)), "<BOARD_PASSWORD>"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "<DASHSCOPE_API_KEY>"),
]


def should_copy(remote_path: str) -> tuple[bool, str]:
    path = PurePosixPath(remote_path)
    if any(part in EXCLUDE_PARTS for part in path.parts):
        return False, "excluded directory"
    if path.name in EXCLUDE_FILENAMES:
        return False, "excluded sensitive filename"
    suffixes = "".join(path.suffixes)
    if suffixes.endswith(".tar.gz") or suffixes.endswith(".tar.bz2"):
        return False, "excluded archive"
    if path.suffix in EXCLUDE_SUFFIXES:
        return False, "excluded suffix"
    if path.suffix in ALLOW_SUFFIXES or path.name in ALLOW_FILENAMES:
        return True, "source/config"
    return False, "unsupported file type"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def sanitize_text_file(path: str) -> None:
    try:
        with open(path, "rb") as f:
            raw = f.read()
        text = raw.decode("utf-8")
    except (UnicodeDecodeError, OSError):
        return
    changed = text
    for pattern, replacement in SANITIZE_PATTERNS:
        changed = pattern.sub(replacement, changed)
    if changed != text:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(changed)


def walk_sftp(sftp: paramiko.SFTPClient, remote: str):
    attrs = sftp.stat(remote)
    if S_ISREG(attrs.st_mode):
        yield remote, attrs
        return
    if not S_ISDIR(attrs.st_mode):
        return
    for child in sftp.listdir_attr(remote):
        child_path = remote.rstrip("/") + "/" + child.filename
        if S_ISDIR(child.st_mode):
            if child.filename in EXCLUDE_PARTS:
                yield child_path, child
                continue
            yield from walk_sftp(sftp, child_path)
        else:
            yield child_path, child


def main() -> None:
    if os.path.isdir(SNAPSHOT_ROOT):
        shutil.rmtree(SNAPSHOT_ROOT)
    os.makedirs(SNAPSHOT_ROOT, exist_ok=True)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15, banner_timeout=15, auth_timeout=15)
    sftp = ssh.open_sftp()

    copied = []
    skipped = []
    for remote_root, local_root in REMOTE_DIRS.items():
        for remote_path, attrs in walk_sftp(sftp, remote_root):
            if S_ISDIR(attrs.st_mode):
                skipped.append({"remote": remote_path, "reason": "excluded directory"})
                continue
            ok, reason = should_copy(remote_path)
            rel = remote_path[len(remote_root) :].lstrip("/")
            local_parts = [SNAPSHOT_ROOT, *local_root.split("/")]
            if rel:
                local_parts.extend(rel.split("/"))
            local_path = os.path.join(*local_parts)
            if not ok:
                skipped.append({"remote": remote_path, "reason": reason})
                continue
            ensure_parent(local_path)
            sftp.get(remote_path, local_path)
            sanitize_text_file(local_path)
            copied.append(
                {
                    "remote": remote_path,
                    "local": local_path.replace("\\", "/"),
                    "size": attrs.st_size,
                    "mtime": attrs.st_mtime,
                    "sha256": sha256_file(local_path),
                }
            )

    sftp.close()
    ssh.close()

    manifest = {
        "board_host": HOST,
        "board_user": USER,
        "snapshot_root": SNAPSHOT_ROOT,
        "copied_count": len(copied),
        "skipped_count": len(skipped),
        "copied": copied,
        "skipped": skipped,
    }
    with open(os.path.join(SNAPSHOT_ROOT, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    with open(os.path.join(SNAPSHOT_ROOT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(
            "# Live Board Snapshot 2026-08-18\n\n"
            "This directory preserves source and small configuration files pulled from the live Ascend 310B board before returning the device.\n\n"
            "Excluded intentionally: passwords, certificates, `.env` files, runtime logs, caches, Python bytecode, model artifacts (`.om`, `.onnx`, `.pt`, `.engine`), large datasets, and archives.\n\n"
            "See `manifest.json` for copied paths, skipped paths, sizes, mtimes, and SHA-256 hashes.\n"
        )

    print(f"copied={len(copied)} skipped={len(skipped)}")


if __name__ == "__main__":
    main()
