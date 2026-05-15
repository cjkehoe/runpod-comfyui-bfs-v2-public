import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import unquote, urlparse


BFS_V2_WORKFLOW_ID = "bfs_ltx23_head_swap_v2"
BFS_V2_WORKFLOW_VERSION = "alissonerdx_bfs_v2_first_frame_anchor_v1"
BFS_V2_SOURCE_WORKFLOW_URL = (
    "https://huggingface.co/Alissonerdx/BFS-Best-Face-Swap-Video/raw/main/"
    "workflows/workflow_ltx2_head_swap_drag_and_drop_v2.0.json"
)
BFS_V2_SOURCE_WORKFLOW_SHA256 = "fd6a297e56a9a794c63df6bc4bd9c837f99ebd7937ac2e8214ee1731a13a741e"
BFS_V2_SOURCE_TEMPLATE_PATH = (
    Path(__file__).parent / "workflows" / "workflow_ltx2_head_swap_drag_and_drop_v2.0.source.json"
)

BFS_V2_LTX_TRANSFORMER_NAME = "ltx-2-19b-dev-fp8_transformer_only.safetensors"
BFS_V2_LTX_GGUF_TRANSFORMER_NAME = "LTX-2-dev-Q8_0.gguf"
BFS_V2_TEXT_ENCODER_NAME = "gemma_3_12B_it_fp8_scaled.safetensors"
BFS_V2_TEXT_CONNECTOR_NAME = "ltx-2-19b-embeddings_connector_dev_bf16.safetensors"
BFS_V2_VIDEO_VAE_NAME = "LTX2_video_vae_bf16.safetensors"
BFS_V2_AUDIO_VAE_NAME = "LTX2_audio_vae_bf16.safetensors"
BFS_V2_SPATIAL_UPSCALER_NAME = "ltx-2-spatial-upscaler-x2-1.0.safetensors"
BFS_V2_DISTILLED_LORA_NAME = "ltx-2/ltx-2-19b-distilled-lora_resized_dynamic_fro09_avg_rank_175_bf16.safetensors"
BFS_V2_HEAD_SWAP_LORA_NAME = "head_swap_ltx2_v2.safetensors"
BFS_V2_FLUX_KLEIN_NAME = "flux-2-klein-9b-fp8.safetensors"
BFS_V2_FLUX_HEAD_LORA_NAME = "bfs_head_v1_flux-klein_9b_step3500_rank128.safetensors"
BFS_V2_FLUX_TEXT_ENCODER_NAME = "qwen_3_8b_fp8mixed.safetensors"
BFS_V2_FLUX_VAE_NAME = "flux2-vae.safetensors"
BFS_V2_MELBAND_MODEL_NAME = "MelBandRoformer_fp32.safetensors"

BFS_V2_DEFAULT_FPS = 24
BFS_V2_DEFAULT_DURATION = 5.0
BFS_V2_DEFAULT_BASE_RESOLUTION = 1024
BFS_V2_DEFAULT_PROMPT = "head_swap"
BFS_V2_DEFAULT_NEGATIVE_PROMPT = (
    "worst quality, inconsistent motion, blurry, jittery, distorted"
)

BFS_V2_SERVERLESS_ADAPTATIONS = [
    "Resolved SetNode/GetNode/primitive UI routing into direct RunPod API prompt values.",
    "Expanded the source workflow's embedded first-frame Flux/Klein and frame-placement subgraphs into API prompt nodes.",
    "Patched LoadImage node 13 and VHS_LoadVideo node 28 with request source image and target MP4 filenames.",
    "Preserved the V2 first-frame preparation path: source face plus first target frame are routed through the author's Flux/Klein head-swap subgraph before LTX inference.",
    "Defaulted skip_first_frames to 0 for submitted videos instead of using the demo workflow's sample-specific skip value, while exposing it as an optional setting.",
    "Added a VideoOutputBridge after the creator's final VHS_VideoCombine node so RunPod uploads a reachable final MP4.",
]

