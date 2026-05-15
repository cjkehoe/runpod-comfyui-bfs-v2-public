import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests


MANIFEST_PATH = Path(__file__).with_name("asset-manifest.json")
DEFAULT_COMFY_ROOT = Path(os.getenv("COMFY_ROOT", "/comfyui"))
DEFAULT_NETWORK_VOLUME_ROOT = Path(os.getenv("NETWORK_VOLUME_ROOT", "/runpod-volume"))
PREWARM_WORKFLOW_ID = os.getenv("PREWARM_WORKFLOW_ID", "").strip()
HUGGING_FACE_HOSTS = {"huggingface.co", "hf.co"}
CIVITAI_HOSTS = {"civitai.com", "www.civitai.com", "civitai.red", "www.civitai.red"}


def _load_manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _request_headers_for_url(url: str) -> Dict[str, str]:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        host = ""

    if host in HUGGING_FACE_HOSTS:
        token = os.getenv("HF_TOKEN", "").strip() or os.getenv("HUGGINGFACE_HUB_TOKEN", "").strip()
        return {"Authorization": f"Bearer {token}"} if token else {}
    if host in CIVITAI_HOSTS:
        token = os.getenv("CIVITAI_TOKEN", "").strip() or os.getenv("CIVITAI_API_KEY", "").strip()
        return {"Authorization": f"Bearer {token}"} if token else {}
    return {}


def _download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=600, headers=_request_headers_for_url(url)) as response:
        response.raise_for_status()
        with destination.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output_file.write(chunk)


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _resolve_cache_destination(relative_path: str, filename: str, network_volume_root: Path) -> Optional[Path]:
    if relative_path == "input":
        return None
    if not network_volume_root.exists() or not network_volume_root.is_dir():
        return None

    return network_volume_root / "comfyui" / relative_path / filename


def _model_matches_workflow(model: Dict[str, Any], workflow_id: str) -> bool:
    if not workflow_id or workflow_id == "all":
        return True
    workflow_ids = model.get("workflow_ids")
    if not isinstance(workflow_ids, list):
        return True
    return workflow_id in {str(item) for item in workflow_ids}


def _ensure_core_model(model: Dict[str, Any], comfy_root: Path, network_volume_root: Path) -> None:
    if model.get("optional") and not os.getenv("PREWARM_OPTIONAL_MODELS"):
        print(f"Skipping optional model {model.get('filename')}")
        return

    relative_path = str(model["relative_path"]).strip("/")
    filename = Path(str(model["filename"])).name
    destination = comfy_root / relative_path / filename
    if destination.exists() and destination.stat().st_size > 0:
        return

    cache_destination = _resolve_cache_destination(relative_path, filename, network_volume_root)
    if cache_destination and cache_destination.exists() and cache_destination.stat().st_size > 0:
        print(f"Copying cached core model {cache_destination} -> {destination}")
        _copy_file(cache_destination, destination)
        return

    url_env = str(model.get("url_env") or "").strip()
    url = os.getenv(url_env, "").strip() if url_env else ""
    url = url or str(model.get("default_url") or "").strip()
    if not url:
        print(f"Skipping {filename} - {model.get('url_env')} is not set and no default_url is configured")
        return

    print(f"Downloading {filename} -> {destination}")
    _download_file(url, destination)

    if cache_destination:
        _copy_file(destination, cache_destination)


def main() -> None:
    manifest = _load_manifest()
    for model in manifest.get("core_models", []):
        if not _model_matches_workflow(model, PREWARM_WORKFLOW_ID):
            continue
        _ensure_core_model(model, DEFAULT_COMFY_ROOT, DEFAULT_NETWORK_VOLUME_ROOT)


if __name__ == "__main__":
    main()

