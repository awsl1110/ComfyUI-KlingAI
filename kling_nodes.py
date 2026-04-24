"""ComfyUI nodes for Kling AI OmniVideo API — POST /v1/videos/omni-video."""

import json
import os
import time
import urllib.request

try:
    from comfy_api.input_impl import VideoFromFile as _VideoFromFile
    _HAS_VIDEO_TYPE = True
except ImportError:
    _HAS_VIDEO_TYPE = False

from .api_client import KlingClient, encode_jwt_token


MODELS  = ["kling-video-o1", "kling-v3-omni"]
MODES   = ["pro", "std", "4k"]
RATIOS  = ["16:9", "9:16", "1:1"]

_DUR      = {"default": 5, "min": 3, "max": 15, "step": 1, "display": "slider"}  # 文本/图像/首尾帧
_DUR_VID  = {"default": 5, "min": 3, "max": 10, "step": 1, "display": "slider"}  # 视频到视频
_DUR_SHOT = {"default": 3, "min": 1, "max": 15, "step": 1, "display": "slider"}  # 单镜头时长

_T_MULTI_SHOT = "KLING_MULTI_SHOT"  # list: [{index, prompt, duration}, ...]


def _parse_element_list(ids: str) -> list:
    """把逗号分隔的主体 ID 字符串解析成 API 所需的列表格式。"""
    result = []
    for s in ids.split(","):
        s = s.strip()
        if s:
            result.append({"element_id": int(s)})
    return result


def _client(api_token: str) -> KlingClient:
    token = (api_token or "").strip()
    if not token:
        raise ValueError("api_token is required — connect a KlingAuth node.")
    return KlingClient(token=token)


def _run_video(api_token: str, payload: dict, poll_timeout: int) -> tuple:
    client = _client(api_token)
    print(f"[KlingAI] Submitting task — keys: {list(payload.keys())}")
    task_id = client.create_task(payload)
    print(f"[KlingAI] Task created: {task_id}")
    task = client.wait(task_id, timeout=poll_timeout)
    videos = task.get("task_result", {}).get("videos", [])
    if not videos:
        raise RuntimeError(
            "No video in task result:\n" + json.dumps(task, indent=2, ensure_ascii=False)
        )
    url = videos[0]["url"]
    print(f"[KlingAI] Result URL: {url}")
    return (url,)


def _base(model_name: str, mode: str, watermark_enabled: bool) -> dict:
    return {
        "model_name": model_name,
        "mode": mode,
        "watermark_info": {"enabled": watermark_enabled},
    }


def _opt(payload: dict, key: str, value: str) -> None:
    if value:
        payload[key] = value


# ══════════════════════════════════════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════════════════════════════════════

class KlingAuth:
    CATEGORY     = "KlingAI"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("api_token",)
    FUNCTION     = "generate"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "访问密钥": ("STRING", {"default": "", "multiline": False}),
                "安全密钥": ("STRING", {"default": "", "multiline": False}),
            },
            "optional": {
                "有效期秒": ("INT", {"default": 1800, "min": 300, "max": 86400}),
            },
        }

    def generate(self, 访问密钥: str, 安全密钥: str, 有效期秒: int = 1800):
        ak = (访问密钥 or "").strip()
        sk = (安全密钥 or "").strip()
        if not ak or not sk:
            raise ValueError("访问密钥和安全密钥不能为空")
        token = encode_jwt_token(ak, sk, ttl=有效期秒)
        print(f"[KlingAI] Token generated (ttl={有效期秒}s): {token[:20]}…")
        return (token,)


# ══════════════════════════════════════════════════════════════════════════════
# 1. 文本到视频
# ══════════════════════════════════════════════════════════════════════════════

