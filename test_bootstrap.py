import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load_bootstrap_module():
    module_path = Path(__file__).with_name("bootstrap.py")
    spec = importlib.util.spec_from_file_location("bfs_v2_bootstrap_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


bootstrap = load_bootstrap_module()


class BfsV2BootstrapTests(unittest.TestCase):
    def test_ensure_core_model_downloads_once_and_caches_to_network_volume(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            comfy_root = temp_path / "comfyui"
            network_volume_root = temp_path / "runpod-volume"
            network_volume_root.mkdir(parents=True, exist_ok=True)
            os.environ["BFS_TEST_MODEL_URL"] = "https://models.example.com/model.safetensors"

            def fake_download(url: str, destination: Path) -> None:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"core-model")

            with patch.object(bootstrap, "_download_file", side_effect=fake_download):
                bootstrap._ensure_core_model(
                    {
                        "filename": "model.safetensors",
                        "relative_path": "models/loras/test",
                        "url_env": "BFS_TEST_MODEL_URL",
                    },
                    comfy_root,
                    network_volume_root,
                )

            runtime_model = comfy_root / "models" / "loras" / "test" / "model.safetensors"
            cached_model = network_volume_root / "comfyui" / "models" / "loras" / "test" / "model.safetensors"

            self.assertEqual(runtime_model.read_bytes(), b"core-model")
            self.assertEqual(cached_model.read_bytes(), b"core-model")

    def test_optional_models_are_skipped_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch.object(bootstrap, "_download_file") as download:
                bootstrap._ensure_core_model(
                    {
                        "filename": "optional.safetensors",
                        "relative_path": "models/loras",
                        "default_url": "https://models.example.com/optional.safetensors",
                        "optional": True,
                    },
                    temp_path / "comfyui",
                    temp_path / "runpod-volume",
                )

            download.assert_not_called()

    def test_download_file_writes_part_file_then_renames(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "model.safetensors"

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    return False

                def raise_for_status(self):
                    return None

                def iter_content(self, chunk_size):
                    yield b"model"
                    self.partial_exists_during_stream = destination.with_name("model.safetensors.part").exists()
                    yield b"-bytes"

            response = FakeResponse()
            with patch.object(bootstrap.requests, "get", return_value=response) as request_get:
                bootstrap._download_file("https://models.example.com/model.safetensors", destination)

            request_get.assert_called_once()
            self.assertTrue(response.partial_exists_during_stream)
            self.assertEqual(destination.read_bytes(), b"model-bytes")
            self.assertFalse(destination.with_name("model.safetensors.part").exists())


if __name__ == "__main__":
    unittest.main()
