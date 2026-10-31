#!/usr/bin/env bash
# ==============================================================================
# Setup script: Cài đặt FFmpeg, Fonts hỗ trợ Tiếng Việt & Thư viện Python
# ==============================================================================

set -euo pipefail

echo ">>> [1/4] Kiểm tra và cài đặt FFmpeg & Fonts tiếng Việt..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ffmpeg \
        fontconfig \
        fonts-dejavu-core \
        fonts-roboto \
        python3 \
        python3-pip \
        curl \
        ca-certificates
    fc-cache -fv
elif command -v apk >/dev/null 2>&1; then
    apk update
    apk add --no-cache ffmpeg fontconfig ttf-dejavu python3 py3-pip curl bash
else
    echo "(!) Vui lòng đảm bảo ffmpeg đã được cài đặt trong môi trường của bạn."
fi

echo ">>> [2/4] Kiểm tra FFmpeg version..."
ffmpeg -version | head -n 1

echo ">>> [3/4] Cài đặt dependencies Python..."
python3 -m pip install --upgrade pip
if [ -f "scripts/requirements.txt" ]; then
    python3 -m pip install -r scripts/requirements.txt
fi

echo ">>> [4/4] Khởi tạo các thư mục lưu trữ media..."
mkdir -p shared_media/temp shared_media/outputs n8n_data
chmod -R 777 shared_media

echo ">>> Setup hoàn tất thành công!"