class KlingText2Video:
    CATEGORY     = "KlingAI"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_url",)
    FUNCTION     = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "提示词":   ("STRING", {"multiline": True, "default": ""}),
                "模式":     (MODES,),
                "时长":     ("INT", _DUR),
                "画面比例": (RATIOS, {"default": "16:9"}),
            },
            "optional": {
                "API令牌":      ("STRING", {"default": ""}),
                "模型名称":     (MODELS,),
                "声音":         (["off", "on"], {"default": "off"}),
                "多镜头":       ("BOOLEAN", {"default": False}),
                "分镜方式":     (["intelligence", "customize"], {"default": "intelligence"}),
                "分镜脚本":     (_T_MULTI_SHOT,),
                "添加水印":     ("BOOLEAN", {"default": False}),
                "回调地址":     ("STRING", {"default": ""}),
                "自定义任务ID": ("STRING", {"default": ""}),
                "等待超时秒":   ("INT", {"default": 600, "min": 60, "max": 1800}),
            },
        }

    def run(self, 提示词, 模式, 时长, 画面比例,
            API令牌="", 模型名称="kling-video-o1", 声音="off", 多镜头=False, 分镜方式="intelligence",
            分镜脚本=None, 添加水印=False,
            回调地址="", 自定义任务ID="", 等待超时秒=600):

        payload = _base(模型名称, 模式, 添加水印)
        payload["duration"]     = str(时长)
        payload["aspect_ratio"] = 画面比例
        payload["sound"]        = 声音

        if 多镜头:
            payload["multi_shot"] = True
            payload["shot_type"]  = 分镜方式
            if 分镜脚本:
                payload["multi_prompt"] = 分镜脚本
        else:
            payload["prompt"] = 提示词

        _opt(payload, "callback_url",     回调地址.strip())
        _opt(payload, "external_task_id", 自定义任务ID.strip())
        return _run_video(API令牌, payload, 等待超时秒)


# ══════════════════════════════════════════════════════════════════════════════
# 1a. 多镜头分镜脚本配置（连接到文本到视频）
# ══════════════════════════════════════════════════════════════════════════════

class KlingMultiShot:
    """Builds the multi_prompt list for multi-shot text-to-video.
    Each shot has its own prompt and duration; index is assigned automatically."""
    CATEGORY     = "KlingAI"
    RETURN_TYPES = (_T_MULTI_SHOT,)
    RETURN_NAMES = ("分镜脚本",)
    FUNCTION     = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "镜头1提示词": ("STRING", {"multiline": True, "default": ""}),
                "镜头1时长":   ("INT", _DUR_SHOT),
            },
            "optional": {
                "镜头2提示词": ("STRING", {"multiline": True, "default": ""}),
                "镜头2时长":   ("INT", _DUR_SHOT),
                "镜头3提示词": ("STRING", {"multiline": True, "default": ""}),
                "镜头3时长":   ("INT", _DUR_SHOT),
                "镜头4提示词": ("STRING", {"multiline": True, "default": ""}),
                "镜头4时长":   ("INT", _DUR_SHOT),
                "镜头5提示词": ("STRING", {"multiline": True, "default": ""}),
                "镜头5时长":   ("INT", _DUR_SHOT),
                "镜头6提示词": ("STRING", {"multiline": True, "default": ""}),
                "镜头6时长":   ("INT", _DUR_SHOT),
            },
        }

    def run(self, 镜头1提示词, 镜头1时长,
            镜头2提示词="", 镜头2时长=3,
            镜头3提示词="", 镜头3时长=3,
            镜头4提示词="", 镜头4时长=3,
            镜头5提示词="", 镜头5时长=3,
            镜头6提示词="", 镜头6时长=3):
        raw = [
            (镜头1提示词, 镜头1时长),
            (镜头2提示词, 镜头2时长),
            (镜头3提示词, 镜头3时长),
            (镜头4提示词, 镜头4时长),
            (镜头5提示词, 镜头5时长),
            (镜头6提示词, 镜头6时长),
        ]
        shots = [
            {"index": i + 1, "prompt": p.strip(), "duration": str(d)}
            for i, (p, d) in enumerate(raw)
            if p and p.strip()
        ]
        return (shots,)


# ══════════════════════════════════════════════════════════════════════════════
# 2. 图像到视频
# ══════════════════════════════════════════════════════════════════════════════

