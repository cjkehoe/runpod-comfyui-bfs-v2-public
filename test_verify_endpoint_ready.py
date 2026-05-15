import unittest

from scripts import verify_endpoint_ready


class VerifyEndpointReadyTests(unittest.TestCase):
    def test_verify_accepts_ready_endpoint(self):
        result = verify_endpoint_ready.verify(
            endpoint={
                "id": "endpoint",
                "templateId": "template",
                "workersMax": 1,
                "workersMin": 0,
            },
            template={
                "id": "template",
                "containerDiskInGb": 150,
                "env": {key: "redacted" for key in verify_endpoint_ready.REQUIRED_TEMPLATE_ENV_KEYS},
            },
            prewarm_job={"id": "job", "status": "COMPLETED"},
            expected_template_id="template",
            required_env_keys=verify_endpoint_ready.REQUIRED_TEMPLATE_ENV_KEYS,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["missingEnvKeys"], [])
        self.assertTrue(result["checks"]["prewarm_job_completed"])

    def test_verify_reports_missing_env_without_values(self):
        result = verify_endpoint_ready.verify(
            endpoint={"id": "endpoint", "templateId": "template", "workersMax": 1},
            template={
                "id": "template",
                "containerDiskInGb": 150,
                "env": {"HF_TOKEN": "do-not-print"},
            },
            prewarm_job={"id": "job", "status": "COMPLETED"},
            expected_template_id="template",
            required_env_keys=verify_endpoint_ready.REQUIRED_TEMPLATE_ENV_KEYS,
        )

        self.assertFalse(result["ok"])
        self.assertIn("BFS_V2_FLUX_KLEIN_URL", result["missingEnvKeys"])
        self.assertNotIn("do-not-print", str(result))

    def test_verify_flags_disabled_workers_and_failed_prewarm(self):
        result = verify_endpoint_ready.verify(
            endpoint={"id": "endpoint", "templateId": "template", "workersMax": 0},
            template={
                "id": "template",
                "containerDiskInGb": 150,
                "env": {key: "redacted" for key in verify_endpoint_ready.REQUIRED_TEMPLATE_ENV_KEYS},
            },
            prewarm_job={"id": "job", "status": "FAILED"},
            expected_template_id="template",
            required_env_keys=verify_endpoint_ready.REQUIRED_TEMPLATE_ENV_KEYS,
        )

        self.assertFalse(result["ok"])
        self.assertFalse(result["checks"]["workers_max_allows_jobs"])
        self.assertFalse(result["checks"]["prewarm_job_completed"])


if __name__ == "__main__":
    unittest.main()
