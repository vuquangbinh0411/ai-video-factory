#!/usr/bin/env python3
"""
scripts/fetch_image.py
Nhiệm vụ: Nhận prompt mô tả cảnh, gọi API Pollinations.ai (FLUX engine) tải ảnh 9:16 (1080x1920) miễn phí 100%.
Hỗ trợ cả chế độ đơn lẻ và chế độ tạo hàng loạt (batch) cho toàn bộ kịch bản.
"""

import sys
import os
import json
import random
import time
import urllib.parse
import urllib.request
import subprocess
import argparse
import logging
from pathlib import Path

# Đảm bảo UTF-8 an toàn trên mọi hệ điều hành
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    import requests
except ImportError:
    requests = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from dotenv import load_dotenv
    ROOT_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    ROOT_DIR = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger("fetch_image")

TEMP_DIR = Path(os.getenv("SHARED_MEDIA_DIR", str(ROOT_DIR / "shared_media"))) / "temp"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
}

RESOLUTIONS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080)
}
DEFAULT_ASPECT = "9:16"
WIDTH, HEIGHT = RESOLUTIONS[DEFAULT_ASPECT]

def enhance_prompt(raw_prompt: str) -> str:
    """Bổ sung từ khóa tăng cường thẩm mỹ điện ảnh chân thực cho model FLUX"""
    enhancements = (
        "award-winning 35mm photo, shot on Hasselblad, dramatic cinematic lighting, "
        "hyperrealistic textures, volumetric atmosphere, sharp focus, 8k uhd, "
        "rich vibrant colors, high detail, masterpiece, clean image, no blur, no text, no watermark"
    )
    return f"{raw_prompt.strip()}, {enhancements}"

POLLINATIONS_KEY = os.getenv("POLLINATIONS_API_KEY", "")
IMAGE_ENGINE = os.getenv("IMAGE_ENGINE", "auto")

def generate_google_imagen_image(prompt: str, output_path: Path, aspect_ratio: str = "9:16", api_key: str = "") -> bool:
    """Tạo ảnh điện ảnh 4K chuẩn theo tỷ lệ khung hình bằng Google Imagen 3 (Mô hình cốt lõi của Google Flow)"""
    key = (
        api_key
        or os.getenv("GOOGLE_IMAGEN_API_KEY", "")
        or os.getenv("GEMINI_API_KEY", "")
        or os.getenv("CUSTOM_LLM_API_KEY", "")
    )
    if not key or len(key) < 10:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean_prompt = prompt.strip()
    valid_aspect = aspect_ratio if aspect_ratio in ["9:16", "16:9", "1:1"] else "9:16"

    # Thử các model Google Imagen 3 (:predict)
    models_to_try = ["imagen-3.0-generate-002", "imagen-3.0-generate-001", "imagen-3.0-fast-generate-001"]
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:predict?key={key}"
        payload = {
            "instances": [{"prompt": clean_prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": valid_aspect,
                "outputMimeType": "image/jpeg",
                "personGeneration": "ALLOW_ADULT"
            }
        }
        try:
            logger.info(f"Đang thử tạo ảnh với Google Imagen 3 ({model_name}, {valid_aspect})...")
            r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
            if r.status_code == 200:
                res_json = r.json()
                predictions = res_json.get("predictions", [])
                if predictions and "bytesBase64Encoded" in predictions[0]:
                    import base64
                    img_data = base64.b64decode(predictions[0]["bytesBase64Encoded"])
                    with open(output_path, "wb") as f:
                        f.write(img_data)
                    logger.info(f"🎉 TUYỆT VỜI! Đã tạo ảnh 4K bằng Google Imagen 3: {output_path} ({len(img_data)//1024} KB)")
                    return True
            elif r.status_code == 429:
                logger.warning(f"Google Imagen 3 {model_name} báo Quota 429 (Cần tài khoản Google Pro có billing).")
                break
        except Exception as e:
            logger.warning(f"Lỗi gọi Imagen 3 {model_name} ({e})")
            continue

    # Thử Google Multimodal Image Generation (Nano Banana - Gemini Image)
    gemini_image_models = ["gemini-2.5-flash-image", "gemini-3.1-flash-image", "gemini-3-pro-image"]
    for g_model in gemini_image_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={key}"
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"Generate a high-definition cinematic {valid_aspect} photo: {clean_prompt}"
                }]
            }]
        }
        try:
            logger.info(f"Đang thử tạo ảnh với Google Flow Engine ({g_model})...")
            r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=25)
            if r.status_code == 200:
                res_json = r.json()
                candidates = res_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        inline_data = part.get("inlineData", {})
                        if "data" in inline_data:
                            import base64
                            img_data = base64.b64decode(inline_data["data"])
                            with open(output_path, "wb") as f:
                                f.write(img_data)
                            logger.info(f"🎉 Thành công tạo ảnh điện ảnh Google {g_model}: {output_path} ({len(img_data)//1024} KB)")
                            return True
        except Exception:
            continue

    return False