class KlingImage2Video:
    CATEGORY     = "KlingAI"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_url",)
    FUNCTION     = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "提示词":   ("STRING", {"multiline": True, "default": "让<<<image_1>>>中的人物向镜头挥手"}),
                "参考图1":  ("STRING", {"default": ""}),
                "模式":     (MODES,),
                "时长":     ("INT", _DUR),
                "画面比例": (RATIOS, {"default": "16:9"}),
            },
            "optional": {
                "API令牌":      ("STRING", {"default": ""}),
                "模型名称":     (MODELS,),
                "参考图2":      ("STRING", {"default": ""}),
                "参考图3":      ("STRING", {"default": ""}),
                "参考图4":      ("STRING", {"default": ""}),
                "参考图5":      ("STRING", {"default": ""}),
                "元素ID列表":   ("STRING", {"default": "", "placeholder": "123456,789012"}),
                "声音":         (["off", "on"], {"default": "off"}),
                "添加水印":     ("BOOLEAN", {"default": False}),
                "回调地址":     ("STRING", {"default": ""}),
                "自定义任务ID": ("STRING", {"default": ""}),
                "等待超时秒":   ("INT", {"default": 600, "min": 60, "max": 1800}),
            },
        }

    def run(self, 提示词, 参考图1, 模式, 时长, 画面比例,
            API令牌="", 模型名称="kling-video-o1", 参考图2="", 参考图3="", 参考图4="", 参考图5="",
            元素ID列表="", 声音="off", 添加水印=False,
            回调地址="", 自定义任务ID="", 等待超时秒=600):

        image_list = [
            {"image_url": u.strip()}
            for u in [参考图1, 参考图2, 参考图3, 参考图4, 参考图5]
            if u and u.strip()
        ]

        payload = _base(模型名称, 模式, 添加水印)
        payload["prompt"]       = 提示词
        payload["duration"]     = str(时长)
        payload["aspect_ratio"] = 画面比例
        payload["sound"]        = 声音
        payload["image_list"]   = image_list

        if 元素ID列表.strip():
            payload["element_list"] = _parse_element_list(元素ID列表)

        _opt(payload, "callback_url",     回调地址.strip())
        _opt(payload, "external_task_id", 自定义任务ID.strip())
        return _run_video(API令牌, payload, 等待超时秒)


# ══════════════════════════════════════════════════════════════════════════════
# 3. 首尾帧到视频
# ══════════════════════════════════════════════════════════════════════════════

class KlingFrame2Video:
    CATEGORY     = "KlingAI"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_url",)
    FUNCTION     = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "提示词":   ("STRING", {"multiline": True, "default": ""}),
                "首帧URL":  ("STRING", {"default": ""}),
                "模式":     (MODES,),
                "时长":     ("INT", _DUR),
            },
            "optional": {
                "API令牌":      ("STRING", {"default": ""}),
                "模型名称":     (MODELS,),
                "尾帧URL":      ("STRING", {"default": ""}),
                "元素ID列表":   ("STRING", {"default": "", "placeholder": "123456,789012"}),
                "添加水印":     ("BOOLEAN", {"default": False}),
                "回调地址":     ("STRING", {"default": ""}),
                "自定义任务ID": ("STRING", {"default": ""}),
                "等待超时秒":   ("INT", {"default": 600, "min": 60, "max": 1800}),
            },
        }

    def run(self, 提示词, 首帧URL, 模式, 时长,
            API令牌="", 模型名称="kling-video-o1", 尾帧URL="", 元素ID列表="", 添加水印=False,
            回调地址="", 自定义任务ID="", 等待超时秒=600):

        image_list = [{"image_url": 首帧URL.strip(), "type": "first_frame"}]
        if 尾帧URL and 尾帧URL.strip():
            image_list.append({"image_url": 尾帧URL.strip(), "type": "end_frame"})

        payload = _base(模型名称, 模式, 添加水印)
        payload["prompt"]     = 提示词
        payload["duration"]   = str(时长)
        payload["image_list"] = image_list
        # aspect_ratio 由首帧尺寸决定，无需传入

        if 元素ID列表.strip():
            payload["element_list"] = _parse_element_list(元素ID列表)

        _opt(payload, "callback_url",     回调地址.strip())
        _opt(payload, "external_task_id", 自定义任务ID.strip())
        return _run_video(API令牌, payload, 等待超时秒)


