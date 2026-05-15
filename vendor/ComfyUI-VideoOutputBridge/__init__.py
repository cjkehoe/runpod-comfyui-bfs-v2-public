from pathlib import Path

COMFY_OUTPUT_ROOT = Path("/comfyui/output")


def _resolve_subfolder(path: Path) -> str:
    if path.parent == Path("."):
        return ""

    if path.is_absolute():
        try:
            relative_parent = path.parent.relative_to(COMFY_OUTPUT_ROOT)
        except ValueError:
            return path.parent.name if path.parent.name else ""

        return "" if str(relative_parent) == "." else relative_parent.as_posix()

    return path.parent.as_posix()


class VideoOutputBridge:
    """Expose VideoHelperSuite video filenames as standard image outputs."""

    CATEGORY = "Utility/Bridges"
    RETURN_TYPES: tuple = ()
    RETURN_NAMES: tuple = ()
    FUNCTION = "forward"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "filenames": ("VHS_FILENAMES",),
                "label": (
                    "STRING",
                    {
                        "default": "video-output",
                        "multiline": False,
                    },
                ),
            }
        }

    def forward(self, filenames, label: str):
        images = []

        if isinstance(filenames, tuple) and len(filenames) == 1:
            if isinstance(filenames[0], tuple) and len(filenames[0]) == 2:
                filenames = filenames[0]

        if isinstance(filenames, tuple) and len(filenames) == 2:
            _, filenames = filenames

        if isinstance(filenames, bool) or filenames is None:
            filenames = []

        if not isinstance(filenames, list):
            filenames = [filenames]

        video_files = [
            entry
            for entry in filenames
            if not (isinstance(entry, str) and entry.lower().endswith(".png"))
        ]

        for index, entry in enumerate(video_files):
            if isinstance(entry, str):
                path = Path(entry)
                images.append(
                    {
                        "filename": path.name,
                        "subfolder": _resolve_subfolder(path),
                        "type": "output",
                    }
                )
                continue

            if isinstance(entry, dict):
                images.append(
                    {
                        "filename": entry.get("filename") or f"{label}_{index}.mp4",
                        "subfolder": entry.get("subfolder", ""),
                        "type": entry.get("type", "output"),
                    }
                )

        if not images:
            images.append(
                {
                    "filename": f"{label}_missing.mp4",
                    "subfolder": "",
                    "type": "output",
                }
            )

        return {"ui": {"images": images}}


NODE_CLASS_MAPPINGS = {
    "VideoOutputBridge": VideoOutputBridge,
}


NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoOutputBridge": "Video Output Bridge",
}
