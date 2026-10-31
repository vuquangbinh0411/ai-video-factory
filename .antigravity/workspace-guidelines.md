# Workspace Guidelines - AI Video Factory

Tài liệu quy chuẩn kỹ thuật và tiêu chuẩn lập trình cho dự án **AI Video Factory** (Hệ thống tự động hóa sản xuất video ngắn TikTok/Reels/Shorts).

---

## 1. Môi trường phát triển & Ngôn ngữ

- **Phiên bản Python**: Tối thiểu Python 3.10+ (khuyến nghị Python 3.11).
- **Format & Type Hints**: Bắt buộc sử dụng `type hinting` cho tất cả các function và class (`typing` module, `Path`, `dict`, `list`, `Optional`).
- **Data Validation**: Ưu tiên sử dụng `dataclasses` hoặc `pydantic` khi xử lý cấu trúc dữ liệu kịch bản (Script schema).
- **Asyncio**: Các tác vụ I/O lớn (tải ảnh, sinh giọng đọc TTS) cần ưu tiên chạy bất đồng bộ (`asyncio`, `aiohttp`, `asyncio.gather`) để tối ưu tốc độ.

---

## 2. Quản lý Biến Môi Trường (`.env`)

- **Không hardcode secrets**: Tuyệt đối không lưu API keys, tokens, mật khẩu trong mã nguồn.
- **Thư viện chuẩn**: Sử dụng `python-dotenv` để load file `.env`.
- **Cơ chế fallback an toàn**:
  ```python
  import os
  from pathlib import Path
  from dotenv import load_dotenv

  # Tìm file .env từ thư mục gốc dự án
  ROOT_DIR = Path(__file__).resolve().parent.parent
  load_dotenv(ROOT_DIR / ".env")

  LLM_API_KEY = os.getenv("CUSTOM_LLM_API_KEY", "")
  VOICE_NAME = os.getenv("DEFAULT_TTS_VOICE", "vi-VN-HoaiMyNeural")
  ```
- **Kiểm tra hợp lệ**: Các script phải kiểm tra các biến bắt buộc trước khi thực thi. Nếu thiếu, raise Exception hoặc in thông báo rõ ràng về biến còn thiếu.

---

## 3. Quản lý Đường Dẫn & File Hệ Thống

- **Cross-platform Path**: Bắt buộc sử dụng `pathlib.Path` thay vì nối chuỗi đường dẫn thủ công (`+` hoặc `os.path.join`).
- **Thư mục chia sẻ (`shared_media/`)**:
  - `shared_media/temp/`: Lưu trữ tạm thời các frame ảnh, audio câu thoại, nhạc nền chưa ghép, file subtitle `.srt`/`.ass`.
  - `shared_media/outputs/`: Lưu file video thành phẩm cuối cùng (`final_reel.mp4`).
- **Quy tắc dọn dẹp (Cleanup)**:
  - Cung cấp cờ `--clean-temp` hoặc hàm cleanup sau khi render xong để tránh tràn ổ cứng container.

---

## 4. Chuẩn Giao Tiếp với n8n (CLI & JSON I/O)

Tất cả các script trong thư mục `scripts/` được thiết kế để n8n gọi thông qua node **Execute Command** (hoặc Webhook/Docker Exec).

- **Arguments Interface**: Sử dụng `argparse` chuẩn hóa CLI options:
  - `--output`: Đường dẫn lưu kết quả.
  - `--json`: Xuất kết quả dưới dạng JSON string ra `stdout`.
- **Nguyên tắc stdout vs stderr**:
  - `stdout`: CHỈ in ra JSON hợp lệ khi có cờ hoặc khi kết thúc tiến trình, phục vụ n8n parse output trực tiếp.
  - `stderr` hoặc `logging`: Dùng để log tiến trình, debug, warnings, lỗi. Không in log tự do ra stdout làm vỡ định dạng JSON của n8n.
- **Ví dụ chuẩn trả về**:
  ```json
  {
    "status": "success",
    "video_path": "/shared_media/outputs/reel_20261029_213000.mp4",
    "duration": 28.5,
    "title": "5 Bí Mật Chưa Từng Tiết Lộ",
    "tags": ["#trending", "#reels", "#viral"]
  }
  ```
- **Mã thoát (Exit Codes)**:
  - `0`: Thành công.
  - `1+`: Thất bại (in traceback hoặc error message ra `stderr`).

---

## 5. Quy chuẩn Render Video & Phụ đề (FFmpeg)

- **Độ phân giải chuẩn**: Vertical 9:16 (1080x1920 pixels).
- **Tốc độ khung hình (FPS)**: 30 fps.
- **Codec video**: `libx264` (H.264), `yuv420p` (tương thích 100% với Instagram Reels, TikTok, YouTube Shorts).
- **Codec audio**: `aac`, sample rate `44100Hz` hoặc `48000Hz`, bitrate `192k`.
- **Âm lượng**:
  - Voiceover TTS: 100% (volume = 1.0).
  - Background Music: Giảm âm lượng nền xuống 10% - 15% (ducking) để giọng nói luôn rõ ràng.
- **Phụ đề động**:
  - Font chữ: Roboto Bold hoặc Noto Sans Vietnamese.
  - Hiệu ứng: Chữ to nổi bật, nền viền đen (outline), vị trí căn giữa màn hình hoặc 1/3 dưới, hỗ trợ ký tự Tiếng Việt có dấu đầy đủ.
