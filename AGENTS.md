# AGENTS.md

## Local Context

This worker is an isolated CEL-200 experiment for the Alissonerdx BFS Best-Face-Swap-Video V2 first-frame head-swap workflow.

Do not modify the production `ltx23_mrxin_v5_10eros_i2v` worker or workflow from this repo. Keep this project focused on the BFS V2 endpoint research and preserve the source workflow JSON unchanged under `workflows/`.

Use RunPod native GitHub integration for deployment. Do not add GHCR workflows or GHCR image references.

## Validation

Run the targeted worker checks before deployment:

```bash
python -m unittest -v
python -m compileall .
python -m json.tool asset-manifest.json >/dev/null
python -m json.tool workflows/workflow_ltx2_head_swap_drag_and_drop_v2.0.source.json >/dev/null
git diff --check
```
