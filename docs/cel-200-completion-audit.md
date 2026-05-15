# CEL-200 Completion Audit

## Objective

Create a dedicated RunPod/ComfyUI endpoint that runs Alissonerdx BFS Best-Face-Swap-Video V2 exactly as intended by the author/community, then prove it works with the CEL-200 source face image and target MP4.

## Evidence Checklist

| Requirement | Evidence | Status |
| --- | --- | --- |
| Dedicated local repo under `/Users/chriskehoe/Documents/Repositories/Empire/runpod` | `/Users/chriskehoe/Documents/Repositories/Empire/runpod/runpod-comfyui-bfs-v2` | Complete |
| Do not modify existing production I2V workflow or endpoint | Separate repo, separate endpoint `0apsddjr33ry7p`; existing I2V endpoint not changed | Complete |
| Use native RunPod GitHub integration, no GHCR | Public mirror `cjkehoe/runpod-comfyui-bfs-v2-public`; Dockerfile/test asserts no GHCR | Complete |
| Preserve V2 source workflow | `workflows/workflow_ltx2_head_swap_drag_and_drop_v2.0.source.json`, SHA256 `fd6a297e56a9a794c63df6bc4bd9c837f99ebd7937ac2e8214ee1731a13a741e` | Complete |
| Determine direct photo conditioning vs first-frame anchoring | `README.md` and `docs/bfs-v2-first-frame-anchor.md` document V2 first-frame head-swap anchoring | Complete |
| Preserve intended inputs | Handler accepts `source_face_image_url`, `target_video_url`, optional prompt/negative/seed/settings | Complete |
| Add workflow ID | `bfs_ltx23_head_swap_v2` | Complete |
| Identify custom nodes and model assets | `asset-manifest.json`; Dockerfile pins custom node revisions | Complete |
| Add smoke submit and polling support | `scripts/smoke_submit.py` with prewarm, submit, poll, output download, ffprobe support, URL preflight, and in-memory R2 target signing via `--target-video-r2-key` | Complete |
| Local validation | `python -m unittest -v` passes 29 tests; `python -m compileall .`, JSON checks, and `git diff --check` passed after latest smoke tooling changes | Complete |
| Endpoint readiness verifier | `python -u scripts/verify_endpoint_ready.py` returns `ok: true`, all checks true, and no missing env keys | Complete |
| Prewarm/download model set | RunPod job `8d4d5d25-60ed-425f-89b0-b18acf43c82b-e2` completed; queue delay `181778` ms; execution `199051` ms; model paths downloaded. Current endpoint has no network volume and `workersMin: 0`, so a later cold worker may need to re-download models. | Complete, but cache persistence is weak |
| Submit one real test using provided media | Target MP4 signed URL fails preflight with HTTP 403; no substitute media used | Blocked |
| Verify output MP4 reachable | No real generation output yet | Blocked |
| Run ffprobe for video/audio streams | No real generation output yet | Blocked |
| Capture runtime, GPU/worker, disk, OOM/perf issues | Prewarm runtime captured; generation runtime/quality not available until smoke can run | Partial |
| Final recommendation | Cannot promote or reject on quality until real smoke succeeds | Blocked |

## Current RunPod State

- Endpoint: `0apsddjr33ry7p` / `runpod-comfyui-bfs-v2-public`
- Template: `27upkmyvti`
- Image observed: `registry.runpod.net/cjkehoe-runpod-comfyui-bfs-v2-public-main-dockerfile:80877f353`
- Template env keys: `HF_TOKEN`, `BFS_V2_FLUX_KLEIN_URL`, `BUCKET_ENDPOINT_URL`, `BUCKET_ACCESS_KEY_ID`, `BUCKET_SECRET_ACCESS_KEY`, `OUTPUT_BUCKET_NAME`, `OUTPUT_PUBLIC_BASE`
- Endpoint config: `workersMax: 1`, `workersMin: 0`, `workersStandby: 1`, no network volume, 150 GB container disk, H100 80GB-class GPU pool, 2-hour execution timeout
- Prewarm result: completed on job `8d4d5d25-60ed-425f-89b0-b18acf43c82b-e2`
- Cache note: because there is no network volume and `workersMin` is zero, prewarm proves the model set can download successfully but does not guarantee model files persist until a future smoke job. If a fresh signed URL is not available immediately, expect the smoke job to incur cold-start/model-download time again.
- Output storage note: the experiment template has the same `runpod/worker-comfyui` output bucket env keys used by the working I2V template, so the future smoke job should be able to return a reachable MP4 URL if generation succeeds.
- Readiness verifier: `python -u scripts/verify_endpoint_ready.py` passes against the live endpoint/template and prewarm job.

## Remaining Blocker

The CEL-200 target object exists in production Supabase metadata as private `celebmakerai-user-media`, but the supplied signed URL is expired and returns HTTP 403. The approved root production env only contains Supabase credentials, not R2 signing credentials, and the local Heroku login has no apps. A fresh R2-signed URL for the same target object is required before submitting the real smoke job.

Additional read-only checks:

- `generated_videos.video_url`, `r2_object_name`, and `video_storage_key` all point to the same private object key.
- A `media_backup_jobs` row exists for the same source bucket/key with `status = succeeded`, but the row stores only a backup bucket/key. Common public S3 URL forms for that stored backup key returned 404, so the backup copy does not provide a usable unauthenticated input URL from this environment.
- `scripts/sign_user_media_url.py` and `scripts/smoke_submit.py --target-video-r2-key` can mint a fresh URL once approved R2 credentials are available. They do not remove the blocker because those credentials are not present in the approved local environment.
- The experiment template's output bucket credentials were tested in memory against the exact `celebmakerai-user-media` target object; the signed range-read returned HTTP 404, so output-storage credentials cannot be used to fetch the private input media.
- Production Supabase Storage was checked with the approved service-role key. The `celebmakerai-user-media` bucket is not a Supabase Storage bucket in that project, and object lookup for the exact target key returned HTTP 400, so Supabase Storage signing cannot provide the target MP4.
- Local Vercel CLI access was checked for a deployed frontend signing path. The available scopes list `cjkehoes-projects` and `10x-engineers`; neither exposes the CelebMaker frontend project, so deployed frontend env/config cannot be used from this session to mint the URL.
