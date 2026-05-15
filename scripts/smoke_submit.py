#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow_builder import BFS_V2_DEFAULT_PROMPT, BFS_V2_WORKFLOW_ID  # noqa: E402


def _read_runpod_api_key() -> str:
    key = os.getenv("RUNPOD_API_KEY", "").strip()
    if key:
        return key

    config_path = Path.home() / ".runpod" / "config.toml"
    if config_path.exists():
        for line in config_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("apikey"):
                _, raw = line.split("=", 1)
                key = raw.strip().strip("'\"")
                if key:
                    return key

    raise SystemExit("RUNPOD_API_KEY is not set and ~/.runpod/config.toml has no apikey")


def _request(method: str, url: str, api_key: str, **kwargs: Any) -> Dict[str, Any]:
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {api_key}"
    response = requests.request(method, url, headers=headers, timeout=120, **kwargs)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"RunPod returned non-object JSON: {data!r}")
    return data


def _preflight_url(label: str, url: Optional[str]) -> None:
    if not url:
        raise SystemExit(f"{label} is required")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit(f"{label} must be an HTTPS URL")

    try:
        with requests.get(url, headers={"Range": "bytes=0-0"}, stream=True, timeout=60) as response:
            if response.status_code >= 400:
                raise SystemExit(f"{label} failed preflight with HTTP {response.status_code}")
    except requests.RequestException as exc:
        raise SystemExit(f"{label} failed preflight: {exc.__class__.__name__}") from exc


def _read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return args.prompt_file.read_text(encoding="utf-8").strip()
    return (args.prompt or BFS_V2_DEFAULT_PROMPT).strip()


def _build_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if args.prewarm:
        return {"input": {"action": "prewarm_core_models", "workflow_id": args.workflow_id}}

    return {
        "input": {
            "workflow_id": args.workflow_id,
            "source_face_image_url": args.source_face_image_url,
            "target_video_url": args.target_video_url,
            "prompt": _read_prompt(args),
            "negative_prompt": args.negative_prompt,
            "duration": args.duration,
            "fps": args.fps,
            "seed": args.seed,
            "base_resolution": args.base_resolution,
            "debug_outputs": args.debug_outputs,
            "settings": {
                "skip_first_frames": args.skip_first_frames,
            },
        }
    }


def _submit(endpoint_id: str, api_key: str, payload: Dict[str, Any]) -> str:
    data = _request("POST", f"https://api.runpod.ai/v2/{endpoint_id}/run", api_key, json=payload)
    job_id = str(data.get("id") or "").strip()
    if not job_id:
        raise RuntimeError(f"RunPod did not return a job id: {data}")
    return job_id


def _poll(endpoint_id: str, api_key: str, job_id: str, timeout_seconds: int, poll_seconds: int) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        data = _request("GET", f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}", api_key)
        status = str(data.get("status") or "").upper()
        print(
            json.dumps(
                {
                    "job_id": job_id,
                    "status": status,
                    "delayTime": data.get("delayTime"),
                    "executionTime": data.get("executionTime"),
                }
            )
        )
        if status in {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            return data
        if time.monotonic() > deadline:
            raise TimeoutError(f"Timed out waiting for {job_id}; last status={status}")
        time.sleep(poll_seconds)


def _output_dict(status: Dict[str, Any]) -> Dict[str, Any]:
    output = status.get("output")
    return output if isinstance(output, dict) else {}


def _extract_video_url(status: Dict[str, Any]) -> Optional[str]:
    video_url = _output_dict(status).get("video_url")
    return video_url if isinstance(video_url, str) and video_url.startswith("https://") else None


def _ffprobe_streams(video_url: str) -> Optional[Dict[str, Any]]:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,duration",
                "-of",
                "json",
                video_url,
            ],
            check=True,
            text=True,
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError:
        return None
    except subprocess.CalledProcessError:
        return {"streams": []}

    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {"streams": []}
    return data if isinstance(data, dict) else {"streams": []}