# ══════════════════════════════════════════════════════════════════════════════
# 4. 视频到视频（特征参考 / 延伸）
# ══════════════════════════════════════════════════════════════════════════════

class KlingVideoFeature:
    CATEGORY     = "KlingAI"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_url",)
    FUNCTION     = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "提示词":   ("STRING", {"multiline": True, "default": "参考<<<video_1>>>的运镜方式，生成一段视频"}),
                "视频URL":  ("STRING", {"default": ""}),
                "模式":     (MODES,),
                "时长":     ("INT", _DUR_VID),
                "画面比例": (RATIOS, {"default": "16:9"}),
            },
            "optional": {
                "API令牌":      ("STRING", {"default": ""}),
                "模型名称":     (MODELS,),
                "保留原声":     (["yes", "no"], {"default": "yes"}),
                # 可附加图片/主体作为额外参考（用 <<<image_N>>> / <<<element_N>>> 在提示词中引用）
                "参考图1":      ("STRING", {"default": ""}),
                "参考图2":      ("STRING", {"default": ""}),
                "参考图3":      ("STRING", {"default": ""}),
                "参考图4":      ("STRING", {"default": ""}),
                "元素ID列表":   ("STRING", {"default": "", "placeholder": "123456,789012"}),
                "添加水印":     ("BOOLEAN", {"default": False}),
                "回调地址":     ("STRING", {"default": ""}),
                "自定义任务ID": ("STRING", {"default": ""}),
                "等待超时秒":   ("INT", {"default": 600, "min": 60, "max": 1800}),
            },
        }

    def run(self, 提示词, 视频URL, 模式, 时长, 画面比例,
            API令牌="", 模型名称="kling-video-o1", 保留原声="yes",
            参考图1="", 参考图2="", 参考图3="", 参考图4="",
            元素ID列表="", 添加水印=False,
            回调地址="", 自定义任务ID="", 等待超时秒=600):

        payload = _base(模型名称, 模式, 添加水印)
        payload["prompt"]       = 提示词
        payload["duration"]     = str(时长)
        payload["aspect_ratio"] = 画面比例
        payload["sound"]        = "off"  # 有 video_list 时 API 要求声音关闭
        payload["video_list"]   = [{
            "video_url":           视频URL.strip(),
            "refer_type":          "feature",
            "keep_original_sound": 保留原声,
        }]

        image_list = [
            {"image_url": u.strip()}
            for u in [参考图1, 参考图2, 参考图3, 参考图4]
            if u and u.strip()
        ]
        if image_list:
            payload["image_list"] = image_list

        if 元素ID列表.strip():
            payload["element_list"] = _parse_element_list(元素ID列表)

        _opt(payload, "callback_url",     回调地址.strip())
        _opt(payload, "external_task_id", 自定义任务ID.strip())
        return _run_video(API令牌, payload, 等待超时秒)


# ══════════════════════════════════════════════════════════════════════════════
# 5. 编辑视频（指令变换）
# ══════════════════════════════════════════════════════════════════════════════

