from pathlib import Path
import unittest


class DockerfileStartupTests(unittest.TestCase):
    def test_dockerfile_executes_start_sh_directly(self):
        dockerfile = Path(__file__).with_name("Dockerfile").read_text(encoding="utf-8")

        self.assertIn('CMD ["/start.sh"]', dockerfile)

    def test_dockerfile_uses_native_github_path_without_ghcr(self):
        dockerfile = Path(__file__).with_name("Dockerfile").read_text(encoding="utf-8")

        self.assertNotIn("ghcr.io", dockerfile.lower())
        self.assertNotIn("docker push", dockerfile.lower())

    def test_dockerfile_pins_required_custom_nodes(self):
        dockerfile = Path(__file__).with_name("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("git checkout c011fb520c79b9dfbe7f885d613771774f746eef", dockerfile)
        self.assertIn("https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git", dockerfile)
        self.assertIn("https://github.com/Lightricks/ComfyUI-LTXVideo.git", dockerfile)
        self.assertIn("https://github.com/kijai/ComfyUI-KJNodes.git", dockerfile)
        self.assertIn("https://github.com/city96/ComfyUI-GGUF.git", dockerfile)
        self.assertIn("https://github.com/kijai/ComfyUI-MelBandRoFormer.git", dockerfile)
        self.assertIn("https://github.com/1038lab/ComfyUI-RMBG.git", dockerfile)
        self.assertIn("https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes.git", dockerfile)
        self.assertIn("https://github.com/chflame163/ComfyUI_LayerStyle.git", dockerfile)
        self.assertIn("https://github.com/cubiq/ComfyUI_essentials.git", dockerfile)
        self.assertIn("https://github.com/yolain/ComfyUI-Easy-Use.git", dockerfile)
        self.assertIn("https://github.com/alisson-anjos/ComfyUI-BFSNodes.git", dockerfile)

    def test_dockerfile_vendors_video_output_bridge_node(self):
        dockerfile = Path(__file__).with_name("Dockerfile").read_text(encoding="utf-8")

        self.assertIn(
            "COPY vendor/ComfyUI-VideoOutputBridge /comfyui/custom_nodes/ComfyUI-VideoOutputBridge",
            dockerfile,
        )

    def test_dockerfile_sets_pythonpath_for_handler_imports(self):
        dockerfile = Path(__file__).with_name("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("ENV PYTHONPATH=/opt/bfs-v2", dockerfile)
        self.assertIn("ENV ASSET_MANIFEST_PATH=/opt/bfs-v2/asset-manifest.json", dockerfile)
        self.assertIn("ENV NETWORK_VOLUME_ROOT=/workspace", dockerfile)
        self.assertIn("COPY workflow_builder.py /opt/bfs-v2/workflow_builder.py", dockerfile)
        self.assertIn("COPY workflows /opt/bfs-v2/workflows", dockerfile)

    def test_dockerfile_documents_flux_klein_download_override(self):
        dockerfile = Path(__file__).with_name("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("CEL-200 test-time download-source override", dockerfile)
        self.assertIn("ENV BFS_V2_FLUX_KLEIN_URL=", dockerfile)
        self.assertIn("flux-2-klein-9b-fp8.safetensors", dockerfile)


if __name__ == "__main__":
    unittest.main()
