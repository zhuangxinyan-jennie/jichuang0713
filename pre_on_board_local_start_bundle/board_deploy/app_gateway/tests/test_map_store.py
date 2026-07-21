from __future__ import annotations

import json
import zipfile
from io import BytesIO

import pytest

from app_gateway.core import GatewayError
from app_gateway.map_store import MapStore


def test_manifest_and_bundle(tmp_path) -> None:
    (tmp_path / "places.json").write_text('{"places": []}', encoding="utf-8")
    (tmp_path / "map.png").write_bytes(b"not-a-real-png")
    store = MapStore(tmp_path)

    manifest = store.manifest()
    assert manifest["version"] != "0"
    assert [item["path"] for item in manifest["files"]] == ["map.png", "places.json"]
    assert all(len(item["sha256"]) == 64 for item in manifest["files"])

    archive = zipfile.ZipFile(BytesIO(store.bundle(manifest["version"])))
    assert set(archive.namelist()) == {"manifest.json", "map.png", "places.json"}
    bundled_manifest = json.loads(archive.read("manifest.json"))
    assert bundled_manifest["version"] == manifest["version"]


def test_wrong_map_version_is_rejected(tmp_path) -> None:
    (tmp_path / "places.json").write_text("{}", encoding="utf-8")
    with pytest.raises(GatewayError) as exc:
        MapStore(tmp_path).bundle("old")
    assert exc.value.code == "MAP_VERSION_NOT_FOUND"
