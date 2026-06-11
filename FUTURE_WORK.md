## 已解决

### Windows Cookie Issue ~~(TODO)~~
已通过迁移到 `bilibili-api-python` 彻底解决。不再依赖 yt-dlp、浏览器 cookie、DPAPI。
公开视频无需任何登录即可运行，付费课程通过 `python login.py` 扫码一次。

## 待实现

### 1. Windows faster-whisper 适配验证
Mac 上使用 whisper.cpp (brew)，Windows 上代码已支持 faster-whisper 自动降级，
但未在 Windows 上完整验证端到端流程。

### 2. 视觉模型集成测试
API 已验证可用（ModelScope stepfun-ai/Step-3.7-Flash），单帧识别正常。
但 47 帧 × ~3s/帧 ≈ 2.5 分钟额外开销，加上 OCR 5 分钟，单视频约 10 分钟。
如需启用：`python pipeline.py --vision`

### 3. yt-dlp 完全移除
`export_cookies.py`、`get_cookies.py`、`setup.py` 中仍有 yt-dlp 引用，可清理。

### 4. 并行处理
当前是串行处理 129 个视频，可改为多进程并行（受限于 whisper.cpp 和 PaddleOCR 的 GPU 互斥）。

### 5. 进度持久化
当前仅靠 `--resume` 判断单视频是否已完成。如果单个视频中途失败（如 OCR 超时），
无法从中间步骤恢复，需要重新跑整个视频。
