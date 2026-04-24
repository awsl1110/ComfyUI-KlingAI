# ComfyUI-KlingAI

在 ComfyUI 中调用可灵 AI（KlingAI）OmniVideo API，支持文本/图像/首尾帧/视频多种生成模式。

---

## 环境要求

- ComfyUI（支持原生 VIDEO 类型的版本，用于「下载视频」节点）
- Python 3.8+
- 依赖库：`requests`、`PyJWT`

```bash
pip install requests PyJWT
```

---

## 安装

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/your-org/ComfyUI-KlingAI
```

重启 ComfyUI，节点菜单中出现 **KlingAI** 分类即安装成功。

---

## 鉴权

所有生成节点都需要通过 **Kling Auth** 节点获取 `api_token`，再将其连接到目标节点的「API令牌」输入端口。

在可灵 AI 开放平台（[klingai.com](https://klingai.com)）创建应用后，可以拿到「访问密钥（Access Key）」和「安全密钥（Secret Key）」。

```
Kling Auth
├── 访问密钥  ← Access Key
├── 安全密钥  ← Secret Key
└── 有效期秒  ← 默认 1800s，最长 86400s
        ↓
    api_token（STRING）
```

> Token 在客户端本地生成（HS256 JWT），不经过任何中间服务器。

---

## 节点一览

### Kling Auth

生成鉴权 Token，输出 `api_token` 字符串连接到其他节点。

| 参数 | 类型 | 说明 |
|------|------|------|
| 访问密钥 | STRING | 可灵开放平台 Access Key |
| 安全密钥 | STRING | 可灵开放平台 Secret Key |
| 有效期秒 | INT | Token 有效时长，默认 1800s |

---

### Kling 文本到视频

纯文字驱动生成视频，支持多镜头模式。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 模型名称 | 下拉 | ✓ | `kling-video-o1` / `kling-v3-omni` |
| 提示词 | STRING | ✓ | 视频内容描述（多镜头模式下由分镜脚本覆盖） |
| 模式 | 下拉 | ✓ | `pro`（高质量）/ `std`（标准） |
| 时长 | 滑动条 | ✓ | 3 ~ 15 秒，默认 5s |
| 画面比例 | 下拉 | ✓ | `16:9` / `9:16` / `1:1` |
| API令牌 | STRING | ✓ | 连接 Kling Auth 节点输出 |
| 声音 | 下拉 | — | `off` / `on`，开启后自动生成背景音 |
| 多镜头 | BOOLEAN | — | 开启后启用分镜模式 |
| 分镜方式 | 下拉 | — | `intelligence`（自动）/ `customize`（手动，需连接分镜脚本） |
| 分镜脚本 | KLING_MULTI_SHOT | — | 连接「多镜头分镜脚本」节点 |
| 添加水印 | BOOLEAN | — | 默认关闭 |
| 回调地址 | STRING | — | 任务完成后的 Webhook URL |
| 自定义任务ID | STRING | — | 用于业务侧追踪，需保证唯一 |
| 等待超时秒 | INT | — | 轮询超时，默认 600s |

**输出：** `video_url`（STRING）

---

### Kling 多镜头分镜脚本

为文本到视频的多镜头模式配置每个镜头的提示词，最多支持 4 个镜头。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 镜头1提示词 | STRING | ✓ | 第一个镜头的内容描述 |
| 镜头2提示词 | STRING | — | 留空则忽略该镜头 |
| 镜头3提示词 | STRING | — | |
| 镜头4提示词 | STRING | — | |

**输出：** `分镜脚本`（KLING_MULTI_SHOT）→ 连接到「文本到视频」的「分镜脚本」端口

**典型连法：**
```
Kling 多镜头分镜脚本 ──分镜脚本──▶ Kling 文本到视频
                                      （多镜头 = True，分镜方式 = customize）
