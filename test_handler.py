import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def load_handler_module(base_handler_path: Path):
    fake_runpod = types.ModuleType("runpod")
    fake_runpod.serverless = types.SimpleNamespace(start=lambda *args, **kwargs: None)
    sys.modules["runpod"] = fake_runpod

    os.environ["BASE_HANDLER_PATH"] = str(base_handler_path)

    module_path = Path(__file__).with_name("handler.py")
    spec = importlib.util.spec_from_file_location("bfs_v2_handler_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_stub_base_handler(temp_dir: Path) -> Path:
    base_handler_path = temp_dir / "handler_base_stub.py"
    base_handler_path.write_text("def handler(job):\n    return {'images': []}\n", encoding="utf-8")
    return base_handler_path


class BfsV2HandlerTests(unittest.TestCase):
    def test_bfs_payload_stages_inputs_builds_workflow_and_rewrites_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            handler = load_handler_module(write_stub_base_handler(temp_path))
            handler.COMFY_ROOT = temp_path / "comfyui"
            handler.NETWORK_VOLUME_ROOT = temp_path / "runpod-volume"
            handler.OUTPUT_PUBLIC_BASE = "https://cdn.example.com/videos"
            handler.OUTPUT_BUCKET_NAME = "videos"

            captured_job = {}

            def fake_base_handler(job):
                captured_job["value"] = job
                return {
                    "images": [
                        {
                            "filename": "bfs_ltx23_head_swap_v2_final_00001-audio.mp4",
                            "type": "s3_url",
                            "data": "https://account.r2.cloudflarestorage.com/videos/job-123/final.mp4",
                        }
                    ]
                }

            def fake_download(url: str, destination: Path) -> None:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(f"downloaded:{url}".encode("utf-8"))

            handler.BASE_HANDLER = fake_base_handler

            with patch.object(handler, "_ensure_core_models", return_value={"models/loras"}, create=True), patch.object(
                handler,
                "_download_file",
                side_effect=fake_download,
                create=True,
            ), patch.object(
                handler,
                "_probe_source_video",
                return_value={
                    "source_video_duration": 5.0,
                    "source_video_width": 1280,
                    "source_video_height": 720,
                    "source_video_frame_count": 120,
                    "source_video_fps": 24.0,
                    "source_video_has_audio": True,
                },
                create=True,
            ), patch.object(handler, "_refresh_comfy_file_cache", return_value=None, create=True):
                result = handler.handler(
                    {
                        "id": "runpod-job-123",
                        "input": {
                            "workflow_id": "bfs_ltx23_head_swap_v2",
                            "source_face_image_url": "https://cdn.example.com/source.png?token=redacted",
                            "target_video_url": "https://cdn.example.com/target.mp4?token=redacted",
                            "prompt": "head_swap:\n\nFACE:\nA reference identity.\n\nACTION:\nA person turns.",
                            "seed": 42,
                        }
                    }
                )

            staged_inputs = list((handler.COMFY_ROOT / "input").glob("*"))
            self.assertEqual(len(staged_inputs), 2)
            self.assertEqual(captured_job["value"]["id"], "runpod-job-123")
            self.assertIn("workflow", captured_job["value"]["input"])
            self.assertNotIn("model_downloads", captured_job["value"]["input"])
            self.assertEqual(result["workflow_id"], "bfs_ltx23_head_swap_v2")
            self.assertEqual(result["workflow_version"], "alissonerdx_bfs_v2_first_frame_anchor_v1")
            self.assertEqual(result["seed"], 42)
            self.assertEqual(result["video_url"], "https://cdn.example.com/videos/job-123/final.mp4")
            self.assertEqual(result["model_metadata"]["audio_status"], "source_video_audio_muxed")
            self.assertEqual(result["model_metadata"]["target_video_width"], 1280)
            self.assertEqual(result["model_metadata"]["target_video_height"], 720)

    def test_prewarm_uses_manifest_models_for_workflow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            handler = load_handler_module(write_stub_base_handler(temp_path))
            handler.NETWORK_VOLUME_ROOT = temp_path / "runpod-volume"

            with patch.object(handler, "_ensure_core_models", return_value={"models/diffusion_models"}, create=True), patch.object(
                handler, "_refresh_comfy_file_cache", return_value=None, create=True
            ):
                result = handler.handler(
                    {
                        "input": {
                            "action": "prewarm_core_models",
                            "workflow_id": "bfs_ltx23_head_swap_v2",
                        }
                    }
                )

            self.assertTrue(result["ok"])
            self.assertEqual(result["mode"], "prewarm_core_models")
            self.assertEqual(result["workflow_id"], "bfs_ltx23_head_swap_v2")
            self.assertEqual(result["downloaded_relative_paths"], ["models/diffusion_models"])

    def test_invalid_payload_returns_workflow_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            handler = load_handler_module(write_stub_base_handler(temp_path))

            result = handler.handler(
                {
                    "input": {
                        "workflow_id": "bfs_ltx23_head_swap_v2",
                        "target_video_url": "https://cdn.example.com/target.mp4",
                    }
                }
            )

            self.assertIn("source_face_image", result["error"])
            self.assertEqual(result["workflow_id"], "bfs_ltx23_head_swap_v2")


if __name__ == "__main__":
    unittest.main()
