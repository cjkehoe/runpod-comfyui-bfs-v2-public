# BFS V2 First-Frame Anchor Notes

## Source

- Model card: `https://huggingface.co/Alissonerdx/BFS-Best-Face-Swap-Video`
- Workflow JSON: `workflows/workflow_ltx2_head_swap_drag_and_drop_v2.0.source.json`
- Source SHA256: `fd6a297e56a9a794c63df6bc4bd9c837f99ebd7937ac2e8214ee1731a13a741e`

## Operating Mode

The author documents several V2 modes, including direct photo conditioning, automatic magazine-style overlay, manual overlay, and first-frame head swap. The recommended V2 mode is first-frame head swap because the first frame already matches target pose, lighting, depth, and occlusions.

This endpoint uses the recommended mode. The source face image is not passed directly as the only LTX conditioning signal; the graph first uses it to create a swapped first frame with the embedded Flux/Klein head-swap subgraph, then feeds that anchor into the LTX-2 V2 video pass.

## Runtime Graph

- `13` `LoadImage`: source face/head image.
- `28` `VHS_LoadVideo`: target/guide MP4.
- `52`/`150`: first target frame selection.
- `149` embedded subgraph: `Head Swap First Frame (Flux Klein 4/9b)`.
- `661`/`482`: SAM3 face/head/hair segmentation.
- `727`/`728`: magenta mask preparation.
- `74`/`374`: source rgthree Power Lora Loader nodes, converted to sequential `LoraLoaderModelOnly` API nodes.
- `351`: creator final `Head Swap Result Upscaled` MP4 mux.
- `9901`: local `VideoOutputBridge` added for RunPod upload.

## Required Models

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
- `head_swap_ltx2_v2.safetensors` mapped from `ltx-2/head_swap_v2_multimodes.safetensors`
- `ltx-2-spatial-upscaler-x2-1.0.safetensors`
- `MelBandRoformer_fp32.safetensors`

## Validation

Local validation:

```bash
python -m unittest -v
python -m compileall .
python -m json.tool asset-manifest.json >/dev/null
python -m json.tool workflows/workflow_ltx2_head_swap_drag_and_drop_v2.0.source.json >/dev/null
git diff --check
```

Remote validation remains blocked until the CEL-200 target video signed URL is refreshed.
