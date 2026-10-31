FROM docker.n8n.io/n8nio/n8n:latest

USER root

# Cài đặt Python3, pip, FFmpeg và Fonts tiếng Việt / Unicode
RUN apk update && \
    apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    fontconfig \
    ttf-dejavu \
    bash \
    curl

# Cài đặt các thư viện Python cần thiết
COPY scripts/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

# Đưa virtualenv vào PATH để lệnh `python3` và các thư viện luôn có sẵn
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/scripts:$PYTHONPATH"

# Phân quyền cho thư mục dữ liệu
RUN mkdir -p /shared_media/temp /shared_media/outputs && \
    chmod -R 777 /shared_media

USER node