class KlingVideoEdit:
    CATEGORY     = "KlingAI"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_url",)
    FUNCTION     = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "提示词":   ("STRING", {"multiline": True, "default": ""}),
                "视频URL":  ("STRING", {"default": ""}),
                "模式":     (MODES,),
            },
            "optional": {
                "API令牌":      ("STRING", {"default": ""}),
                "模型名称":     (MODELS,),
                "保留原声":     (["yes", "no"], {"default": "yes"}),
                # 有参考视频时，参考图片数量之和不得超过 4
                "参考图1":      ("STRING", {"default": ""}),
                "参考图2":      ("STRING", {"default": ""}),
                "参考图3":      ("STRING", {"default": ""}),
                "参考图4":      ("STRING", {"default": ""}),
                "元素ID列表":   ("STRING", {"default": "", "placeholder": "123456,789012"}),
                "添加水印":     ("BOOLEAN", {"default": False}),
                "回调地址":     ("STRING", {"default": ""}),
                "自定义任务ID": ("STRING", {"default": ""}),
                "等待超时秒":   ("INT", {"default": 600, "min": 60, "max": 1800}),
            },
        }

    def run(self, 提示词, 视频URL, 模式,
            API令牌="", 模型名称="kling-video-o1", 保留原声="yes",
            参考图1="", 参考图2="", 参考图3="", 参考图4="",
            元素ID列表="", 添加水印=False, 回调地址="", 自定义任务ID="", 等待超时秒=600):

        payload = _base(模型名称, 模式, 添加水印)
        payload["prompt"] = 提示词
        payload["sound"]  = "off"
        # 时长和画面比例由输入视频决定，API 忽略这两个字段
        payload["video_list"] = [{
            "video_url":           视频URL.strip(),
            "refer_type":          "base",
            "keep_original_sound": 保留原声,
        }]

        image_list = [
            {"image_url": u.strip()}
            for u in [参考图1, 参考图2, 参考图3, 参考图4]
            if u and u.strip()
        ]
        if image_list:
            payload["image_list"] = image_list

        if 元素ID列表.strip():
            payload["element_list"] = _parse_element_list(元素ID列表)

        _opt(payload, "callback_url",     回调地址.strip())
        _opt(payload, "external_task_id", 自定义任务ID.strip())
        return _run_video(API令牌, payload, 等待超时秒)


# ══════════════════════════════════════════════════════════════════════════════
# 6. URL 下载视频
# ══════════════════════════════════════════════════════════════════════════════

class KlingVideoFromURL:
    CATEGORY     = "KlingAI"
    OUTPUT_NODE  = True
    RETURN_TYPES = ("VIDEO",)
    RETURN_NAMES = ("视频",)
    FUNCTION     = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "视频URL": ("STRING", {"default": ""}),
            },
        }

    def run(self, 视频URL):
        import folder_paths

        url = 视频URL.strip()
        if not url:
            raise ValueError("视频URL不能为空")

        output_dir = folder_paths.get_output_directory()
        filename = f"kling_{int(time.time())}.mp4"
        filepath = os.path.join(output_dir, filename)

        print(f"[KlingAI] Downloading {url} → {filepath}")
        urllib.request.urlretrieve(url, filepath)
        print(f"[KlingAI] Saved: {filename}")

        if not _HAS_VIDEO_TYPE:
            raise RuntimeError(
                "ComfyUI VIDEO 类型不可用（需要 comfy_api.input_impl.VideoFromFile），"
                "请升级 ComfyUI 至支持原生 VIDEO 类型的版本。"
            )

        return {
            "ui":     {"videos": [{"filename": filename, "subfolder": "", "type": "output"}]},
            "result": (_VideoFromFile(filepath),),
        }


# ══════════════════════════════════════════════════════════════════════════════

NODE_CLASS_MAPPINGS = {
    "KlingAuth":         KlingAuth,
    "KlingText2Video":   KlingText2Video,
    "KlingMultiShot":    KlingMultiShot,
    "KlingImage2Video":  KlingImage2Video,
    "KlingFrame2Video":  KlingFrame2Video,
    "KlingVideoFeature": KlingVideoFeature,
    "KlingVideoEdit":    KlingVideoEdit,
    "KlingVideoFromURL": KlingVideoFromURL,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KlingAuth":         "Kling Auth",
    "KlingText2Video":   "Kling 文本到视频",
    "KlingMultiShot":    "Kling 多镜头分镜脚本",
    "KlingImage2Video":  "Kling 图像到视频",
    "KlingFrame2Video":  "Kling 首尾帧到视频",
    "KlingVideoFeature": "Kling 视频到视频",
    "KlingVideoEdit":    "Kling 编辑视频",
    "KlingVideoFromURL": "Kling 下载视频",
}
