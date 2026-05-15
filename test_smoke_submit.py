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


if __name__ == "__main__":
    unittest.main()
