#!/usr/bin/env bash
# ==============================================================================
# Script setup môi trường cho AI Video Factory
# Tương thích: Ubuntu 22.04+, Debian 11+, Docker Linux Containers
# ==============================================================================

set -euo pipefail

echo ">>> [1/5] Cập nhật danh sách gói hệ thống..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    
    echo ">>> [2/5] Cài đặt FFmpeg, Fonts hỗ trợ Tiếng Việt và các công cụ cần thiết..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ffmpeg \
        fontconfig \
        fonts-dejavu-core \
        fonts-roboto \
        fonts-noto-cjk \
        python3 \
        python3-pip \
        python3-venv \
        curl \
        ca-certificates

    echo ">>> Cập nhật font cache..."
    fc-cache -fv
elif command -v apk >/dev/null 2>&1; then
    # Hỗ trợ Alpine Linux nếu chạy trên container Alpine
    echo ">>> [2/5] Cài đặt gói cho Alpine..."
    apk update
    apk add --no-cache ffmpeg fontconfig ttf-dejavu python3 py3-pip curl bash
else
    echo "(!) Cảnh báo: Hệ điều hành không dùng apt hoặc apk. Vui lòng tự cài đặt FFmpeg và Fonts thủ công."
fi

echo ">>> [3/5] Kiểm tra phiên bản FFmpeg..."
ffmpeg -version | head -n 1 || {
    echo "(!) Lỗi: FFmpeg chưa được cài đặt chính xác!"
    exit 1
}

echo ">>> [4/5] Thiết lập môi trường Python & Cài đặt thư viện..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

if [ -f "scripts/requirements.txt" ]; then
    echo ">>> Cài đặt các gói Python từ scripts/requirements.txt..."
    python3 -m pip install --upgrade pip
    python3 -m pip install -r scripts/requirements.txt
else
    echo "(!) Không tìm thấy scripts/requirements.txt"
fi

echo ">>> [5/5] Cấp quyền thực thi cho các thư mục media..."
mkdir -p shared_media/temp shared_media/outputs n8n_data
chmod -R 777 shared_media

echo "=== Cài đặt hoàn tất! Hệ thống sẵn sàng tạo video. ==="
