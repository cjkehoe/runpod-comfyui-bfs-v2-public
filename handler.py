import importlib.util
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set
from urllib.parse import urlparse

import requests
import runpod

from workflow_builder import (
    BFS_V2_WORKFLOW_ID,
    BFS_V2_WORKFLOW_VERSION,
    BfsV2WorkflowInputError,
    build_bfs_v2_job_input,
    is_high_level_bfs_v2_request,
    target_video_filename,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

BASE_HANDLER_PATH = Path(os.getenv("BASE_HANDLER_PATH", "/handler_base.py"))
DEFAULT_MANIFEST_PATH = Path(__file__).with_name("asset-manifest.json")
MANIFEST_PATH = Path(
    os.getenv(
        "ASSET_MANIFEST_PATH",
        str(DEFAULT_MANIFEST_PATH if DEFAULT_MANIFEST_PATH.exists() else Path("/workspace/asset-manifest.json")),
    )
)
DEFAULT_MODELS_RELATIVE_PATH = "models/loras"
NETWORK_VOLUME_ROOT = Path(os.getenv("NETWORK_VOLUME_ROOT", "/runpod-volume"))
COMFY_ROOT = Path(os.getenv("COMFY_ROOT", "/comfyui"))
OUTPUT_PUBLIC_BASE = os.getenv("OUTPUT_PUBLIC_BASE", "").strip().rstrip("/")
OUTPUT_BUCKET_NAME = os.getenv("OUTPUT_BUCKET_NAME", "").strip().strip("/")
HUGGING_FACE_HOSTS = {"huggingface.co", "hf.co"}
CIVITAI_HOSTS = {"civitai.com", "www.civitai.com", "civitai.red", "www.civitai.red"}
NETWORK_VOLUME_CACHE_READ_MODES = {"1", "true", "yes", "on", "enabled", "read", "read_only", "ro", "write", "read_write", "rw"}
NETWORK_VOLUME_CACHE_WRITE_MODES = {"1", "true", "yes", "on", "enabled", "write", "read_write", "rw"}


def _load_base_handler():
    spec = importlib.util.spec_from_file_location("handler_base", BASE_HANDLER_PATH)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load base handler from {BASE_HANDLER_PATH}")

    module = importlib.util.module_from_spec(spec)
    base_handler_dir = str(BASE_HANDLER_PATH.parent)
    added_to_sys_path = False

    original_start = runpod.serverless.start
    runpod.serverless.start = lambda *args, **kwargs: None
    if base_handler_dir and base_handler_dir not in sys.path:
        sys.path.insert(0, base_handler_dir)
        added_to_sys_path = True
    try:
        spec.loader.exec_module(module)
    finally:
        runpod.serverless.start = original_start
        if added_to_sys_path:
            try:
                sys.path.remove(base_handler_dir)
            except ValueError:
                pass

    handler = getattr(module, "handler", None)
    if not callable(handler):
        raise RuntimeError("Base handler did not expose a callable handler(job)")

    return handler


BASE_HANDLER = _load_base_handler()


def _load_manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _resolve_job_input(job: Dict[str, Any]) -> Dict[str, Any]:
    payload = job.get("input") or {}

    if isinstance(payload, str):
        try:
            payload = json.loads(payload) if payload else {}
        except json.JSONDecodeError as exc:
            raise ValueError("Job input is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("Job input must be an object")

    return payload


def _normalize_relative_path(value: Any) -> str:
    raw = str(value or DEFAULT_MODELS_RELATIVE_PATH).strip().replace("\\", "/").strip("/")
    parts = [part for part in raw.split("/") if part not in {"", ".", ".."}]
    return "/".join(parts) or DEFAULT_MODELS_RELATIVE_PATH


def _iter_model_downloads(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    downloads = payload.pop("model_downloads", None)

    if downloads is None:
        return []

    if not isinstance(downloads, list):
        raise ValueError("model_downloads must be a list")

    return downloads


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
    tmp_destination = destination.with_suffix(f"{destination.suffix}.partial")

    if tmp_destination.exists():
        tmp_destination.unlink()

    try:
        with requests.get(url, stream=True, timeout=600, headers=_request_headers_for_url(url)) as response:
            response.raise_for_status()
            with tmp_destination.open("wb") as output_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output_file.write(chunk)

        os.replace(tmp_destination, destination)
    except Exception:
        if tmp_destination.exists():
            tmp_destination.unlink()
        raise


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _stage_cached_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        destination.unlink()

    try:
        destination.symlink_to(source)
    except OSError:
        logger.warning("Unable to symlink cached asset; copying instead: %s -> %s", source, destination)
        _copy_file(source, destination)


def _network_volume_cache_mode() -> str:
    value = os.getenv("NETWORK_VOLUME_CACHE_MODE")
    if value is None:
        value = os.getenv("NETWORK_VOLUME_CACHE_ENABLED", "read_only")
    return value.strip().lower()


def _network_volume_cache_read_enabled() -> bool:
    return _network_volume_cache_mode() in NETWORK_VOLUME_CACHE_READ_MODES


def _network_volume_cache_write_enabled() -> bool:
    return _network_volume_cache_mode() in NETWORK_VOLUME_CACHE_WRITE_MODES


def _resolve_cache_destination(relative_path: str, filename: str) -> Optional[Path]:
    if relative_path == "input":
        return None
    if not _network_volume_cache_read_enabled():
        return None
    if not NETWORK_VOLUME_ROOT.exists() or not NETWORK_VOLUME_ROOT.is_dir():
        return None

    return NETWORK_VOLUME_ROOT / "comfyui" / relative_path / filename


def _resolve_model_url(model: Dict[str, Any]) -> str:
    url_env = str(model.get("url_env") or "").strip()
    env_url = os.getenv(url_env, "").strip() if url_env else ""
    return env_url or str(model.get("default_url") or "").strip()


def _get_expected_file_size(url: str) -> Optional[int]:
    try:
        response = requests.head(url, allow_redirects=True, timeout=120, headers=_request_headers_for_url(url))
        response.raise_for_status()
    except Exception:
        logger.warning("Unable to determine remote size for core model; continuing without size validation")
        return None

    raw_size = response.headers.get("Content-Length") or response.headers.get("content-length")
    if not raw_size:
        return None

    try:
        return int(raw_size)
    except (TypeError, ValueError):
        return None


def _has_expected_size(path: Path, expected_size: Optional[int]) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    if expected_size is None:
        return True
    return path.stat().st_size == expected_size


def _ensure_core_model(model: Dict[str, Any]) -> Optional[str]:
    if model.get("optional") and not os.getenv("PREWARM_OPTIONAL_MODELS"):
        logger.info("Skipping optional model during default prewarm: %s", model.get("filename"))
        return None

    relative_path = _normalize_relative_path(model.get("relative_path"))
    filename = Path(str(model.get("filename") or "").strip()).name
    if not filename:
        return None

    runtime_destination = COMFY_ROOT / relative_path / filename
    runtime_destination.parent.mkdir(parents=True, exist_ok=True)
    cache_destination = _resolve_cache_destination(relative_path, filename)
    url = _resolve_model_url(model)
    expected_size = _get_expected_file_size(url) if url else None

    if _has_expected_size(runtime_destination, expected_size):
        logger.info("Using existing core model: %s", runtime_destination)
        return relative_path
    if runtime_destination.exists():
        logger.warning("Discarding incomplete core model at %s", runtime_destination)
        runtime_destination.unlink(missing_ok=True)

    if cache_destination and _has_expected_size(cache_destination, expected_size):
        logger.info("Linking cached core model into Comfy path: %s -> %s", cache_destination, runtime_destination)
        _stage_cached_file(cache_destination, runtime_destination)
        return relative_path

    cache_writable = bool(cache_destination and _network_volume_cache_write_enabled())
    if cache_destination and cache_writable and cache_destination.exists():
        logger.warning("Discarding incomplete cached core model at %s", cache_destination)
        cache_destination.unlink(missing_ok=True)

    if not url:
        logger.warning(
            "Skipping missing core model %s because %s is unset and no default_url is configured",
            filename,
            model.get("url_env"),
        )
        return None

    download_destination = cache_destination if cache_writable else runtime_destination
    logger.info("Downloading core model %s -> %s", filename, download_destination)
    _download_file(url, download_destination)
    if expected_size is not None and download_destination.stat().st_size != expected_size:
        actual_size = download_destination.stat().st_size
        download_destination.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded core model {filename} had size {actual_size} but expected {expected_size}")

    if cache_writable:
        logger.info("Cached core model at %s", cache_destination)
        _stage_cached_file(cache_destination, runtime_destination)

    return relative_path


def _model_matches_workflow(model: Dict[str, Any], workflow_id: Optional[str]) -> bool:
    if not workflow_id or workflow_id == "all":
        return True
    workflow_ids = model.get("workflow_ids")
    if not workflow_ids:
        return True
    if not isinstance(workflow_ids, list):
        return True
    return workflow_id in {str(item) for item in workflow_ids}


def _ensure_core_models(workflow_id: Optional[str] = None) -> Set[str]:
    try:
        manifest = _load_manifest()
    except FileNotFoundError:
        logger.warning("Asset manifest not found at %s; skipping core model ensure", MANIFEST_PATH)
        return set()

    downloaded_relative_paths: Set[str] = set()
    for model in manifest.get("core_models", []):
        if not _model_matches_workflow(model, workflow_id):
            continue
        relative_path = _ensure_core_model(model)
        if relative_path:
            downloaded_relative_paths.add(relative_path)

    return downloaded_relative_paths


def _process_model_downloads(payload: Dict[str, Any]) -> Set[str]:
    downloaded_relative_paths: Set[str] = set()

    for index, item in enumerate(_iter_model_downloads(payload)):
        if not isinstance(item, dict):
            raise ValueError(f"model_downloads[{index}] must be an object")

        url = str(item.get("url") or "").strip()
        filename = Path(str(item.get("filename") or "").strip()).name
        relative_path = _normalize_relative_path(item.get("relative_path"))

        if not url:
            raise ValueError(f"model_downloads[{index}] is missing url")
        if not filename:
            raise ValueError(f"model_downloads[{index}] is missing filename")

        runtime_destination = COMFY_ROOT / relative_path / filename
        runtime_destination.parent.mkdir(parents=True, exist_ok=True)
        cache_destination = _resolve_cache_destination(relative_path, filename)

        if runtime_destination.exists() and runtime_destination.stat().st_size > 0:
            logger.info("Using existing runtime asset: %s", runtime_destination)
        elif cache_destination and cache_destination.exists() and cache_destination.stat().st_size > 0:
            logger.info("Linking cached runtime asset into Comfy path: %s -> %s", cache_destination, runtime_destination)
            _stage_cached_file(cache_destination, runtime_destination)
        else:
            cache_writable = bool(cache_destination and _network_volume_cache_write_enabled())
            if cache_writable:
                logger.info("Downloading runtime asset %s -> %s", filename, cache_destination)
                _download_file(url, cache_destination)
                logger.info("Cached runtime asset at %s", cache_destination)
                _stage_cached_file(cache_destination, runtime_destination)
            else:
                logger.info("Downloading runtime asset %s -> %s", filename, runtime_destination)
                _download_file(url, runtime_destination)

        downloaded_relative_paths.add(relative_path)

    return downloaded_relative_paths


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_frame_rate(value: Any) -> Optional[float]:
    if not isinstance(value, str) or not value:
        return None
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        try:
            parsed_denominator = float(denominator)
            if parsed_denominator == 0:
                return None
            return float(numerator) / parsed_denominator
        except (TypeError, ValueError):
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _probe_source_video(path: Path) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,nb_frames,duration",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            text=True,
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError:
        logger.warning("ffprobe is not installed; continuing without source video metadata")
        return {}
    except subprocess.CalledProcessError as exc:
        logger.warning("ffprobe failed for source video %s: %s", path, exc.stderr.strip())
        return {}

    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        logger.warning("ffprobe returned invalid JSON for source video %s", path)
        return {}

    streams = data.get("streams") if isinstance(data, dict) else []
    if not isinstance(streams, list):
        streams = []

    video_stream = next(
        (stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"),
        {},
    )
    audio_present = any(isinstance(stream, dict) and stream.get("codec_type") == "audio" for stream in streams)

    def positive_float(value: Any) -> Optional[float]:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def positive_int(value: Any) -> Optional[int]:
        try:
            parsed = int(float(value))
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    format_data = data.get("format") if isinstance(data.get("format"), dict) else {}
    duration = positive_float(video_stream.get("duration")) or positive_float(format_data.get("duration"))
    frame_rate = _parse_frame_rate(video_stream.get("avg_frame_rate")) or _parse_frame_rate(
        video_stream.get("r_frame_rate")
    )
    frame_count = positive_int(video_stream.get("nb_frames"))
    if frame_count is None and duration and frame_rate:
        frame_count = max(1, int(round(duration * frame_rate)))

    return {
        "source_video_duration": duration,
        "source_video_width": positive_int(video_stream.get("width")),
        "source_video_height": positive_int(video_stream.get("height")),
        "source_video_frame_count": frame_count,
        "source_video_fps": frame_rate,
        "source_video_has_audio": audio_present,
        "source_video_streams": streams,
    }


def _annotate_target_video_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    video_url = str(payload.get("target_video_url") or payload.get("video_url") or payload.get("video") or "").strip()
    if not video_url:
        return payload

    filename = target_video_filename(video_url)
    source_path = COMFY_ROOT / "input" / filename
    if not source_path.exists() or source_path.stat().st_size <= 0:
        logger.info("Downloading BFS target video before workflow build: %s", filename)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        _download_file(video_url, source_path)

    annotated = dict(payload)
    annotated["source_video_filename"] = filename
    annotated["source_video_sha256"] = _sha256_file(source_path)
    for key, value in _probe_source_video(source_path).items():
        if value is not None:
            annotated[key] = value
    logger.info(
        "Using BFS target video metadata filename=%s duration=%s dimensions=%sx%s has_audio=%s",
        filename,
        annotated.get("source_video_duration"),
        annotated.get("source_video_width"),
        annotated.get("source_video_height"),
        annotated.get("source_video_has_audio"),
    )
    return annotated


def _refresh_comfy_file_cache(downloaded_relative_paths: Set[str]) -> None:
    folder_keys = set()

    for relative_path in downloaded_relative_paths:
        if relative_path == "input":
            continue
        if relative_path == "models/loras" or relative_path.startswith("models/loras/"):
            folder_keys.add("loras")
        elif relative_path == "models/checkpoints" or relative_path.startswith("models/checkpoints/"):
            folder_keys.add("checkpoints")
        elif relative_path == "models/diffusion_models" or relative_path.startswith("models/diffusion_models/"):
            folder_keys.add("diffusion_models")
        elif relative_path == "models/unet" or relative_path.startswith("models/unet/"):
            folder_keys.add("diffusion_models")
            folder_keys.add("unet")
        elif relative_path in {"models/clip", "models/text_encoders"}:
            folder_keys.add("clip")
            folder_keys.add("text_encoders")
        elif relative_path.startswith("models/clip/") or relative_path.startswith("models/text_encoders/"):
            folder_keys.add("clip")
            folder_keys.add("text_encoders")
        elif relative_path == "models/vae" or relative_path.startswith("models/vae/"):
            folder_keys.add("vae")
        elif relative_path == "models/latent_upscale_models" or relative_path.startswith("models/latent_upscale_models/"):
            folder_keys.add("latent_upscale_models")
        elif relative_path == "models/upscale_models" or relative_path.startswith("models/upscale_models/"):
            folder_keys.add("upscale_models")

    if not folder_keys:
        return

    try:
        import folder_paths

        for folder_key in folder_keys:
            folder_paths.filename_list_cache.pop(folder_key, None)
            visible_files = folder_paths.get_filename_list(folder_key)
            logger.info("Refreshed ComfyUI cache for %s. Visible files: %s", folder_key, visible_files[:20])
    except Exception:
        logger.exception("Failed to refresh ComfyUI file cache")


def _rewrite_public_output_url(url: str) -> str:
    if not OUTPUT_PUBLIC_BASE:
        return url

    parsed = urlparse(url)
    path = parsed.path.lstrip("/")

    if OUTPUT_BUCKET_NAME and path.startswith(f"{OUTPUT_BUCKET_NAME}/"):
        path = path[len(OUTPUT_BUCKET_NAME) + 1 :]

    if not path:
        return url

    return f"{OUTPUT_PUBLIC_BASE}/{path}"


def _select_primary_video_url(images: Iterable[Any]) -> Optional[str]:
    fallback_url: Optional[str] = None

    for item in images:
        if not isinstance(item, dict):
            continue

        data = item.get("data")
        if not isinstance(data, str) or not data.strip():
            continue

        filename = str(item.get("filename") or "").strip().lower()
        if "_debug_" in filename:
            continue

        if filename.endswith("-audio.mp4"):
            return data

        if fallback_url is None:
            fallback_url = data

    return fallback_url


def _collect_debug_video_urls(images: Iterable[Any]) -> Dict[str, str]:
    debug_urls: Dict[str, str] = {}

    for item in images:
        if not isinstance(item, dict):
            continue

        data = item.get("data")
        if not isinstance(data, str) or not data.strip():
            continue

        filename = str(item.get("filename") or "").strip().lower()
        if "_debug_first_pass" in filename:
            debug_urls["first_pass"] = data
        elif "_debug_comparison" in filename:
            debug_urls["comparison"] = data

    return debug_urls


def _normalize_video_output(result: Any, metadata: Dict[str, Any]) -> Any:
    if not isinstance(result, dict):
        return result

    images = result.get("images")
    if not isinstance(images, list) or not images:
        normalized_result = dict(result)
    else:
        normalized_images = []
        for item in images:
            if not isinstance(item, dict):
                normalized_images.append(item)
                continue

            normalized_item = dict(item)
            data = normalized_item.get("data")
            if isinstance(data, str) and data.strip():
                normalized_item["data"] = _rewrite_public_output_url(data)
            normalized_images.append(normalized_item)

        normalized_result = dict(result)
        normalized_result["images"] = normalized_images

        primary_video_url = _select_primary_video_url(normalized_images)
        if primary_video_url:
            normalized_result["video_url"] = primary_video_url

        debug_video_urls = _collect_debug_video_urls(normalized_images)
        if debug_video_urls:
            normalized_result["debug_video_urls"] = debug_video_urls

    for key in ("workflow_id", "workflow_version", "seed", "settings", "metadata", "model_metadata"):
        if key in metadata and key not in normalized_result:
            normalized_result[key] = metadata[key]

    return normalized_result


def _is_prewarm_request(payload: Dict[str, Any]) -> bool:
    action = str(payload.get("action") or "").strip().lower()
    if action == "prewarm_core_models":
        return True
    return bool(payload.get("prewarm_core_models"))


def _prewarm_workflow_id(payload: Dict[str, Any]) -> str:
    workflow_id = str(payload.get("workflow_id") or payload.get("prewarm_workflow_id") or BFS_V2_WORKFLOW_ID).strip()
    return workflow_id or BFS_V2_WORKFLOW_ID


def _prepare_execution_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "workflow" in payload:
        return dict(payload)

    if is_high_level_bfs_v2_request(payload):
        source_image_url = str(
            payload.get("source_face_image_url")
            or payload.get("source_face_image")
            or payload.get("source_image")
            or payload.get("source_image_url")
            or payload.get("face_image")
            or payload.get("image")
            or ""
        ).strip()
        video_url = str(payload.get("target_video_url") or payload.get("video_url") or payload.get("video") or "").strip()
        if not source_image_url or not video_url:
            return build_bfs_v2_job_input(payload)

        annotated_payload = _annotate_target_video_metadata(payload)
        prepared = build_bfs_v2_job_input(annotated_payload)
        extra_downloads = payload.get("model_downloads")
        if extra_downloads:
            if not isinstance(extra_downloads, list):
                raise ValueError("model_downloads must be a list")
            prepared["model_downloads"].extend(extra_downloads)
        return prepared

    raise BfsV2WorkflowInputError(f"workflow_id must be {BFS_V2_WORKFLOW_ID}")


def _extract_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: payload[key]
        for key in ("workflow_id", "workflow_version", "seed", "settings", "metadata", "model_metadata")
        if key in payload
    }


def handler(job: Dict[str, Any]) -> Any:
    payload = _resolve_job_input(job)

    if _is_prewarm_request(payload):
        prewarm_workflow_id = _prewarm_workflow_id(payload)
        downloaded_relative_paths = _ensure_core_models(prewarm_workflow_id)
        _refresh_comfy_file_cache(downloaded_relative_paths)
        return {
            "ok": True,
            "mode": "prewarm_core_models",
            "workflow_id": prewarm_workflow_id,
            "downloaded_relative_paths": sorted(downloaded_relative_paths),
            "network_volume_attached": NETWORK_VOLUME_ROOT.exists() and NETWORK_VOLUME_ROOT.is_dir(),
            "network_volume_root": str(NETWORK_VOLUME_ROOT),
            "network_volume_cache_mode": _network_volume_cache_mode(),
        }

    try:
        execution_payload = _prepare_execution_payload(payload)
    except BfsV2WorkflowInputError as exc:
        return {
            "error": str(exc),
            "workflow_id": BFS_V2_WORKFLOW_ID,
            "workflow_version": BFS_V2_WORKFLOW_VERSION,
        }

    workflow_id = str(execution_payload.get("workflow_id") or BFS_V2_WORKFLOW_ID)
    core_model_paths = _ensure_core_models(workflow_id)
    runtime_model_paths = _process_model_downloads(execution_payload)
    _refresh_comfy_file_cache(core_model_paths | runtime_model_paths)
    metadata = _extract_metadata(execution_payload)

    base_job = dict(job)
    base_job["input"] = execution_payload
    result = BASE_HANDLER(base_job)
    return _normalize_video_output(result, metadata)


runpod.serverless.start({"handler": handler})
