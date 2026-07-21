"""Versioned map bundle served by App Gateway."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from .core import GatewayError


class MapStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def manifest(self) -> dict[str, Any]:
        files = self._files()
        entries = []
        version_hash = hashlib.sha256()
        for path in files:
            relative = path.relative_to(self.root).as_posix()
            digest = self._sha256(path)
            size = path.stat().st_size
            entries.append({"path": relative, "size": size, "sha256": digest})
            version_hash.update(relative.encode("utf-8"))
            version_hash.update(digest.encode("ascii"))
        version = version_hash.hexdigest()[:16] if entries else "0"
        return {
            "schema_version": 1,
            "version": version,
            "updated_at": max((path.stat().st_mtime for path in files), default=0),
            "files": entries,
            "bundle_path": f"/api/v1/map/bundle/{version}",
        }

    def bundle(self, version: str) -> bytes:
        manifest = self.manifest()
        if str(version) != manifest["version"]:
            raise GatewayError(404, "MAP_VERSION_NOT_FOUND", "地图版本不存在")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for path in self._files():
                archive.write(path, path.relative_to(self.root).as_posix())
        return output.getvalue()

    def _files(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return sorted(
            path
            for path in self.root.rglob("*")
            if path.is_file() and not path.name.startswith(".") and path.name != "manifest.json"
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

