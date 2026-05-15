import contextlib
import io
import unittest
from unittest.mock import Mock, patch

from scripts import smoke_submit


class SmokeSubmitTests(unittest.TestCase):
    def test_preflight_uses_get_range_and_accepts_reachable_url(self):
        response = Mock()
        response.status_code = 206
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch.object(smoke_submit.requests, "get", return_value=response) as get:
            smoke_submit._preflight_url("target_video_url", "https://cdn.example.com/video.mp4?sig=redacted")

        get.assert_called_once()
        _, kwargs = get.call_args
        self.assertEqual(kwargs["headers"], {"Range": "bytes=0-0"})
        self.assertTrue(kwargs["stream"])

    def test_preflight_rejects_expired_or_forbidden_url_without_echoing_url(self):
        response = Mock()
        response.status_code = 403
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch.object(smoke_submit.requests, "get", return_value=response), self.assertRaises(SystemExit) as raised:
            smoke_submit._preflight_url("target_video_url", "https://cdn.example.com/video.mp4?secret=do-not-echo")

        self.assertEqual(str(raised.exception), "target_video_url failed preflight with HTTP 403")
        self.assertNotIn("do-not-echo", str(raised.exception))

    def test_main_prewarm_skips_input_url_preflight(self):
        with patch.object(smoke_submit, "_read_runpod_api_key", return_value="rp_redacted"), patch.object(
            smoke_submit, "_submit", return_value="job-123"
        ), patch.object(
            smoke_submit, "_poll", return_value={"status": "COMPLETED", "output": {"ok": True}}
        ), patch.object(smoke_submit, "_preflight_url") as preflight, contextlib.redirect_stdout(io.StringIO()):
            result = smoke_submit.main(["--endpoint-id", "endpoint-123", "--prewarm"])

        self.assertEqual(result, 0)
        preflight.assert_not_called()

    def test_rejects_both_target_url_and_r2_key(self):
        with self.assertRaises(SystemExit) as raised:
            smoke_submit.parse_args(
                [
                    "--endpoint-id",
                    "endpoint-123",
                    "--source-face-image-url",
                    "https://cdn.example.com/face.jpg",
                    "--target-video-url",
                    "https://cdn.example.com/video.mp4",
                    "--target-video-r2-key",
                    "videos/video.mp4",
                ]
            )

        self.assertEqual(
            str(raised.exception),
            "Use exactly one of --target-video-url or --target-video-r2-key unless --prewarm is set",
        )

    def test_target_video_r2_key_is_signed_in_memory(self):
        args = smoke_submit.parse_args(
            [
                "--endpoint-id",
                "endpoint-123",
                "--source-face-image-url",
                "https://cdn.example.com/face.jpg",
                "--target-video-r2-key",
                "videos/video.mp4",
            ]
        )
        with patch.object(smoke_submit, "_load_env_file") as load_env, patch.object(
            smoke_submit, "_config_from_env", return_value={"bucket": "celebmakerai-user-media"}
        ) as config_from_env, patch.object(
            smoke_submit, "_build_presigned_url", return_value="https://signed.example.com/video.mp4"
        ) as build_presigned_url:
            url = smoke_submit._resolve_target_video_url(args)

        self.assertEqual(url, "https://signed.example.com/video.mp4")
        load_env.assert_called_once_with(None)
        config_from_env.assert_called_once_with(None)
        build_presigned_url.assert_called_once_with(
            {"bucket": "celebmakerai-user-media"},
            "videos/video.mp4",
            3600,
        )

    def test_main_uses_signed_r2_key_without_echoing_url(self):
        with patch.object(smoke_submit, "_read_runpod_api_key", return_value="rp_redacted"), patch.object(
            smoke_submit, "_build_presigned_url", return_value="https://signed.example.com/video.mp4?secret=do-not-echo"
        ), patch.object(smoke_submit, "_config_from_env", return_value={"bucket": "celebmakerai-user-media"}), patch.object(
            smoke_submit, "_preflight_url"
        ) as preflight, patch.object(
            smoke_submit, "_submit", return_value="job-123"
        ) as submit, patch.object(
            smoke_submit, "_poll", return_value={"status": "COMPLETED", "output": {"ok": True}}
        ), contextlib.redirect_stdout(io.StringIO()) as stdout:
            result = smoke_submit.main(
                [
                    "--endpoint-id",
                    "endpoint-123",
                    "--source-face-image-url",
                    "https://cdn.example.com/face.jpg",
                    "--target-video-r2-key",
                    "videos/video.mp4",
                ]
            )

        self.assertEqual(result, 0)
        preflight.assert_any_call("target_video_url", "https://signed.example.com/video.mp4?secret=do-not-echo")
        payload = submit.call_args.args[2]
        self.assertEqual(
            payload["input"]["target_video_url"],
            "https://signed.example.com/video.mp4?secret=do-not-echo",
        )
        self.assertNotIn("do-not-echo", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