```

---

### Kling 图像到视频

以一张或多张参考图为基础生成视频，提示词中用 `<<<image_N>>>` 引用图片。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 模型名称 | 下拉 | ✓ | |
| 提示词 | STRING | ✓ | 可用 `<<<image_1>>>` ~ `<<<image_5>>>` 引用各图 |
| 参考图1 | STRING | ✓ | 图片 URL |
| 模式 | 下拉 | ✓ | |
| 时长 | 滑动条 | ✓ | 3 ~ 15 秒 |
| 画面比例 | 下拉 | ✓ | |
| API令牌 | STRING | ✓ | |
| 参考图2 ~ 参考图5 | STRING | — | 最多 5 张图片 |
| 声音 | 下拉 | — | |
| 添加水印 | BOOLEAN | — | |
| 回调地址 | STRING | — | |
| 自定义任务ID | STRING | — | |
| 等待超时秒 | INT | — | 默认 600s |

**输出：** `video_url`（STRING）

---

### Kling 首尾帧到视频

指定首帧（必填）和尾帧（可选），生成补间视频。画面比例由首帧尺寸自动决定，无需手动设置。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 模型名称 | 下拉 | ✓ | |
| 提示词 | STRING | ✓ | 对过渡过程的描述 |
| 首帧URL | STRING | ✓ | 视频起始帧图片 URL |
| 模式 | 下拉 | ✓ | |
| 时长 | 滑动条 | ✓ | 3 ~ 15 秒 |
| API令牌 | STRING | ✓ | |
| 尾帧URL | STRING | — | 留空则仅使用首帧 |
| 添加水印 | BOOLEAN | — | |
| 回调地址 | STRING | — | |
| 自定义任务ID | STRING | — | |
| 等待超时秒 | INT | — | 默认 600s |

**输出：** `video_url`（STRING）

---

### Kling 视频到视频

以已有视频为特征参考，生成风格延伸或续集视频。

> 有视频输入时，API 强制关闭声音输出。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 模型名称 | 下拉 | ✓ | |
| 提示词 | STRING | ✓ | |
| 视频URL | STRING | ✓ | 参考视频地址 |
| 模式 | 下拉 | ✓ | |
| 时长 | 滑动条 | ✓ | 3 ~ 10 秒 |
| 画面比例 | 下拉 | ✓ | |
| API令牌 | STRING | ✓ | |
| 保留原声 | 下拉 | — | `yes` / `no` |
| 添加水印 | BOOLEAN | — | |
| 回调地址 | STRING | — | |
| 自定义任务ID | STRING | — | |
| 等待超时秒 | INT | — | 默认 600s |

**输出：** `video_url`（STRING）

---

### Kling 编辑视频

对已有视频按提示词指令进行变换编辑，可附加最多 4 张参考图辅助描述目标风格。

> 时长和画面比例由输入视频决定，无需填写。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 模型名称 | 下拉 | ✓ | |
| 提示词 | STRING | ✓ | 编辑指令，如「把场景改为雪天」 |
| 视频URL | STRING | ✓ | 待编辑视频地址 |
| 模式 | 下拉 | ✓ | |
| API令牌 | STRING | ✓ | |
| 保留原声 | 下拉 | — | `yes` / `no` |
| 参考图1 ~ 参考图4 | STRING | — | 目标风格参考图，总数不超过 4 张 |
| 添加水印 | BOOLEAN | — | |
| 回调地址 | STRING | — | |
| 自定义任务ID | STRING | — | |
| 等待超时秒 | INT | — | 默认 600s |

**输出：** `video_url`（STRING）

---

### Kling 下载视频

将 `video_url` 下载到 ComfyUI 输出目录，输出原生 `VIDEO` 类型供后续节点使用。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 视频URL | STRING | ✓ | 连接任意生成节点的 `video_url` 输出 |

**输出：** `视频`（VIDEO）

> 需要 ComfyUI 支持原生 VIDEO 类型（`comfy_api.input_impl.VideoFromFile`），请使用较新版本的 ComfyUI。

---

## 典型工作流

### 文本生成视频

```
Kling Auth ──api_token──▶ Kling 文本到视频 ──video_url──▶ Kling 下载视频
```

### 图像生成视频

```
Kling Auth ──api_token──▶ Kling 图像到视频 ──video_url──▶ Kling 下载视频
                                 ↑
                        参考图1（图片URL）
```

### 多镜头文本生成视频

```
Kling 多镜头分镜脚本 ──分镜脚本──▶ Kling 文本到视频 ──video_url──▶ Kling 下载视频
                                          ↑
                                    Kling Auth
                             （多镜头=True，分镜方式=customize）
```

### 首尾帧补间

```
Kling Auth ──api_token──▶ Kling 首尾帧到视频 ──video_url──▶ Kling 下载视频
                                ↑         ↑
                          首帧URL       尾帧URL
```

---

## 参数说明补充

### 模型选择

| 模型 | 特点 |
|------|------|
| `kling-video-o1` | 通用基础模型 |
| `kling-v3-omni` | 全能增强模型，支持更丰富的生成能力 |

### 模式选择

| 模式 | 说明 |
|------|------|
| `pro` | 高质量模式，生成时间较长，消耗积分更多 |
| `std` | 标准模式，速度更快 |

### 等待超时秒

节点会在提交任务后轮询 API 直到任务完成。如果视频较长或服务繁忙，可适当调大此值（最大 1800s）。超时后节点报错，但任务在服务端仍会继续执行，可通过任务 ID 手动查询结果。

---

## 常见问题

**Q：提示 `api_token is required`**  
A：请确认 Kling Auth 节点的输出端口已连接到生成节点的「API令牌」输入端口。

**Q：任务超时**  
A：增大「等待超时秒」，或在可灵 AI 平台控制台用任务 ID 手动查询状态。

**Q：`ComfyUI VIDEO 类型不可用`**  
A：「下载视频」节点需要较新版本的 ComfyUI。如无法升级，可跳过该节点，直接用浏览器或其他工具下载 `video_url` 中的链接。

**Q：如何在提示词中引用多张参考图？**  
A：图像到视频节点中，用 `<<<image_1>>>`、`<<<image_2>>>` 等占位符在提示词里指代对应编号的参考图，例如：`让<<<image_1>>>中的人物走向<<<image_2>>>所示的建筑`。