def fetch_image_smart(prompt: str, output_path: Path, aspect_ratio: str = "9:16") -> bool:
    """
    Quy trình tạo ảnh thông minh theo thứ tự ưu tiên:
    1. Google Imagen 3 (Mô hình Google Flow chất lượng 4K đỉnh cao)
    2. Fallback sang Pollinations FLUX + Lanczos Upscale + Unsharp
    3. Fallback sang kho ảnh HD
    """
    # 1. Thử Google Imagen 3 trước tiên nếu có cấu hình hoặc auto
    if IMAGE_ENGINE in ("google_imagen", "auto"):
        if generate_google_imagen_image(prompt, output_path, aspect_ratio=aspect_ratio):
            return True

    # 2. Dự phòng Pollinations FLUX tăng cường độ nét
    return download_pollinations_image(prompt, output_path, aspect_ratio=aspect_ratio)

def create_fallback_graphic(prompt: str, output_path: Path, aspect_ratio: str = "9:16") -> bool:
    """Tải ảnh chụp phong cảnh / điện ảnh HD thực tế dự phòng nếu API AI bị 503 hoặc quá tải"""
    w, h = RESOLUTIONS.get(aspect_ratio, (1080, 1920))
    seed = random.randint(100, 99999)
    fallback_url = f"https://picsum.photos/seed/{seed}/{w}/{h}"
    logger.info(f"Đang tải ảnh HD {aspect_ratio} ({w}x{h}) dự phòng từ: {fallback_url}...")
    
    try:
        content_bytes = b""
        if requests:
            res = requests.get(fallback_url, headers=BROWSER_HEADERS, timeout=15)
            if res.status_code == 200 and len(res.content) > 10000:
                content_bytes = res.content
        else:
            req = urllib.request.Request(fallback_url, headers=BROWSER_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content_bytes = resp.read()

        if len(content_bytes) > 10000:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if Image:
                import io
                from PIL import ImageEnhance
                with Image.open(io.BytesIO(content_bytes)) as img:
                    img = img.convert("RGB")
                    if img.size[0] < w or img.size[1] < h:
                        img = img.resize((w, h), Image.Resampling.LANCZOS)
                    img = ImageEnhance.Sharpness(img).enhance(1.25)
                    img.save(output_path, "JPEG", quality=95, subsampling=0)
            else:
                with open(output_path, "wb") as f:
                    f.write(content_bytes)
            logger.info(f"Đã tải thành công ảnh chụp HD {w}x{h}: {output_path} ({output_path.stat().st_size // 1024} KB)")
            return True
    except Exception as e:
        logger.warning(f"Lỗi tải ảnh fallback từ picsum ({e}). Sẽ tạo ảnh gradient thẩm mỹ.")

    # Nếu không có mạng thì mới dùng FFmpeg tạo gradient nghệ thuật
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"gradients=s={w}x{h}:c0=0x1A2B4C:c1=0x3B1A4C:type=radial:d=1",
        "-frames:v", "1",
        str(output_path)
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        return True
    except:
        return False

def download_pollinations_image(prompt: str, output_path: Path, aspect_ratio: str = "9:16", max_retries: int = 3) -> bool:
    """Tải ảnh từ Pollinations AI (FLUX) với retry 3 lần, timeout 30s, negative prompt"""
    w, h = RESOLUTIONS.get(aspect_ratio, (1080, 1920))
    encoded_prompt = urllib.parse.quote(enhance_prompt(prompt))
    encoded_negative = urllib.parse.quote(
        "blurry, low quality, watermark, text, logo, ugly, deformed, noisy, "
        "jpeg artifacts, out of frame, cropped, bad anatomy, disfigured"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    key_param = f"&key={POLLINATIONS_KEY}" if POLLINATIONS_KEY else ""

    for attempt in range(1, max_retries + 1):
        seed = random.randint(1000, 999999)
        image_url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={w}&height={h}&model=flux&nologo=true"
            f"&seed={seed}&negative={encoded_negative}{key_param}"
        )

        logger.info(f"Lần thử {attempt}/{max_retries} - Đang tạo ảnh AI FLUX ({aspect_ratio} {w}x{h})...")
        try:
            content_bytes = b""
            if requests:
                response = requests.get(image_url, headers=BROWSER_HEADERS, timeout=30)
                if response.status_code == 200 and len(response.content) > 5000:
                    content_bytes = response.content
            else:
                req = urllib.request.Request(image_url, headers=BROWSER_HEADERS)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    content_bytes = resp.read()

            if len(content_bytes) > 5000:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if Image:
                    import io
                    from PIL import ImageEnhance
                    with Image.open(io.BytesIO(content_bytes)) as img:
                        img = img.convert("RGB")
                        # Nâng cấp độ phân giải lên đúng kích thước nếu ảnh nhỏ
                        if img.size[0] < w or img.size[1] < h:
                            img = img.resize((w, h), Image.Resampling.LANCZOS)
                        # Tăng cường độ nét kết cấu chi tiết và độ tương phản
                        img = ImageEnhance.Sharpness(img).enhance(1.35)
                        img = ImageEnhance.Contrast(img).enhance(1.05)
                        img.save(output_path, "JPEG", quality=95, subsampling=0)
                else:
                    with open(output_path, "wb") as f:
                        f.write(content_bytes)

                logger.info(f"✅ Tải & tăng độ nét AI FLUX thành công: {output_path} ({output_path.stat().st_size // 1024} KB)")
                return True
        except Exception as e:
            logger.warning(f"Lần thử {attempt} thất bại ({e}).")
            if attempt < max_retries:
                wait_time = attempt * 3
                logger.info(f"Đợi {wait_time}s rồi thử lại với seed mới...")
                time.sleep(wait_time)

    logger.warning("Đã hết lần thử Pollinations. Chuyển sang ảnh dự phòng HD...")
    return create_fallback_graphic(prompt, output_path, aspect_ratio=aspect_ratio)

def main():
    parser = argparse.ArgumentParser(description="Fetch cinematic image from Google Imagen 3 or Pollinations AI (0 dong)")
    parser.add_argument("--prompt", type=str, default="", help="Prompt đơn lẻ")
    parser.add_argument("--prompts-json", type=str, default="", help="Mảng JSON chứa danh sách các prompts")
    parser.add_argument("--aspect-ratio", type=str, choices=["9:16", "16:9", "1:1"], default="9:16", help="Tỷ lệ khung hình: 9:16 (dọc), 16:9 (ngang), 1:1 (vuông)")
    parser.add_argument("--output", type=str, default="", help="Đường dẫn file ảnh đầu ra (cho prompt đơn)")
    parser.add_argument("--output-dir", type=str, default="", help="Thư mục lưu ảnh cho batch prompts")
    args = parser.parse_args()

    saved_images = []

    # Xử lý trường hợp nhận mảng JSON nhiều prompts từ n8n
    if args.prompts_json:
        try:
            prompts = json.loads(args.prompts_json)
        except Exception as e:
            logger.error(f"Lỗi parse JSON prompts: {e}")
            sys.exit(1)

        out_dir = Path(args.output_dir) if args.output_dir else TEMP_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        for idx, p in enumerate(prompts, start=1):
            img_path = out_dir / f"scene_{idx:02d}.jpg"
            success = fetch_image_smart(p, img_path, aspect_ratio=args.aspect_ratio)
            if success:
                saved_images.append(str(img_path.resolve()))
            else:
                logger.error(f"Thất bại khi tải ảnh cảnh {idx}")
    else:
        # Xử lý prompt đơn
        prompt = args.prompt if args.prompt else "A futuristic city with flying neon vehicles in cyberpunk Vietnam night, cinematic hyperrealistic"
        out_path = Path(args.output) if args.output else (TEMP_DIR / "scene_01.jpg")
        success = fetch_image_smart(prompt, out_path, aspect_ratio=args.aspect_ratio)
        if success:
            saved_images.append(str(out_path.resolve()))

    if saved_images:
        res = {
            "status": "success",
            "count": len(saved_images),
            "images": saved_images
        }
        print(json.dumps(res, ensure_ascii=False))
    else:
        err = {"status": "error", "message": "Không thể tải bất kỳ hình ảnh nào từ Pollinations"}
        print(json.dumps(err, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