BFS_V2_WIDGET_OVERRIDES = {
    "BasicScheduler": ["scheduler", "steps", "denoise"],
    "CFGGuider": ["cfg"],
    "CLIPTextEncode": ["text"],
    "CLIPLoader": ["clip_name", "type", "device"],
    "DualCLIPLoader": ["clip_name1", "clip_name2", "type", "device"],
    "DualCLIPLoaderGGUF": ["clip_name1", "clip_name2", "type"],
    "UnetLoaderGGUF": ["unet_name"],
    "ImageConcanate": ["direction", "match_image_size"],
    "ImageResizeKJv2": [
        "width",
        "height",
        "upscale_method",
        "keep_proportion",
        "pad_color",
        "crop_position",
        "divisible_by",
        "device",
    ],
    "KSamplerSelect": ["sampler_name"],
    "LatentUpscaleModelLoader": ["model_name"],
    "LoadImage": ["image", "upload"],
    "LoraLoader": ["lora_name", "strength_model", "strength_clip"],
    "LoraLoaderModelOnly": ["lora_name", "strength_model"],
    "LTXVConditioning": ["frame_rate"],
    "MelBandRoFormerModelLoader": ["model"],
    "RandomNoise": ["noise_seed", "control_after_generate"],
    "ReservedRegionFrameComposer": [
        "region_position",
        "region_size_px",
        "face_distribution",
        "interval_frames",
        "overflow_mode",
        "stack_direction",
        "face_scale_pct",
        "face_padding_px",
        "face_gap_px",
        "face_align_main",
        "face_align_cross",
        "chroma_r",
        "chroma_g",
        "chroma_b",
    ],
    "SAM3Segment": [
        "prompt",
        "mode",
        "threshold",
        "dilation",
        "blur",
        "expand",
        "padding",
        "device",
        "invert_mask",
        "preview",
        "background",
        "background_color",
    ],
    "SolidMask": ["value", "width", "height"],
    "TrimAudioDuration": ["start_time", "duration"],
    "UNETLoader": ["unet_name", "weight_dtype"],
    "VAELoader": ["vae_name"],
    "VAELoaderKJ": ["vae_name", "device", "dtype"],
    "VHS_LoadVideo": [
        "video",
        "force_rate",
        "custom_width",
        "custom_height",
        "frame_load_cap",
        "skip_first_frames",
        "select_every_nth",
        "format",
    ],
}

BFS_V2_UI_ONLY_TYPES = {
    "GetNode",
    "SetNode",
    "PrimitiveFloat",
    "PrimitiveInt",
    "PrimitiveNode",
    "PrimitiveStringMultiline",
    "SimpleCalculatorKJ",
    "Note",
    "MarkdownNote",
    "PreviewAny",
}


class BfsV2WorkflowInputError(ValueError):
    pass


def _load_source_template(path: Path = BFS_V2_SOURCE_TEMPLATE_PATH) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_filename_stem(value: str, fallback: str) -> str:
    stem = Path(value).stem if value else ""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-_")
    return stem or fallback


def _filename_from_url(url: str, fallback_stem: str, allowed_suffixes: Set[str], default_suffix: str) -> str:
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    try:
        parsed = urlparse(url)
        path_parts = [unquote(part) for part in parsed.path.split("/") if part]
    except Exception:
        path_parts = []

    candidate = path_parts[-1] if path_parts else ""
    suffix = Path(candidate).suffix.lower()
    if suffix not in allowed_suffixes:
        suffix = default_suffix

    return f"{_safe_filename_stem(candidate, fallback_stem)}-{url_hash}{suffix}"


def source_image_filename(image_url: str) -> str:
    return _filename_from_url(image_url, "bfs-v2-source-face", {".png", ".jpg", ".jpeg", ".webp"}, ".png")


def target_video_filename(video_url: str) -> str:
    return _filename_from_url(video_url, "bfs-v2-target-video", {".mp4", ".mov", ".m4v", ".webm"}, ".mp4")


def _normalize_seed(value: Any) -> int:
    try:
        seed = int(value)
    except (TypeError, ValueError):
        seed = -1
    if seed < 0:
        return random.randint(0, 2**32 - 1)
    return seed


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _normalize_fps(value: Any) -> int:
    return _clamp_int(value, BFS_V2_DEFAULT_FPS, 8, 30)


def _normalize_duration(value: Any) -> float:
    return _clamp_float(value, BFS_V2_DEFAULT_DURATION, 1.0, 60.0)


def _normalize_base_resolution(value: Any) -> int:
    parsed = _clamp_int(value, BFS_V2_DEFAULT_BASE_RESOLUTION, 512, 1536)
    return max(32, parsed - (parsed % 32))


