# RunPod ComfyUI BFS V2 Worker

Isolated CEL-200 research worker for the Alissonerdx BFS Best-Face-Swap-Video V2 workflow.

## Workflow

- Workflow ID: `bfs_ltx23_head_swap_v2`
- Workflow version: `alissonerdx_bfs_v2_first_frame_anchor_v1`
- Source model/card: `https://huggingface.co/Alissonerdx/BFS-Best-Face-Swap-Video`
- Source workflow: `https://huggingface.co/Alissonerdx/BFS-Best-Face-Swap-Video/raw/main/workflows/workflow_ltx2_head_swap_drag_and_drop_v2.0.json`
- Preserved source JSON: `workflows/workflow_ltx2_head_swap_drag_and_drop_v2.0.source.json`
- Source JSON SHA256: `fd6a297e56a9a794c63df6bc4bd9c837f99ebd7937ac2e8214ee1731a13a741e`

## Request

```json
{
  "input": {
    "workflow_id": "bfs_ltx23_head_swap_v2",
    "source_face_image_url": "https://cdn.example.com/source-face.png",
    "target_video_url": "https://cdn.example.com/target.mp4",
    "prompt": "head_swap",
    "seed": 42,
    "debug_outputs": false
  }
}
```

`source_face_image`, `source_image`, `source_image_url`, `face_image`, and `image` are accepted aliases for `source_face_image_url`. `video_url` and `video` are accepted aliases for `target_video_url`.

## Preserved V2 Behavior

The source workflow JSON is stored unchanged. The executable API prompt preserves the author/community V2 first-frame anchoring route:

- Load source face image through node `13`.
- Load target video through node `28`.
- Take the first visible guide frame.
- Run the embedded `Head Swap First Frame (Flux Klein 4/9b)` subgraph with `flux-2-klein-9b-fp8.safetensors` and `bfs_head_v1_flux-klein_9b_step3500_rank128.safetensors`.
- Prepare V2 magenta face/head masks with SAM3 and related mask nodes.
- Run the LTX-2 V2 head-swap LoRA `head_swap_ltx2_v2.safetensors` with the `head_swap` trigger.
- Return the final MP4 from the creator's `Head Swap Result Upscaled` node `351`.

Direct photo conditioning is documented by the author as supported, but first-frame head swap is the recommended reliability path for V2. This endpoint uses that recommended first-frame anchoring mode and does not substitute the V3 persistent-template workflow.

## Serverless Adaptations

- The ComfyUI UI graph is converted to an API prompt at request time by resolving Set/Get/primitive routing and expanding embedded subgraphs.
- rgthree Power Lora Loader nodes are converted to equivalent sequential `LoraLoaderModelOnly` nodes for API execution.
- Demo filenames are replaced with request-staged files.
- `skip_first_frames` defaults to `0` instead of the demo clip's sample-specific `15`; callers may override it in `settings`.
- `VideoOutputBridge` is added after final node `351` so RunPod uploads a reachable MP4.
- Target-video audio from `VHS_LoadVideo` is preserved through the creator final mux path when the input has audio.

## RunPod Template Requirements

Use RunPod's native GitHub integration and RunPod-managed image build. Do not use GHCR.

Set these as RunPod secrets/env vars where available:

- `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN` if Hugging Face downloads require authentication.
- R2 output env vars used by `runpod/worker-comfyui`: `BUCKET_ENDPOINT_URL`, `BUCKET_ACCESS_KEY_ID`, `BUCKET_SECRET_ACCESS_KEY`, `OUTPUT_BUCKET_NAME`, `OUTPUT_PUBLIC_BASE`.

The source workflow expects Black Forest Labs `flux-2-klein-9b-fp8.safetensors`. During CEL-200 prewarm, the endpoint reached Hugging Face with the configured token but received `403 Forbidden` from the gated upstream model repo. For this isolated experiment only, the Dockerfile sets `BFS_V2_FLUX_KLEIN_URL` to a public mirror of the same filename so the V2 graph can be tested without replacing the Flux/Klein first-frame method or moving to V3. If the HF account gains direct BFL access later, remove that baked override or replace it with the official BFL URL in endpoint env.

Prewarm:

```bash
python -u scripts/smoke_submit.py --endpoint-id <endpoint> --prewarm
```

Smoke:

```bash
python -u scripts/smoke_submit.py \
  --endpoint-id <endpoint> \
  --source-face-image-url '<source face image URL>' \
  --target-video-url '<fresh signed target MP4 URL>' \
  --verify-audio \
  --download-output outputs/bfs-v2-smoke.mp4
```

If a signed target MP4 URL returns `403 Forbidden` or is already past its signing window, request a fresh URL and do not substitute another video.

## Validation

```bash
python -m unittest -v
python -m compileall .
python -m json.tool asset-manifest.json >/dev/null
python -m json.tool workflows/workflow_ltx2_head_swap_drag_and_drop_v2.0.source.json >/dev/null
git diff --check
```

## CEL-200 Endpoint Status

- Endpoint ID: `0apsddjr33ry7p`
- Endpoint name: `runpod-comfyui-bfs-v2-public`
- Template ID: `27upkmyvti`
- GitHub repo: `https://github.com/cjkehoe/runpod-comfyui-bfs-v2-public`
- Latest source commit: `e174e75`
- RunPod image observed after releases: `registry.runpod.net/cjkehoe-runpod-comfyui-bfs-v2-public-main-dockerfile:80877f353`
- Releases published to trigger native GitHub rebuild: `bfs-v2-flux-mirror-20260515`, `v0.2.0-bfs-v2-flux-mirror`
- Prewarm: blocked. The existing image lacks the `BFS_V2_FLUX_KLEIN_URL` override and fails with `403 Forbidden` against the gated Black Forest Labs Flux Klein URL. Updating the template env through API was not authorized, and the RunPod GitHub release trigger did not roll the image forward during this session.
- Smoke test: blocked until a fresh signed target MP4 URL is provided. The CEL-200 URL supplied on 2026-05-14 expired at `2026-05-14T06:08:09Z`.
