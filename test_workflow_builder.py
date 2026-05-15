import hashlib
import unittest

import workflow_builder


class BfsV2WorkflowBuilderTests(unittest.TestCase):
    def test_builds_first_frame_anchor_workflow_from_source_graph(self):
        result = workflow_builder.build_bfs_v2_job_input(
            {
                "workflow_id": workflow_builder.BFS_V2_WORKFLOW_ID,
                "source_face_image": "https://cdn.example.com/input/source.png?token=redacted",
                "target_video_url": "https://cdn.example.com/input/target.mp4?token=redacted",
                "seed": 42,
                "source_video_duration": 5.0,
                "source_video_width": 1280,
                "source_video_height": 720,
                "source_video_has_audio": True,
                "source_video_sha256": "abc123",
            }
        )
        built = result["workflow"]
        class_types = {node["class_type"] for node in built.values()}

        self.assertEqual(result["workflow_id"], workflow_builder.BFS_V2_WORKFLOW_ID)
        self.assertEqual(result["workflow_version"], workflow_builder.BFS_V2_WORKFLOW_VERSION)
        self.assertEqual(result["seed"], 42)
        self.assertEqual(result["settings"]["frame_count"], 121)
        self.assertEqual(result["model_downloads"][0]["relative_path"], "input")
        self.assertEqual(result["model_downloads"][1]["relative_path"], "input")
        self.assertEqual(result["model_metadata"]["source_workflow_sha256"], workflow_builder.BFS_V2_SOURCE_WORKFLOW_SHA256)
        self.assertEqual(result["model_metadata"]["target_video_hash"], "abc123")
        self.assertTrue(result["model_metadata"]["target_video_has_audio"])
        self.assertEqual(result["model_metadata"]["audio_status"], "source_video_audio_muxed")
        self.assertEqual(
            result["model_metadata"]["operating_mode"],
            "first_frame_head_swap_anchor_recommended_by_author",
        )

        self.assertIn("SAM3Segment", class_types)
        self.assertIn("LTXVAddGuideMulti", class_types)
        self.assertIn("LTXVAudioVAEEncode", class_types)
        self.assertIn("LTXVConcatAVLatent", class_types)
        self.assertIn("VHS_LoadVideo", class_types)
        self.assertIn("VHS_VideoCombine", class_types)
        self.assertIn("VideoOutputBridge", class_types)
        self.assertIn("LoraLoaderModelOnly", class_types)
        self.assertNotIn("Power Lora Loader (rgthree)", class_types)
        self.assertNotIn("GetNode", class_types)
        self.assertNotIn("SetNode", class_types)
        self.assertNotIn("5335b611-140f-4011-920c-8aa336974181", class_types)
        self.assertNotIn("148968b9-9ce1-4a1f-876a-d28c0d0e330c", class_types)

        self.assertEqual(built["13"]["inputs"]["image"], "source-1011adc3ba34.png")
        self.assertEqual(built["28"]["inputs"]["video"], "target-6fcc99761d10.mp4")
        self.assertEqual(built["28"]["inputs"]["skip_first_frames"], 0)
        self.assertEqual(built["149207"]["inputs"]["lora_name"], workflow_builder.BFS_V2_FLUX_HEAD_LORA_NAME)
        self.assertEqual(built["149193"]["inputs"]["samples"], ["149189", 0])
        self.assertEqual(built["351"]["inputs"]["images"], ["481", 0])
        self.assertEqual(built["351"]["inputs"]["filename_prefix"], f"{workflow_builder.BFS_V2_WORKFLOW_ID}_final")
        self.assertEqual(built["9901"]["inputs"]["filenames"], ["351", 0])

    def test_preserves_creator_model_names_and_lora_strengths(self):
        result = workflow_builder.build_bfs_v2_job_input(
            {
                "workflow_id": workflow_builder.BFS_V2_WORKFLOW_ID,
                "source_face_image_url": "https://cdn.example.com/source.png",
                "target_video_url": "https://cdn.example.com/target.mp4",
            }
        )
        built = result["workflow"]

        self.assertEqual(built["687"]["inputs"]["unet_name"], workflow_builder.BFS_V2_LTX_TRANSFORMER_NAME)
        self.assertEqual(built["3"]["inputs"]["clip_name1"], workflow_builder.BFS_V2_TEXT_ENCODER_NAME)
        self.assertEqual(built["3"]["inputs"]["clip_name2"], workflow_builder.BFS_V2_TEXT_CONNECTOR_NAME)
        self.assertEqual(built["4"]["inputs"]["vae_name"], workflow_builder.BFS_V2_VIDEO_VAE_NAME)
        self.assertEqual(built["5"]["inputs"]["vae_name"], workflow_builder.BFS_V2_AUDIO_VAE_NAME)
        self.assertEqual(built["7401"]["inputs"]["lora_name"], workflow_builder.BFS_V2_DISTILLED_LORA_NAME)
        self.assertEqual(built["7401"]["inputs"]["strength_model"], 0.6)
        self.assertEqual(built["7402"]["inputs"]["lora_name"], workflow_builder.BFS_V2_HEAD_SWAP_LORA_NAME)
        self.assertEqual(built["7402"]["inputs"]["strength_model"], 1.0)
        self.assertEqual(built["149206"]["inputs"]["unet_name"], workflow_builder.BFS_V2_FLUX_KLEIN_NAME)
        self.assertEqual(built["149205"]["inputs"]["clip_name"], workflow_builder.BFS_V2_FLUX_TEXT_ENCODER_NAME)
        self.assertEqual(built["149196"]["inputs"]["vae_name"], workflow_builder.BFS_V2_FLUX_VAE_NAME)

    def test_debug_outputs_add_first_pass_and_comparison_bridges(self):
        result = workflow_builder.build_bfs_v2_job_input(
            {
                "workflow_id": workflow_builder.BFS_V2_WORKFLOW_ID,
                "source_face_image": "https://cdn.example.com/source.png",
                "target_video_url": "https://cdn.example.com/target.mp4",
                "debug_outputs": True,
            }
        )

        self.assertEqual(result["model_metadata"]["debug_output_labels"], ["first_pass", "comparison"])
        self.assertEqual(result["workflow"]["9902"]["inputs"]["filenames"], ["120", 0])
        self.assertEqual(result["workflow"]["9903"]["inputs"]["filenames"], ["180", 0])

    def test_rejects_missing_inputs(self):
        with self.assertRaises(workflow_builder.BfsV2WorkflowInputError):
            workflow_builder.build_bfs_v2_job_input(
                {
                    "workflow_id": workflow_builder.BFS_V2_WORKFLOW_ID,
                    "target_video_url": "https://cdn.example.com/target.mp4",
                }
            )

        with self.assertRaises(workflow_builder.BfsV2WorkflowInputError):
            workflow_builder.build_bfs_v2_job_input(
                {
                    "workflow_id": workflow_builder.BFS_V2_WORKFLOW_ID,
                    "source_face_image": "https://cdn.example.com/source.png",
                }
            )

    def test_source_workflow_hash_matches_downloaded_hugging_face_file(self):
        digest = hashlib.sha256(workflow_builder.BFS_V2_SOURCE_TEMPLATE_PATH.read_bytes()).hexdigest()

        self.assertEqual(digest, workflow_builder.BFS_V2_SOURCE_WORKFLOW_SHA256)


if __name__ == "__main__":
    unittest.main()
