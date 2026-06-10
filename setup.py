#!/usr/bin/env python3
"""Cross-platform one-click setup script.

Detects the platform and prints/executes installation commands.
"""

import platform
import subprocess
import sys


def macos_setup() -> None:
    """Install dependencies on macOS via Homebrew + pip."""
    print("Detected macOS. Installing dependencies...\n")

    brews = ["ffmpeg", "whisper-cpp", "yt-dlp"]
    for pkg in brews:
        print(f"  brew install {pkg}  ...", end=" ")
        try:
            subprocess.run(["brew", "install", pkg], check=True,
                           capture_output=True)
            print("OK")
        except subprocess.CalledProcessError:
            print("FAILED — please install manually")

    print("\n  pip install -r requirements.txt  ...", end=" ")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True, capture_output=True,
        )
        print("OK")
    except subprocess.CalledProcessError:
        print("FAILED — please install manually")

    print("""
╔══════════════════════════════════════════════════════════════╗
║  macOS setup complete.                                       ║
║                                                              ║
║  Next steps:                                                 ║
║  1. Download a whisper model:                                ║
║     https://huggingface.co/ggerganov/whisper.cpp             ║
║     (recommended: ggml-large-v3-turbo.bin)                   ║
║                                                              ║
║  2. Set your DeepSeek API key:                               ║
║     export DEEPSEEK_API_KEY="sk-xxx"                         ║
║                                                              ║
║  3. Add Bilibili URLs to urls.txt                            ║
║                                                              ║
║  4. Run: python pipeline.py --model-path /path/to/model.bin  ║
╚══════════════════════════════════════════════════════════════╝
""")


def windows_setup() -> None:
    """Print Windows installation instructions."""
    has_cuda = False
    try:
        subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        has_cuda = True
    except Exception:
        pass

    print(f"Detected Windows ({'NVIDIA GPU' if has_cuda else 'no GPU'}).\n")
    print("Manual installation steps:\n")
    print("1. Install ffmpeg:")
    print("   winget install ffmpeg")
    print("   (or download from https://ffmpeg.org)")
    print()
    print("2. Install yt-dlp:")
    print("   pip install yt-dlp")
    print()
    print("3. Install whisper.cpp:")
    print("   Download from https://github.com/ggerganov/whisper.cpp/releases")
    if has_cuda:
        print("   Use the CUDA-enabled build (whisper-cublas).")
    print()
    print("4. Install Python dependencies:")
    if has_cuda:
        print("   pip install paddlepaddle-gpu paddleocr imagehash httpx pillow")
    else:
        print("   pip install paddlepaddle paddleocr imagehash httpx pillow")
    print()
    print("5. Download a whisper model:")
    print("   https://huggingface.co/ggerganov/whisper.cpp")
    print("   (recommended: ggml-large-v3-turbo.bin)")
    print()
    print("6. Set your DeepSeek API key:")
    print('   set DEEPSEEK_API_KEY=sk-xxx')
    print()
    print("7. Add Bilibili URLs to urls.txt")
    print()
    print("8. Run:")
    print("   python pipeline.py --model-path C:\\path\\to\\model.bin")


_IS_WSL = False
try:
    with open("/proc/version", "r") as f:
        _IS_WSL = "microsoft" in f.read().lower()
except Exception:
    pass


def linux_setup() -> None:
    """Print Linux / WSL installation instructions."""
    has_cuda = False
    try:
        subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        has_cuda = True
    except Exception:
        pass

    label = "WSL2 (Ubuntu)" if _IS_WSL else "Linux"
    print(f"Detected {label} ({'NVIDIA GPU' if has_cuda else 'no GPU'}).\n")
    print("Installation steps:\n")

    print("1. Install ffmpeg + build tools:")
    print("   sudo apt update && sudo apt install -y ffmpeg cmake build-essential")
    print()

    print("2. Install yt-dlp:")
    print("   pip install yt-dlp")
    print()

    print("3. Compile whisper.cpp:")
    print("   git clone https://github.com/ggerganov/whisper.cpp")
    print("   cd whisper.cpp")
    if has_cuda:
        print("   cmake -B build -DGGML_CUDA=ON")
    else:
        print("   cmake -B build")
    print("   cmake --build build -j --config Release")
    print("   sudo cp build/bin/whisper-cli /usr/local/bin/")
    print()

    print("4. Install Python dependencies:")
    if has_cuda:
        print("   pip install paddlepaddle-gpu paddleocr imagehash httpx pillow")
    else:
        print("   pip install paddlepaddle paddleocr imagehash httpx pillow")
    print()

    print("5. Download a whisper model:")
    print("   https://huggingface.co/ggerganov/whisper.cpp")
    print("   (recommended: ggml-large-v3-turbo.bin)")
    print()

    print("6. Set your DeepSeek API key:")
    print('   export DEEPSEEK_API_KEY="sk-xxx"')
    print()

    print("7. Add Bilibili URLs to urls.txt")
    print()

    print("8. Run:")
    print("   python pipeline.py --model-path /path/to/ggml-large-v3-turbo.bin")


def main() -> None:
    system = platform.system()
    if system == "Darwin":
        if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
            print("Dry-run: would install ffmpeg, whisper-cpp, yt-dlp, pip deps")
        else:
            macos_setup()
    elif system == "Windows":
        windows_setup()
    elif system == "Linux":
        linux_setup()
    else:
        print(f"Unsupported platform: {system}")
        print("Please install dependencies manually:")
        print("  - ffmpeg")
        print("  - whisper.cpp")
        print("  - yt-dlp")
        print("  - pip install paddlepaddle paddleocr imagehash httpx pillow")
        sys.exit(1)


if __name__ == "__main__":
    main()
