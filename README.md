# 🎬 AI Video Factory - Automated 0-Dong Reels Bot

Hệ thống kiến trúc tự động hóa sản xuất video ngắn (Facebook Reels, TikTok, YouTube Shorts) chuẩn dọc 9:16 (1080x1920) vận hành hoàn toàn tự động qua **n8n**, **Docker** và các **Python Micro-scripts** theo tiêu chí **0 đồng**.

---

## 🏗️ Kiến Trúc Hệ Thống (System Architecture)

```
[Schedule / Cron]
       │
       ▼
[1. research_agent.py] ──> Cào RSS xu hướng / tin tức mới nhất (0đ)
       │
       ▼
[2. Custom LLM Node]   ──> Sinh kịch bản chuẩn JSON (Hook, Voiceover, Prompts, Caption)
       │
       ├─────────────────────────┬─────────────────────────┐
       ▼                         ▼                         ▼
[3. fetch_image.py]     [4. generate_tts.py]    [5. generate_music.py]
FLUX 9:16 (Pollinations)  Edge-TTS (Hoài My Nữ)   ACE-Step 1.5 / Lo-Fi Synth
       │                         │                         │
       └─────────────────────────┼─────────────────────────┘
                                 ▼
                     [6. render_video.py]
                     - Hiệu ứng Ken Burns (Zoom/Pan)
                     - Audio Ducking (Nhạc 15%, Thoại 100%)
                     - Phụ đề chữ vàng viền đen Reels Style
                                 │
                                 ▼
                    /shared_media/outputs/final_reel.mp4
                                 │
                                 ▼
               [7. Meta Graph API Reels 3-Phase Upload]
               - Phase 1: Start Session -> upload_url
               - Phase 2: Binary Video Stream
               - Phase 3: Finish & Auto-Publish với Caption
```

---

## 📁 Cấu Trúc Thư Mục

```text
ai-video-factory/
├── .antigravity/
│   ├── workspace-guidelines.md     # Quy chuẩn code Python 3.10+, xử lý path, env
│   └── setup.sh                    # Script cài đặt FFmpeg & font tiếng Việt
├── docker-compose.yml              # Khởi chạy n8n với Python3, FFmpeg, shared volumes
├── Dockerfile                      # Image n8n tích hợp sẵn Python & dependencies
├── setup.sh                        # Script setup môi trường local/container
├── .env                            # Chứa API Keys (Custom LLM, Facebook Page Token...)
├── .env.example                    # Mẫu cấu hình
├── shared_media/
│   ├── temp/                       # Ảnh, audio thoại, nhạc nền tạm thời
│   └── outputs/                    # File video thành phẩm: final_reel.mp4
├── n8n_data/                       # Lưu trữ database & thông số workflow n8n
├── scripts/
│   ├── requirements.txt            # Thư viện Python (edge-tts, pillow, bs4...)
│   ├── research_agent.py           # Cào web RSS, lấy bối cảnh kịch bản
│   ├── generate_tts.py             # Microsoft Edge-TTS tiếng Việt (vi-VN-HoaiMyNeural)
│   ├── generate_music.py           # Giả lập ACE-Step 1.5 / Bộ sinh Synth Lo-fi 0đ
│   ├── fetch_image.py              # Kéo ảnh FLUX 9:16 (Pollinations AI)
│   └── render_video.py             # FFmpeg ghép ảnh Ken Burns + Audio Ducking + Subtitles
└── workflows/
    └── master_n8n_reels_bot.json   # File mã nguồn n8n workflow đầy đủ các Node
```

---

## 🚀 Hướng Dẫn Cài Đặt & Vận Hành

### Bước 1: Cấu hình Biến Môi Trường (`.env`)

Chỉnh sửa file `.env` tại thư mục gốc:

```env
# LLM Endpoint (Oxion AI, DeepSeek, OpenRouter, OpenAI, vLLM...)
CUSTOM_LLM_API_URL=https://api.openai.com/v1
CUSTOM_LLM_API_KEY=your_api_key_here
CUSTOM_LLM_MODEL_NAME=gpt-4o-mini

# Meta Facebook Reels API
FB_PAGE_ID=123456789012345
FB_ACCESS_TOKEN=EAAG...your_long_lived_token
```

### Bước 2: Khởi động với Docker Compose

Chạy lệnh để build image và khởi động n8n container:

```bash
docker compose up -d --build
```

Sau khi chạy, truy cập giao diện n8n tại: **`http://localhost:5678`**

### Bước 3: Import Workflow vào n8n

1. Mở n8n UI -> Chọn **Workflows** -> **Import from File**.
2. Chọn file: `workflows/master_n8n_reels_bot.json`.
3. Bật trạng thái **Active** cho workflow để tự động chạy lúc 08:00 AM mỗi ngày, hoặc ấn **Test Step** để chạy thử ngay.

---

## 🧪 Kiểm Thử Từng Script Độc Lập (Local Test)

Bạn có thể chạy thử từng micro-script trực tiếp bằng dòng lệnh:

```bash
# 1. Cào bối cảnh tin tức
python scripts/research_agent.py

# 2. Tạo ảnh dọc 9:16 từ Pollinations
python scripts/fetch_image.py --prompt "Cyberpunk Hanoi city in 2050 with neon lights, flying vehicles" --output shared_media/temp/scene_01.jpg

# 3. Tạo giọng đọc Tiếng Việt Edge-TTS
python scripts/generate_tts.py --text "Khám phá bí mật công nghệ tương lai cùng AI Video Factory!" --output shared_media/temp/voiceover.mp3

# 4. Tạo nhạc nền 60s
python scripts/generate_music.py --prompt "Chill lofi ambient beat" --duration 60 --output shared_media/temp/background_music.mp3

# 5. Render video hoàn chỉnh
python scripts/render_video.py --output shared_media/outputs/final_reel.mp4
```

---

## 🔒 Lưu Ý Vận Hành & Bảo Mật API Tùy Chỉnh

1. **Linh hoạt chọn Provider LLM**:
   - `CUSTOM_LLM_API_URL` hỗ trợ bất kỳ nhà cung cấp nào tuân theo chuẩn OpenAI API (Oxion AI, OpenRouter, DeepSeek, vLLM, Ollama...).
   - Đổi tên mô hình trực tiếp qua `CUSTOM_LLM_MODEL_NAME` (ví dụ `claude-3-5-sonnet`, `deepseek-chat`, `gpt-4o-mini`) mà **không cần can thiệp vào mã nguồn**.
2. **Cảnh báo bảo mật**:
   - Tuyệt đối **không nhập thông tin thẻ tín dụng cá nhân** hoặc dữ liệu nhạy cảm vào các dịch vụ proxy API trung gian chưa rõ tư cách pháp nhân.
   - Thường xuyên làm mới (refresh) `FB_ACCESS_TOKEN` dạng Long-Lived Token (thời hạn 60 ngày) để tránh gián đoạn luồng tự động đăng bài.
