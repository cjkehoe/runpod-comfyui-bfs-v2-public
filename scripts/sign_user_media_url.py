#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional


DEFAULT_TARGET_KEY = "videos/d58e5d9e-1a89-4652-96e3-f37505cbf0c7_65dad7b8c1b44de2.mp4"


def _load_env_file(path: Optional[Path]) -> None:
    if not path:
        return
    if not path.exists():
        raise SystemExit(f"env file does not exist: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def _first_env(names: Iterable[str]) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _config_from_env(bucket_override: Optional[str]) -> Dict[str, str]:
    config = {
        "account_id": _first_env(["CLOUDFLARE_ACCOUNT_ID", "R2_ACCOUNT_ID"]),
        "access_key_id": _first_env(["CLOUDFLARE_R2_ACCESS_KEY_ID", "R2_ACCESS_KEY_ID"]),
        "secret_access_key": _first_env(["CLOUDFLARE_R2_SECRET_ACCESS_KEY", "R2_SECRET_ACCESS_KEY"]),
        "bucket": (bucket_override or _first_env(["CLOUDFLARE_R2_USER_MEDIA_BUCKET", "R2_USER_MEDIA_BUCKET"])).strip(),
    }
    missing = [key for key, value in config.items() if not value]
    if missing:
        raise SystemExit(f"missing required R2 config: {', '.join(missing)}")
    return config


def _build_presigned_url(config: Dict[str, str], object_key: str, expires_in: int) -> str:
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise SystemExit("boto3 and botocore are required to sign R2 URLs") from exc

    client = boto3.client(
        "s3",
        region_name="auto",
        endpoint_url=f"https://{config['account_id']}.r2.cloudflarestorage.com",
        aws_access_key_id=config["access_key_id"],
        aws_secret_access_key=config["secret_access_key"],
        config=Config(signature_version="s3v4"),
    )
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": config["bucket"], "Key": object_key},
        ExpiresIn=expires_in,
    )


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mint a fresh signed R2 read URL for the CEL-200 target MP4.")
    parser.add_argument("--key", default=DEFAULT_TARGET_KEY, help="R2 object key to sign.")
    parser.add_argument("--bucket", help="Override R2 user-media bucket. Defaults to env.")
    parser.add_argument("--expires-in", type=int, default=3600, help="Signed URL TTL in seconds.")
    parser.add_argument("--env-file", type=Path, help="Optional local env file. Do not commit this file.")
    args = parser.parse_args(argv)
    if not args.key.strip() or args.key.startswith(("http://", "https://")):
        raise SystemExit("--key must be an R2 object key, not a URL")
    if args.expires_in < 60 or args.expires_in > 604800:
        raise SystemExit("--expires-in must be between 60 and 604800 seconds")
    return args


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    _load_env_file(args.env_file)
    config = _config_from_env(args.bucket)
    print(_build_presigned_url(config, args.key.strip().lstrip("/"), args.expires_in))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
