import os
from pathlib import Path
from typing import Any, Dict, Union

import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def create_folder(folder_path: Union[str, Path]) -> None:
    os.makedirs(folder_path, exist_ok=True)


def load_yaml(yaml_file: Union[str, Path]) -> Dict[str, Any]:
    with open(yaml_file, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def save_yaml(data: Dict[str, Any], yaml_file: Union[str, Path]) -> None:
    create_folder(Path(yaml_file).parent)
    with open(yaml_file, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def save_json(data: Dict[str, Any], json_file: Union[str, Path]) -> None:
    import json

    create_folder(Path(json_file).parent)
    with open(json_file, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=4, ensure_ascii=False)


def load_json(json_file: Union[str, Path]) -> Dict[str, Any]:
    import json

    with open(json_file, "r", encoding="utf-8") as handle:
        return json.load(handle)