def _verify_streams(video_url: str) -> Dict[str, Any]:
    data = _ffprobe_streams(video_url)
    if data is None:
        return {"ffprobe_available": False, "has_video": None, "has_audio": None}
    streams = data.get("streams")
    if not isinstance(streams, list):
        streams = []
    return {
        "ffprobe_available": True,
        "has_video": any(stream.get("codec_type") == "video" for stream in streams if isinstance(stream, dict)),
        "has_audio": any(stream.get("codec_type") == "audio" for stream in streams if isinstance(stream, dict)),
        "streams": streams,
        "format": data.get("format") if isinstance(data.get("format"), dict) else {},
    }


def _download_output(video_url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(video_url, stream=True, timeout=600) as response:
        response.raise_for_status()
        with destination.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output_file.write(chunk)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit and poll BFS V2 first-frame-anchor RunPod smoke jobs.")
    parser.add_argument("--endpoint-id", required=True)
    parser.add_argument("--workflow-id", default=BFS_V2_WORKFLOW_ID)
    parser.add_argument("--source-face-image-url", help="HTTPS URL for the source face/head image.")
    parser.add_argument("--target-video-url", help="Fresh HTTPS URL for the target guide MP4.")
    parser.add_argument("--prewarm", action="store_true", help="Only prewarm core models for --workflow-id.")
    parser.add_argument("--prompt", help="Optional BFS V2 prompt. Defaults to the author trigger, head_swap.")
    parser.add_argument("--prompt-file", type=Path, help="Read optional BFS V2 prompt from a local file.")
    parser.add_argument("--negative-prompt")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--fps", type=int)
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--base-resolution", type=int)
    parser.add_argument("--skip-first-frames", type=int, default=0)
    parser.add_argument("--debug-outputs", action="store_true")
    parser.add_argument("--skip-url-preflight", action="store_true", help="Skip source/target URL reachability checks.")
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument("--verify-audio", action="store_true", help="Run ffprobe against completed MP4 URLs when available.")
    parser.add_argument("--download-output", type=Path, help="Download the final MP4 to this local path.")
    parser.add_argument("--output-jsonl", type=Path)
    args = parser.parse_args(argv)
    if args.workflow_id != BFS_V2_WORKFLOW_ID:
        raise SystemExit(f"--workflow-id must be {BFS_V2_WORKFLOW_ID}")
    if not args.prewarm and not args.source_face_image_url:
        raise SystemExit("--source-face-image-url is required unless --prewarm is set")
    if not args.prewarm and not args.target_video_url:
        raise SystemExit("--target-video-url is required unless --prewarm is set")
    if args.prompt and args.prompt_file:
        raise SystemExit("Use either --prompt or --prompt-file, not both")
    return args


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    if not args.prewarm and not args.skip_url_preflight:
        _preflight_url("source_face_image_url", args.source_face_image_url)
        _preflight_url("target_video_url", args.target_video_url)

    api_key = _read_runpod_api_key()
    payload = _build_payload(args)
    job_id = _submit(args.endpoint_id, api_key, payload)
    status = _poll(args.endpoint_id, api_key, job_id, args.timeout_seconds, args.poll_seconds)
    output = status.get("output")
    output_dict = output if isinstance(output, dict) else {}
    record: Dict[str, Any] = {
        "endpoint_id": args.endpoint_id,
        "job_id": job_id,
        "workflow_id": args.workflow_id,
        "status": status.get("status"),
        "delayTime": status.get("delayTime"),
        "executionTime": status.get("executionTime"),
        "output": output,
        "error": status.get("error"),
    }

    model_metadata = output_dict.get("model_metadata") if isinstance(output_dict.get("model_metadata"), dict) else {}
    if model_metadata:
        record["audio_status"] = model_metadata.get("audio_status")
        record["frame_settings"] = model_metadata.get("frame_settings")

    video_url = _extract_video_url(status)
    if video_url:
        record["video_url"] = video_url
        if args.verify_audio:
            record["ffprobe"] = _verify_streams(video_url)
        if args.download_output:
            _download_output(video_url, args.download_output)
            record["downloaded_output"] = str(args.download_output)

    print(json.dumps(record, ensure_ascii=True))
    if args.output_jsonl:
        args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.output_jsonl.open("a", encoding="utf-8") as output_file:
            output_file.write(json.dumps(record, ensure_ascii=True) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
