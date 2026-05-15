# CEL-200 BFS V2 Final Report Draft

## Local / GitHub / RunPod

- Local repo: `/Users/chriskehoe/Documents/Repositories/Empire/runpod/runpod-comfyui-bfs-v2`
- Private GitHub repo: `https://github.com/cjkehoe/runpod-comfyui-bfs-v2`
- Public RunPod GitHub repo: `https://github.com/cjkehoe/runpod-comfyui-bfs-v2-public`
- Branch: `main`
- Current commit: see `git rev-parse --short HEAD`
- RunPod endpoint: `0apsddjr33ry7p` / `runpod-comfyui-bfs-v2-public`
- RunPod template: `27upkmyvti`
- Template image observed: `registry.runpod.net/cjkehoe-runpod-comfyui-bfs-v2-public-main-dockerfile:80877f353`
- Endpoint config: `workersMax: 1`, `workersMin: 0`, no network volume, 150 GB container disk, H100 80GB-class GPU pool, 2-hour execution timeout
- Template env keys include `HF_TOKEN`, `BFS_V2_FLUX_KLEIN_URL`, and the `runpod/worker-comfyui` output bucket keys used by the working I2V template.

## Workflow Source

- Workflow ID: `bfs_ltx23_head_swap_v2`
- Workflow version: `alissonerdx_bfs_v2_first_frame_anchor_v1`
- Model card: `https://huggingface.co/Alissonerdx/BFS-Best-Face-Swap-Video`
- Source workflow: `https://huggingface.co/Alissonerdx/BFS-Best-Face-Swap-Video/blob/main/workflows/workflow_ltx2_head_swap_drag_and_drop_v2.0.json`
- Preserved source JSON: `workflows/workflow_ltx2_head_swap_drag_and_drop_v2.0.source.json`
- Source JSON SHA256: `fd6a297e56a9a794c63df6bc4bd9c837f99ebd7937ac2e8214ee1731a13a741e`

## Operating Mode

V2 first-frame head-swap anchoring is used. The endpoint accepts a source face/head image and target video, extracts the first target frame, runs the author workflow's embedded Flux/Klein first-frame head-swap subgraph, and feeds that swapped first-frame anchor into the LTX-2 V2 video head-swap pass.

Direct photo conditioning is documented by the source workflow as possible, but this endpoint uses the author/community recommended first-frame anchoring path for V2 reliability. V3 was not substituted.

## Source Graph Changes

The original source JSON is preserved unchanged. Runtime adaptations are limited to serverless/API execution:

- Convert UI workflow routing into a ComfyUI API prompt at request time.
- Expand embedded subgraphs needed by the V2 first-frame path.
- Convert rgthree Power Lora Loader nodes into sequential `LoraLoaderModelOnly` nodes.
- Replace demo media filenames with request-staged `source_face_image_url` and `target_video_url`.
- Default `skip_first_frames` to `0` rather than the source demo clip's sample-specific `15`.
- Add local `VideoOutputBridge` after the creator's final MP4 node so RunPod can return an uploaded MP4 URL.
- Preserve target-video audio through the creator's final mux path when present.

## Assets

Required custom nodes and model files are declared in `asset-manifest.json` and pinned in the Dockerfile. The primary model set includes:

- `flux-2-klein-9b-fp8.safetensors`
- `bfs_head_v1_flux-klein_9b_step3500_rank128.safetensors`
- `qwen_3_8b_fp8mixed.safetensors`
- `flux2-vae.safetensors`
- `ltx-2-19b-dev-fp8_transformer_only.safetensors`
- `gemma_3_12B_it_fp8_scaled.safetensors`
- `ltx-2-19b-embeddings_connector_dev_bf16.safetensors`
- `LTX2_video_vae_bf16.safetensors`
- `LTX2_audio_vae_bf16.safetensors`
- `ltx-2-19b-distilled-lora_resized_dynamic_fro09_avg_rank_175_bf16.safetensors`
- `head_swap_ltx2_v2.safetensors`
- `ltx-2-spatial-upscaler-x2-1.0.safetensors`
- `MelBandRoformer_fp32.safetensors`

The Black Forest Labs Flux Klein upstream URL returned 403 even with `HF_TOKEN`, so the experiment template has `BFS_V2_FLUX_KLEIN_URL` set to a public mirror of the same filename. The workflow graph, model filename, first-frame method, and V2 LoRAs remain unchanged.

## Validation Completed

- `python -m unittest -v` passes 26 tests.
- `python -m compileall .` passes.
- `python -m json.tool asset-manifest.json >/dev/null` passes.
- `python -m json.tool workflows/workflow_ltx2_head_swap_drag_and_drop_v2.0.source.json >/dev/null` passes.
- `git diff --check` passes.
- `python -u scripts/verify_endpoint_ready.py` returns `ok: true` against the live endpoint/template and prewarm job.
- Prewarm completed on RunPod job `4c3690e4-ab6f-442b-8ff7-46da0954cb35-e1`.
  - Queue delay: `205120` ms
  - Execution time: `881093` ms
  - Downloaded core model paths: `models/diffusion_models`, `models/latent_upscale_models`, `models/loras`, `models/loras/ltx-2`, `models/text_encoders`, `models/vae`

Cache caveat: there is no network volume and `workersMin` is zero, so prewarm proves that the full model set can download successfully but does not guarantee persistence until a future smoke job.

## Test Input Status

- Source face image: reachable over HTTPS.
- Target video: the supplied signed R2 URL is expired and returns HTTP 403.
- Production Supabase confirms the exact object exists in `generated_videos` as private `celebmakerai-user-media`, with `video_url`, `r2_object_name`, and `video_storage_key` all pointing to the same object key.
- A successful `media_backup_jobs` row exists for the same object, but only private backup bucket/key metadata is available from this environment; common public S3 URL forms returned 404.

## Smoke Test Status

Blocked until a fresh signed target MP4 URL or approved R2 signing credentials are available.

Prepared smoke command when approved R2 env is present:

```bash
python -u scripts/smoke_submit.py \
  --endpoint-id 0apsddjr33ry7p \
  --source-face-image-url '<face image URL>' \
  --target-video-r2-key videos/d58e5d9e-1a89-4652-96e3-f37505cbf0c7_65dad7b8c1b44de2.mp4 \
  --verify-audio \
  --download-output outputs/bfs-v2-smoke.mp4 \
  --output-jsonl .runpod-results/smoke-$(date -u +%Y%m%dT%H%M%SZ).jsonl
```

## Pending Final Fields

- Output MP4 URL/path: pending real smoke.
- `ffprobe` summary: pending real smoke.
- Generation runtime: pending real smoke.
- GPU/worker type actually used for generation: pending real smoke.
- Approximate model disk usage during generation: expected to fit within 150 GB container disk based on prewarm; final measurement pending real smoke.
- OOM/performance issues: none observed during prewarm; generation pending.
- Quality notes: pending real smoke.

## Recommendation

Keep testing. Do not reject or promote yet. The endpoint is built and prewarm-proven, but the core proof requirement has not been met because the private target video URL is expired and no approved signing credentials are available in this environment.
