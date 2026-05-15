#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.smoke_submit import _read_runpod_api_key


REQUIRED_TEMPLATE_ENV_KEYS = {
    "BFS_V2_FLUX_KLEIN_URL",
    "HF_TOKEN",
    "BUCKET_ENDPOINT_URL",
    "BUCKET_ACCESS_KEY_ID",
    "BUCKET_SECRET_ACCESS_KEY",
    "OUTPUT_BUCKET_NAME",
    "OUTPUT_PUBLIC_BASE",
}


def _request_json(url: str, api_key: str) -> Dict[str, Any]:
    response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"RunPod returned non-object JSON from {url}")
    return data


def _missing(required: Iterable[str], actual: Iterable[str]) -> List[str]:
    return sorted(set(required) - set(actual))


def _status(ok: bool) -> str:
    return "ok" if ok else "failed"


def _endpoint_summary(endpoint: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": endpoint.get("id"),
        "name": endpoint.get("name"),
        "templateId": endpoint.get("templateId"),
        "workersMin": endpoint.get("workersMin"),
        "workersMax": endpoint.get("workersMax"),
        "workersStandby": endpoint.get("workersStandby"),
        "networkVolumeId": endpoint.get("networkVolumeId"),
        "executionTimeoutMs": endpoint.get("executionTimeoutMs"),
        "gpuTypeIds": endpoint.get("gpuTypeIds"),
    }


def _template_summary(template: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": template.get("id"),
        "name": template.get("name"),
        "imageName": template.get("imageName"),
        "containerDiskInGb": template.get("containerDiskInGb"),
        "volumeMountPath": template.get("volumeMountPath"),
        "envKeys": sorted((template.get("env") or {}).keys()),
    }


def _job_summary(job: Dict[str, Any]) -> Dict[str, Any]:
    return {key: job.get(key) for key in ("id", "status", "delayTime", "executionTime", "workerId")}


def _read_template(template_id: str) -> Dict[str, Any]:
    output = subprocess.check_output(["runpodctl", "template", "get", template_id], text=True)
    data = json.loads(output)
    if not isinstance(data, dict):
        raise RuntimeError(f"runpodctl returned non-object template JSON for {template_id}")
    return data


def verify(
    *,
    endpoint: Dict[str, Any],
    template: Dict[str, Any],
    prewarm_job: Dict[str, Any] | None,
    expected_template_id: str,
    required_env_keys: Set[str],
) -> Dict[str, Any]:
    env_keys = set((template.get("env") or {}).keys())
    missing_env_keys = _missing(required_env_keys, env_keys)
    workers_max = endpoint.get("workersMax")
    container_disk = template.get("containerDiskInGb")

    checks = {
        "endpoint_template_matches": endpoint.get("templateId") == expected_template_id,
        "workers_max_allows_jobs": isinstance(workers_max, int) and workers_max >= 1,
        "template_has_required_env_keys": not missing_env_keys,
        "template_container_disk_at_least_150gb": isinstance(container_disk, int) and container_disk >= 150,
    }

    if prewarm_job is not None:
        checks["prewarm_job_completed"] = str(prewarm_job.get("status") or "").upper() == "COMPLETED"

    return {
        "ok": all(checks.values()),
        "checks": checks,
        "missingEnvKeys": missing_env_keys,
        "endpoint": _endpoint_summary(endpoint),
        "template": _template_summary(template),
        "prewarmJob": _job_summary(prewarm_job) if prewarm_job else None,
    }


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify sanitized BFS V2 RunPod endpoint readiness.")
    parser.add_argument("--endpoint-id", default="0apsddjr33ry7p")
    parser.add_argument("--template-id", default="27upkmyvti")
    parser.add_argument("--prewarm-job-id", default="8d4d5d25-60ed-425f-89b0-b18acf43c82b-e2")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    api_key = _read_runpod_api_key()
    endpoint = _request_json(f"https://rest.runpod.io/v1/endpoints/{args.endpoint_id}", api_key)
    template = _read_template(args.template_id)
    prewarm_job = (
        _request_json(f"https://api.runpod.ai/v2/{args.endpoint_id}/status/{args.prewarm_job_id}", api_key)
        if args.prewarm_job_id
        else None
    )
    result = verify(
        endpoint=endpoint,
        template=template,
        prewarm_job=prewarm_job,
        expected_template_id=args.template_id,
        required_env_keys=REQUIRED_TEMPLATE_ENV_KEYS,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
