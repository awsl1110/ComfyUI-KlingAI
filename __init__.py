"""ComfyUI-KlingAI — Kling OmniVideo nodes for ComfyUI."""

try:
    from .kling_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

    __all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
    print(f"[KlingAI] Loaded: {list(NODE_CLASS_MAPPINGS)}")

except Exception as e:
    print(f"[KlingAI] Failed to load: {e}")
    print("[KlingAI] Run: pip install -r ComfyUI/custom_nodes/ComfyUI-KlingAI/requirements.txt")
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}
