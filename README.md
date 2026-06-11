# bilibili-extractor

从 Bilibili 习题讲解视频中自动提取题目，生成结构化 JSON。

**流程**：视频 → 音频转写(Whisper) + 画面OCR(PaddleOCR) → DeepSeek 融合 → 结构化题目列表

## 安装

### macOS

```bash
brew install ffmpeg yt-dlp whisper-cpp
pip install -r requirements.txt
```

从 [Hugging Face](https://huggingface.co/ggerganov/whisper.cpp) 下载 whisper 模型，推荐 `ggml-large-v3-turbo.bin`，放在项目根目录。

### Windows

```bash
winget install ffmpeg
pip install -r requirements.txt
```

faster-whisper 会自动下载模型。如果有 NVIDIA GPU，安装 `paddlepaddle-gpu` 替代 `paddlepaddle`。

### Linux / WSL2

```bash
sudo apt install ffmpeg cmake build-essential
pip install -r requirements.txt
```

有 GPU 时安装 `paddlepaddle-gpu`。

## 使用

```bash
export DEEPSEEK_API_KEY="sk-xxx"
python pipeline.py --model-path ggml-large-v3-turbo.bin
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--urls` | 视频链接文件路径 | `urls.txt` |
| `--model-path` | Whisper 模型路径 | `ggml-large-v3-turbo.bin` |
| `--api-key` | DeepSeek API Key（优先于环境变量） | — |
| `--deepseek-model` | DeepSeek 模型名 | `deepseek-v4-flash` |
| `--fps` | 截图频率（帧/秒） | `0.333`（每3秒1帧） |
| `--quality` | 视频流最大高度 | `720` |
| `--resume` | 跳过已处理的视频 | 否 |
| `--vision` | 启用视觉模型描述画面（更慢，适合图表多的视频） | 否 |
| `--no-merge` | 不合并合集结果 | 否 |

### 单集测试 vs 全量运行

`urls.txt` 中直接写 BV 号会展开该视频的**所有分 P**。只想跑单集时，在 URL 后加 `?p=N`：

```
# 全集（129个视频）
https://www.bilibili.com/video/BV1FdetzEEVA/

# 只跑第1集
https://www.bilibili.com/video/BV1FdetzEEVA?p=1
```

### 合集/播放列表

也支持 B站合集和播放列表链接，会自动展开所有视频并合并输出：

```
https://space.bilibili.com/123456/channel/collectiondetail?sid=789
https://www.bilibili.com/medialist/play/123456?business_id=789
```

### B站登录

公开视频无需登录。对付费课程，扫码一次：

```bash
python login.py
```

登录态保存在 `~/.bilibili_api/`。

## 输出

每视频输出一个 JSON 文件到 `output/`，格式：

```json
{
  "video_id": "BV1FdetzEEVA_p1",
  "title": "王道2027版计算机网络习题讲解",
  "url": "https://www.bilibili.com/video/BV1FdetzEEVA",
  "duration_seconds": 57040,
  "problems": [
    {
      "id": 1,
      "time_range": "00:00 - 01:23",
      "topic": "计算机网络定义",
      "content": "计算机网络可被理解为（）。 A．...",
      "has_solution": true,
      "solution_summary": "根据定义，计算机网络是..."
    }
  ]
}
```

合集结果会额外生成 `{collection_id}.merged.json`，合并所有分集的题目。

## 技术架构

```
pipeline.py         主流程编排
src/
├── bilibili.py     B站API（视频信息、音频/视频流下载）
├── bilibili_auth.py 二维码登录
├── config.py       跨平台运行时检测
├── transcribe.py   Whisper 音频转写（whisper.cpp / faster-whisper 自动选择）
├── frames.py       视频帧提取 + 去重（ffmpeg + perceptual hash）
├── ocr.py          PaddleOCR 画面文字识别
├── vision.py       ModelScope 多模态画面描述（可选）
└── fuse.py         DeepSeek API 融合
prompts/
└── fuse.txt        融合 prompt 模板
```

### 管道步骤

1. **获取视频信息** — 调用 B站 API 获取标题、时长
2. **下载音频** — 从 DASH 流下载音频轨道，转 WAV (16kHz mono)
3. **Whisper 转写** — macOS 用 whisper.cpp (CoreML 加速)，Windows 用 faster-whisper
4. **帧提取** — ffmpeg 按固定帧率截图，perceptual hash 去重
5. **PaddleOCR** — 识别帧中的文字（公式、题目、PPT内容）
6. **视觉描述**（可选）— ModelScope 多模态模型描述图表/曲线/几何图形
7. **DeepSeek 融合** — 将转写+OCR+视觉描述发送给 DeepSeek，输出结构化题目

## 跨平台支持

| 平台 | Whisper | OCR | 状态 |
|------|---------|-----|------|
| macOS | whisper-cli (CoreML) | PaddleOCR CPU | 已测试 |
| Windows | faster-whisper (CPU/CUDA) | PaddleOCR GPU | 代码就绪 |
| Linux/WSL2 | faster-whisper (CPU/CUDA) | PaddleOCR GPU | 代码就绪 |

## 性能参考

单视频（14分钟，1080p）：~6分钟，产出 5-10 道题。

| 步骤 | 耗时 |
|------|------|
| 音频下载 | ~5s |
| Whisper 转写 | ~45s |
| 帧提取 | ~10s |
| PaddleOCR | ~5min |
| DeepSeek 融合 | ~10s |

启用 `--vision` 将额外增加约 2.5 分钟。