def _ltx_frame_count(duration_seconds: float, fps: int) -> int:
    requested = max(9, int(round(duration_seconds * fps)))
    return (requested // 8) * 8 + 1


def _link_source_map(links: Any) -> Dict[Any, Tuple[str, int]]:
    sources: Dict[Any, Tuple[str, int]] = {}
    if not isinstance(links, list):
        return sources

    for link in links:
        if isinstance(link, list) and len(link) >= 3:
            sources[link[0]] = (str(link[1]), int(link[2]))
        elif isinstance(link, dict) and "id" in link:
            sources[link["id"]] = (str(link.get("origin_id")), int(link.get("origin_slot", 0)))

    return sources


def _set_input_links(nodes: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    set_input_links: Dict[str, Any] = {}
    for node in nodes:
        if node.get("type") != "SetNode" or not node.get("widgets_values"):
            continue
        inputs = node.get("inputs") or []
        if inputs:
            set_input_links[str(node["widgets_values"][0])] = inputs[0].get("link")
    return set_input_links


def _widget_override_map(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    values = node.get("widgets_values")
    if isinstance(values, dict):
        return {
            key: value
            for key, value in values.items()
            if key != "videopreview"
        }

    names = BFS_V2_WIDGET_OVERRIDES.get(str(node.get("type")))
    if not names or not isinstance(values, list):
        return None

    return {name: values[index] for index, name in enumerate(names) if index < len(values)}


def _eval_simple_calculator(expression: str, variables: Dict[str, Any]) -> float:
    allowed_names = {
        "abs": abs,
        "max": max,
        "min": min,
        "round": round,
    }
    safe_vars = {
        key: float(value)
        for key, value in variables.items()
        if isinstance(value, (int, float, bool))
    }
    return float(eval(expression, {"__builtins__": {}}, {**allowed_names, **safe_vars}))


def _resolve_reference_values(ref: Any) -> Iterable[Any]:
    if isinstance(ref, list):
        yield from ref
    elif isinstance(ref, dict):
        for value in ref.values():
            yield from _resolve_reference_values(value)


def _prune_workflow(workflow: Dict[str, Dict[str, Any]], output_node_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    seen: Set[str] = set()
    stack = [str(node_id) for node_id in output_node_ids]

    while stack:
        node_id = stack.pop()
        if node_id in seen or node_id not in workflow:
            continue
        seen.add(node_id)
        for value in workflow[node_id].get("inputs", {}).values():
            if isinstance(value, list) and value and isinstance(value[0], str):
                stack.append(value[0])
            else:
                for nested in _resolve_reference_values(value):
                    if isinstance(nested, list) and nested and isinstance(nested[0], str):
                        stack.append(nested[0])

    return {node_id: workflow[node_id] for node_id in workflow if node_id in seen}


def _convert_source_to_api(
    source: Dict[str, Any],
    *,
    seed: int,
    fps: int,
    duration_seconds: float,
    frame_count: int,
    base_resolution: int,
    prompt: str,
) -> Dict[str, Dict[str, Any]]:
    nodes = source.get("nodes")
    links = source.get("links")
    if not isinstance(nodes, list) or not isinstance(links, list):
        raise BfsV2WorkflowInputError("BFS V2 source workflow must be a ComfyUI UI workflow")

    definitions = source.get("definitions") if isinstance(source.get("definitions"), dict) else {}
    subgraphs = {
        str(subgraph.get("id")): subgraph
        for subgraph in definitions.get("subgraphs", [])
        if isinstance(subgraph, dict) and subgraph.get("id")
    }

    workflow: Dict[str, Dict[str, Any]] = {}
    expanded_subgraph_outputs: Dict[str, Dict[int, Any]] = {}
    expanded_power_lora_outputs: Dict[Tuple[Optional[int], str], Dict[int, Any]] = {}

    def build_context(context_source: Dict[str, Any]) -> Dict[str, Any]:
        context_nodes = context_source.get("nodes") or []
        return {
            "nodes": context_nodes,
            "node_by_id": {
                str(node["id"]): node
                for node in context_nodes
                if isinstance(node, dict) and "id" in node
            },
            "link_sources": _link_source_map(context_source.get("links")),
            "set_input_links": _set_input_links(context_nodes),
        }

    main_context = build_context(source)

    def prefixed_node_id(prefix: Optional[int], node_id: Any) -> str:
        if prefix is None:
            return str(node_id)
        return str(prefix * 1000 + int(node_id))

    def primitive_value(
        node: Dict[str, Any],
        *,
        context: Dict[str, Any],
        output_index: int,
        prefix: Optional[int],
        seen: Tuple[Tuple[Optional[int], str, int], ...],
    ) -> Any:
        node_id = str(node.get("id"))
        node_type = str(node.get("type"))
        values = node.get("widgets_values") or []

        if prefix is None and node_id == "20":
            return float(fps)
        if prefix is None and node_id == "26":
            return float(duration_seconds)
        if prefix is None and node_id in {"24", "25"}:
            return int(base_resolution)
        if prefix is None and node_id == "21":
            return int(frame_count)
        if node_type == "RandomNoise":
            return int(seed)

        if node_type in {"PrimitiveInt", "INTConstant"}:
            return int(values[0]) if values else 0
        if node_type == "PrimitiveFloat":
            return float(values[0]) if values else 0.0
        if node_type == "PrimitiveStringMultiline":
            return str(values[0]) if values else ""
        if node_type == "PrimitiveNode":
            return values[0] if values else None
        if node_type == "CM_FloatToInt":
            inputs = node.get("inputs") or []
            raw = resolve_link(inputs[0].get("link"), context=context, prefix=prefix, seen=seen) if inputs else 0
            return int(round(float(raw or 0)))
        if node_type == "CM_IntToFloat":
            inputs = node.get("inputs") or []
            raw = resolve_link(inputs[0].get("link"), context=context, prefix=prefix, seen=seen) if inputs else 0
            return float(raw or 0)
        if node_type == "easy mathInt":
            inputs = node.get("inputs") or []
            a = resolve_link(inputs[0].get("link"), context=context, prefix=prefix, seen=seen) if len(inputs) > 0 else 0
            b = resolve_link(inputs[1].get("link"), context=context, prefix=prefix, seen=seen) if len(inputs) > 1 else 0
            a = a if isinstance(a, (int, float, bool)) else 0
            b = b if isinstance(b, (int, float, bool)) else 0
            op = str(values[2] if len(values) > 2 else "add")
            if op == "subtract":
                return int(a or 0) - int(b or 0)
            if op == "multiply":
                return int(a or 0) * int(b or 0)
            if op == "divide":
                return int((a or 0) / (b or 1))
            return int(a or 0) + int(b or 0)
        return None

    def resolve_link(
        link_id: Any,
        *,
        context: Dict[str, Any],
        prefix: Optional[int],
        seen: Tuple[Tuple[Optional[int], str, int], ...] = (),
    ) -> Any:
        if link_id is None:
            return None
        source_node_id, output_index = context["link_sources"][link_id]

        if source_node_id == "-10":
            return context.get("external_inputs", {}).get(output_index)

        key = (prefix, source_node_id, output_index)
        if key in seen:
            raise BfsV2WorkflowInputError("cycle detected while converting BFS V2 source workflow")

        node = context["node_by_id"][source_node_id]
        node_type = str(node.get("type"))
        next_seen = seen + (key,)

        if node_type in subgraphs:
            outputs = expand_subgraph_instance(node, context=context)
            return outputs.get(output_index)
        if node_type == "Power Lora Loader (rgthree)":
            outputs = expand_power_lora(node, context=context, prefix=prefix)
            return outputs.get(output_index)

        if node_type == "GetNode":
            name = str((node.get("widgets_values") or [""])[0])
            if name not in context["set_input_links"]:
                return None
            return resolve_link(
                context["set_input_links"][name],
                context=context,
                prefix=prefix,
                seen=next_seen,
            )
        if node_type == "SetNode":
            inputs = node.get("inputs") or []
            return resolve_link(inputs[0].get("link"), context=context, prefix=prefix, seen=next_seen) if inputs else None
        if node_type in {
            "PrimitiveFloat",
            "PrimitiveInt",
            "PrimitiveNode",
            "PrimitiveStringMultiline",
            "INTConstant",
            "CM_FloatToInt",
            "CM_IntToFloat",
            "easy mathInt",
            "RandomNoise",
        }:
            return primitive_value(
                node,
                context=context,
                output_index=output_index,
                prefix=prefix,
                seen=next_seen,
            )
        if node_type == "SimpleCalculatorKJ":
            inputs = node.get("inputs") or []
            variables: Dict[str, Any] = {}
            for input_item in inputs:
                name = str(input_item.get("name") or "")
                variables[name.split(".", 1)[-1] or name] = resolve_link(
                    input_item.get("link"),
                    context=context,
                    prefix=prefix,
                    seen=next_seen,
                )
            expression = str((node.get("widgets_values") or [""])[0])
            if prefix is None and str(node.get("id")) == "23":
                result = float(frame_count)
            else:
                result = _eval_simple_calculator(expression, variables)
            if output_index == 1:
                return int(result)
            if output_index == 2:
                return bool(result)
            return result
        if node_type == "ComfySwitchNode":
            inputs = node.get("inputs") or []
            input_by_name = {item.get("name"): item for item in inputs}
            switch_value = resolve_link(
                input_by_name.get("switch", {}).get("link"),
                context=context,
                prefix=prefix,
                seen=next_seen,
            )
            branch = "on_true" if bool(switch_value) else "on_false"
            return resolve_link(input_by_name.get(branch, {}).get("link"), context=context, prefix=prefix, seen=next_seen)

        return [prefixed_node_id(prefix, source_node_id), output_index]

    def convert_node(node: Dict[str, Any], *, context: Dict[str, Any], prefix: Optional[int]) -> Dict[str, Any]:
        inputs: Dict[str, Any] = {}
        value_map = _widget_override_map(node)
        if value_map:
            inputs.update(value_map)

        values = node.get("widgets_values")
        value_index = 0

        for input_item in node.get("inputs") or []:
            name = input_item.get("name")
            if not name:
                continue

            if input_item.get("link") is not None:
                inputs[name] = resolve_link(input_item["link"], context=context, prefix=prefix)
                if value_map is None and input_item.get("widget") is not None:
                    value_index += 1
                continue

            if name in inputs:
                continue

            if input_item.get("widget") is not None and isinstance(values, list) and value_index < len(values):
                inputs[name] = values[value_index]
                value_index += 1

        api_node: Dict[str, Any] = {"class_type": node["type"], "inputs": inputs}
        title = node.get("title") or (node.get("properties") or {}).get("Node name for S&R")
        if title:
            api_node["_meta"] = {"title": title}
        return api_node

    def expand_power_lora(
        node: Dict[str, Any],
        *,
        context: Dict[str, Any],
        prefix: Optional[int],
    ) -> Dict[int, Any]:
        cache_key = (prefix, str(node["id"]))
        if cache_key in expanded_power_lora_outputs:
            return expanded_power_lora_outputs[cache_key]

        inputs = node.get("inputs") or []
        model_ref = resolve_link(inputs[0].get("link"), context=context, prefix=prefix) if inputs else None
        clip_ref = resolve_link(inputs[1].get("link"), context=context, prefix=prefix) if len(inputs) > 1 else None
        previous_model = model_ref
        last_node_id: Optional[str] = None
        enabled_loras = [
            item
            for item in (node.get("widgets_values") or [])
            if isinstance(item, dict) and item.get("on") and item.get("lora")
        ]
        for index, lora in enumerate(enabled_loras, start=1):
            lora_node_id = f"{prefixed_node_id(prefix, node['id'])}{index:02d}"
            workflow[lora_node_id] = {
                "class_type": "LoraLoaderModelOnly",
                "inputs": {
                    "model": previous_model,
                    "lora_name": lora.get("lora"),
                    "strength_model": float(lora.get("strength", 1.0)),
                },
                "_meta": {"title": f"{node.get('title') or 'Power Lora Loader'} lora {index}"},
            }
            previous_model = [lora_node_id, 0]
            last_node_id = lora_node_id

        outputs = {
            0: [last_node_id, 0] if last_node_id else model_ref,
            1: clip_ref,
        }
        expanded_power_lora_outputs[cache_key] = outputs
        return outputs

    def expand_subgraph_instance(node: Dict[str, Any], *, context: Dict[str, Any]) -> Dict[int, Any]:
        instance_id = f"{context.get('prefix')}:{node['id']}"
        if instance_id in expanded_subgraph_outputs:
            return expanded_subgraph_outputs[instance_id]

        subgraph = subgraphs.get(str(node.get("type")))
        if not subgraph:
            raise BfsV2WorkflowInputError(f"missing subgraph definition for {node.get('type')}")

        parent_prefix = context.get("prefix")
        prefix = int(prefixed_node_id(parent_prefix, node["id"]))
        sub_context = build_context(subgraph)
        sub_context["prefix"] = prefix
        external_inputs: Dict[int, Any] = {}
        for index, input_item in enumerate(node.get("inputs") or []):
            if input_item.get("link") is not None:
                external_inputs[index] = resolve_link(
                    input_item["link"],
                    context=context,
                    prefix=context.get("prefix"),
                )
        sub_context["external_inputs"] = external_inputs

        for sub_node in sub_context["nodes"]:
            sub_node_type = str(sub_node.get("type"))
            if sub_node_type in BFS_V2_UI_ONLY_TYPES:
                continue
            if sub_node_type in subgraphs:
                expand_subgraph_instance(sub_node, context=sub_context)
                continue
            if sub_node_type == "Power Lora Loader (rgthree)":
                expand_power_lora(sub_node, context=sub_context, prefix=prefix)
                continue
            workflow[prefixed_node_id(prefix, sub_node["id"])] = convert_node(
                sub_node,
                context=sub_context,
                prefix=prefix,
            )

        output_refs: Dict[int, Any] = {}
        for index, output in enumerate(subgraph.get("outputs") or []):
            link_ids = output.get("linkIds") or []
            if link_ids:
                output_refs[index] = resolve_link(link_ids[0], context=sub_context, prefix=prefix)

        expanded_subgraph_outputs[instance_id] = output_refs
        return output_refs

    for node in nodes:
        node_type = str(node.get("type"))
        if node_type in subgraphs:
            main_context["prefix"] = None
            expand_subgraph_instance(node, context=main_context)
            continue
        if node_type == "Power Lora Loader (rgthree)":
            expand_power_lora(node, context=main_context, prefix=None)
            continue
        if node_type in BFS_V2_UI_ONLY_TYPES:
            continue
        workflow[str(node["id"])] = convert_node(node, context=main_context, prefix=None)

    return workflow


def _set_input(workflow: Dict[str, Dict[str, Any]], node_id: str, input_name: str, value: Any) -> None:
    workflow[node_id]["inputs"][input_name] = value


def _apply_runtime_values(
    workflow: Dict[str, Dict[str, Any]],
    *,
    source_face_filename: str,
    target_video_file: str,
    prompt: str,
    negative_prompt: str,
    seed: int,
    fps: int,
    duration_seconds: float,
    frame_count: int,
    skip_first_frames: int,
    source_has_audio: Optional[bool],
    debug_outputs: bool,
) -> List[str]:
    _set_input(workflow, "13", "image", source_face_filename)
    _set_input(workflow, "13", "upload", "image")

    _set_input(workflow, "28", "video", target_video_file)
    _set_input(workflow, "28", "force_rate", float(fps))
    _set_input(workflow, "28", "frame_load_cap", int(frame_count))
    _set_input(workflow, "28", "skip_first_frames", int(skip_first_frames))
    _set_input(workflow, "28", "select_every_nth", 1)

    if "687" in workflow:
        _set_input(workflow, "687", "unet_name", BFS_V2_LTX_TRANSFORMER_NAME)
        _set_input(workflow, "687", "weight_dtype", "default")
    if "696" in workflow:
        _set_input(workflow, "696", "unet_name", BFS_V2_LTX_GGUF_TRANSFORMER_NAME)
    if "3" in workflow:
        _set_input(workflow, "3", "clip_name1", BFS_V2_TEXT_ENCODER_NAME)
        _set_input(workflow, "3", "clip_name2", BFS_V2_TEXT_CONNECTOR_NAME)
        _set_input(workflow, "3", "type", "ltxv")
    if "4" in workflow:
        _set_input(workflow, "4", "vae_name", BFS_V2_VIDEO_VAE_NAME)
    if "5" in workflow:
        _set_input(workflow, "5", "vae_name", BFS_V2_AUDIO_VAE_NAME)
        _set_input(workflow, "5", "device", "main_device")
        _set_input(workflow, "5", "dtype", "bf16")
    if "6" in workflow:
        _set_input(workflow, "6", "model_name", BFS_V2_SPATIAL_UPSCALER_NAME)
    if "302" in workflow:
        _set_input(workflow, "302", "model", BFS_V2_MELBAND_MODEL_NAME)

    for lora_node_id in ("7", "7401", "37401"):
        if lora_node_id in workflow:
            _set_input(workflow, lora_node_id, "lora_name", BFS_V2_DISTILLED_LORA_NAME)
            _set_input(workflow, lora_node_id, "strength_model", 0.6)
    for lora_node_id in ("7402", "37402"):
        if lora_node_id in workflow:
            _set_input(workflow, lora_node_id, "lora_name", BFS_V2_HEAD_SWAP_LORA_NAME)
            _set_input(workflow, lora_node_id, "strength_model", 1.0)

    for noise_node_id in ("88", "340"):
        if noise_node_id in workflow:
            _set_input(workflow, noise_node_id, "noise_seed", seed)
    if "75" in workflow:
        _set_input(workflow, "75", "text", prompt)
    if "76" in workflow:
        _set_input(workflow, "76", "text", negative_prompt)

    if "149206" in workflow:
        _set_input(workflow, "149206", "unet_name", BFS_V2_FLUX_KLEIN_NAME)
        _set_input(workflow, "149206", "weight_dtype", "default")
    if "149205" in workflow:
        _set_input(workflow, "149205", "clip_name", BFS_V2_FLUX_TEXT_ENCODER_NAME)
        _set_input(workflow, "149205", "type", "flux2")
        _set_input(workflow, "149205", "device", "default")
    if "149196" in workflow:
        _set_input(workflow, "149196", "vae_name", BFS_V2_FLUX_VAE_NAME)
    if "149207" in workflow:
        _set_input(workflow, "149207", "lora_name", BFS_V2_FLUX_HEAD_LORA_NAME)
        _set_input(workflow, "149207", "strength_model", 1.0)

    _set_input(workflow, "351", "frame_rate", float(fps))
    _set_input(workflow, "351", "filename_prefix", f"{BFS_V2_WORKFLOW_ID}_final")
    _set_input(workflow, "351", "format", "video/h264-mp4")
    _set_input(workflow, "351", "pix_fmt", "yuv420p")
    _set_input(workflow, "351", "crf", 19)
    _set_input(workflow, "351", "save_metadata", True)
    _set_input(workflow, "351", "save_output", True)

    workflow["9901"] = {
        "class_type": "VideoOutputBridge",
        "inputs": {"filenames": ["351", 0], "label": BFS_V2_WORKFLOW_ID},
        "_meta": {"title": "RunPod BFS V2 final MP4 bridge"},
    }

    debug_labels: List[str] = []
    if debug_outputs:
        for node_id, label in (("120", "first_pass"), ("180", "comparison")):
            if node_id in workflow:
                _set_input(workflow, node_id, "frame_rate", float(fps))
                _set_input(workflow, node_id, "filename_prefix", f"{BFS_V2_WORKFLOW_ID}_debug_{label}")
                _set_input(workflow, node_id, "save_output", True)
                bridge_id = "9902" if node_id == "120" else "9903"
                workflow[bridge_id] = {
                    "class_type": "VideoOutputBridge",
                    "inputs": {"filenames": [node_id, 0], "label": f"{BFS_V2_WORKFLOW_ID}_debug_{label}"},
                    "_meta": {"title": f"RunPod BFS V2 {label} debug bridge"},
                }
                debug_labels.append(label)

    return debug_labels


def build_bfs_v2_job_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    workflow_id = str(payload.get("workflow_id") or BFS_V2_WORKFLOW_ID).strip()
    if workflow_id != BFS_V2_WORKFLOW_ID:
        raise BfsV2WorkflowInputError(f"workflow_id must be {BFS_V2_WORKFLOW_ID}")

    source_image_url = str(
        payload.get("source_face_image_url")
        or payload.get("source_face_image")
        or payload.get("source_image")
        or payload.get("source_image_url")
        or payload.get("face_image")
        or payload.get("image")
        or ""
    ).strip()
    if not source_image_url.startswith(("https://", "http://")):
        raise BfsV2WorkflowInputError("source_face_image_url, source_face_image, or image must be an HTTP(S) URL")

    video_url = str(
        payload.get("target_video_url")
        or payload.get("video_url")
        or payload.get("video")
        or ""
    ).strip()
    if not video_url.startswith(("https://", "http://")):
        raise BfsV2WorkflowInputError("target_video_url or video_url must be an HTTP(S) URL")

    raw_settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else {}
    source_duration = payload.get("source_video_duration")
    source_fps = payload.get("source_video_fps")
    source_has_audio = payload.get("source_video_has_audio")
    if not isinstance(source_has_audio, bool):
        source_has_audio = None

    fps = _normalize_fps(payload.get("fps") or raw_settings.get("fps") or source_fps)
    duration_seconds = _normalize_duration(
        payload.get("duration")
        or payload.get("duration_seconds")
        or raw_settings.get("duration")
        or source_duration
    )
    frame_count = _clamp_int(
        payload.get("frame_count") or raw_settings.get("frame_count") or _ltx_frame_count(duration_seconds, fps),
        _ltx_frame_count(duration_seconds, fps),
        9,
        1441,
    )
    frame_count = (frame_count // 8) * 8 + 1
    base_resolution = _normalize_base_resolution(
        payload.get("base_resolution") or raw_settings.get("base_resolution")
    )
    skip_first_frames = _clamp_int(
        payload.get("skip_first_frames") or raw_settings.get("skip_first_frames") or 0,
        0,
        0,
        100000,
    )
    seed = _normalize_seed(payload.get("seed", raw_settings.get("seed", -1)))
    prompt = str(payload.get("prompt") or raw_settings.get("prompt") or BFS_V2_DEFAULT_PROMPT).strip()
    if not prompt:
        prompt = BFS_V2_DEFAULT_PROMPT
    if not prompt.lower().lstrip().startswith("head_swap"):
        prompt = f"head_swap:\n\n{prompt}"
    negative_prompt = str(
        payload.get("negative_prompt") or raw_settings.get("negative_prompt") or BFS_V2_DEFAULT_NEGATIVE_PROMPT
    ).strip()
    debug_outputs = bool(payload.get("debug_outputs") or raw_settings.get("debug_outputs", False))

    source_face_file = source_image_filename(source_image_url)
    target_file = target_video_filename(video_url)
    source = _load_source_template()
    workflow = _convert_source_to_api(
        source,
        seed=seed,
        fps=fps,
        duration_seconds=duration_seconds,
        frame_count=frame_count,
        base_resolution=base_resolution,
        prompt=prompt,
    )
    debug_output_labels = _apply_runtime_values(
        workflow,
        source_face_filename=source_face_file,
        target_video_file=target_file,
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        fps=fps,
        duration_seconds=duration_seconds,
        frame_count=frame_count,
        skip_first_frames=skip_first_frames,
        source_has_audio=source_has_audio,
        debug_outputs=debug_outputs,
    )
    output_nodes = ["9901", *(["9902", "9903"] if debug_outputs else [])]
    workflow = _prune_workflow(workflow, output_nodes)

    audio_status = "source_audio_attempted_unverified"
    if source_has_audio is True:
        audio_status = "source_video_audio_muxed"
    elif source_has_audio is False:
        audio_status = "source_video_has_no_audio_final_mp4_silent"

    loaded_loras = [
        {
            "name": BFS_V2_FLUX_HEAD_LORA_NAME,
            "role": "flux_klein_first_frame_head_swap_preprocessor",
            "strength_model": 1.0,
            "source_node": "149207",
        },
        {
            "name": BFS_V2_DISTILLED_LORA_NAME,
            "role": "ltx2_distilled_motion_lora",
            "strength_model": 0.6,
            "source_nodes": ["7", "7401", "37401"],
        },
        {
            "name": BFS_V2_HEAD_SWAP_LORA_NAME,
            "role": "bfs_v2_head_swap_multimode_lora",
            "strength_model": 1.0,
            "source_nodes": ["7402", "37402"],
        },
    ]
    metadata = {
        "workflow_id": BFS_V2_WORKFLOW_ID,
        "workflow_version": BFS_V2_WORKFLOW_VERSION,
        "source_workflow_url": BFS_V2_SOURCE_WORKFLOW_URL,
        "source_workflow_sha256": BFS_V2_SOURCE_WORKFLOW_SHA256,
        "source_image_filename": source_face_file,
        "source_image_url_hash": hashlib.sha256(source_image_url.encode("utf-8")).hexdigest(),
        "target_video_filename": target_file,
        "target_video_url_hash": hashlib.sha256(video_url.encode("utf-8")).hexdigest(),
        "target_video_hash": payload.get("source_video_sha256"),
        "target_video_sha256": payload.get("source_video_sha256"),
        "target_video_duration": payload.get("source_video_duration"),
        "target_video_width": payload.get("source_video_width"),
        "target_video_height": payload.get("source_video_height"),
        "target_video_frame_count": payload.get("source_video_frame_count"),
        "target_video_has_audio": source_has_audio,
        "audio_present": source_has_audio,
        "audio_status": audio_status,
        "seed": seed,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "frame_settings": {
            "fps": fps,
            "duration_seconds": duration_seconds,
            "frame_count": frame_count,
            "skip_first_frames": skip_first_frames,
            "base_resolution": base_resolution,
        },
        "operating_mode": "first_frame_head_swap_anchor_recommended_by_author",
        "first_frame_anchor": {
            "source_face_node": "13",
            "target_video_node": "28",
            "first_frame_node": "52",
            "flux_klein_head_swap_subgraph_instance": "149",
            "flux_klein_head_swap_output_set_node": "617",
            "magenta_mask_preparation_nodes": ["661", "482", "727", "728"],
            "final_output_node": "351",
        },
        "loaded_loras": loaded_loras,
        "models": [
            BFS_V2_LTX_TRANSFORMER_NAME,
            BFS_V2_LTX_GGUF_TRANSFORMER_NAME,
            BFS_V2_TEXT_ENCODER_NAME,
            BFS_V2_TEXT_CONNECTOR_NAME,
            BFS_V2_VIDEO_VAE_NAME,
            BFS_V2_AUDIO_VAE_NAME,
            BFS_V2_SPATIAL_UPSCALER_NAME,
            BFS_V2_FLUX_KLEIN_NAME,
            BFS_V2_FLUX_TEXT_ENCODER_NAME,
            BFS_V2_FLUX_VAE_NAME,
            BFS_V2_MELBAND_MODEL_NAME,
        ],
        "serverless_adaptations": BFS_V2_SERVERLESS_ADAPTATIONS,
        "debug_output_labels": debug_output_labels,
    }

    return {
        "workflow": workflow,
        "model_downloads": [
            {"url": source_image_url, "filename": source_face_file, "relative_path": "input"},
            {"url": video_url, "filename": target_file, "relative_path": "input"},
        ],
        "workflow_id": BFS_V2_WORKFLOW_ID,
        "workflow_version": BFS_V2_WORKFLOW_VERSION,
        "seed": seed,
        "settings": {
            "fps": fps,
            "duration_seconds": duration_seconds,
            "frame_count": frame_count,
            "skip_first_frames": skip_first_frames,
            "base_resolution": base_resolution,
            "debug_outputs": debug_outputs,
            "prompt_mode": "api_manual_structured_prompt",
            "audio_status": audio_status,
        },
        "metadata": metadata,
        "model_metadata": metadata,
    }


def is_high_level_bfs_v2_request(payload: Dict[str, Any]) -> bool:
    return str(payload.get("workflow_id") or "").strip() == BFS_V2_WORKFLOW_ID
