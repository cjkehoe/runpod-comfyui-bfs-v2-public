import os
import unittest
from unittest.mock import Mock, patch

from scripts import sign_user_media_url


class SignUserMediaUrlTests(unittest.TestCase):
    def test_config_from_env_accepts_cloudflare_names(self):
        env = {
            "CLOUDFLARE_ACCOUNT_ID": "account",
            "CLOUDFLARE_R2_ACCESS_KEY_ID": "access",
            "CLOUDFLARE_R2_SECRET_ACCESS_KEY": "secret",
            "CLOUDFLARE_R2_USER_MEDIA_BUCKET": "celebmakerai-user-media",
        }
        with patch.dict(os.environ, env, clear=True):
            config = sign_user_media_url._config_from_env(None)

        self.assertEqual(config["account_id"], "account")
        self.assertEqual(config["access_key_id"], "access")
        self.assertEqual(config["secret_access_key"], "secret")
        self.assertEqual(config["bucket"], "celebmakerai-user-media")

    def test_missing_config_exits_without_secret_echo(self):
        with patch.dict(os.environ, {"CLOUDFLARE_R2_SECRET_ACCESS_KEY": "do-not-echo"}, clear=True):
            with self.assertRaises(SystemExit) as raised:
                sign_user_media_url._config_from_env(None)

        message = str(raised.exception)
        self.assertIn("missing required R2 config", message)
        self.assertNotIn("do-not-echo", message)

    def test_rejects_url_as_key(self):
        with self.assertRaises(SystemExit) as raised:
            sign_user_media_url.parse_args(["--key", "https://example.com/video.mp4"])

        self.assertEqual(str(raised.exception), "--key must be an R2 object key, not a URL")

    def test_build_presigned_url_uses_bucket_and_key(self):
        client = Mock()
        client.generate_presigned_url.return_value = "https://signed.example.com/video.mp4"

        with patch.dict(
            "sys.modules",
            {
                "boto3": Mock(client=Mock(return_value=client)),
                "botocore.config": Mock(Config=Mock(return_value="config")),
            },
        ):
            url = sign_user_media_url._build_presigned_url(
                {
                    "account_id": "account",
                    "access_key_id": "access",
                    "secret_access_key": "secret",
                    "bucket": "celebmakerai-user-media",
                },
                "videos/target.mp4",
                3600,
            )

        self.assertEqual(url, "https://signed.example.com/video.mp4")
        client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "celebmakerai-user-media", "Key": "videos/target.mp4"},
            ExpiresIn=3600,
        )


if __name__ == "__main__":
    unittest.main()
