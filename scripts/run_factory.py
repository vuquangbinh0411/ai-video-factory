#!/usr/bin/env python3
"""
scripts/run_factory.py
Tiện ích chạy toàn bộ quy trình AI Video Factory từ A-Z trên máy (CLI Runner)
Dùng để kiểm thử ngay lập tức hoặc chạy độc lập khi không mở n8n.
"""

import sys
import os
import json
import argparse
import logging
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_factory")

def main():
    parser = argparse.ArgumentParser(description="Chạy tự động toàn bộ luồng tạo Reels 0 đồng")
    parser.add_argument("--topic", type=str, default="", help="Chủ đề tùy chọn (bỏ trống để tự động cào tin tức mới nhất)")
    parser.add_argument("--duration", type=str, choices=["short", "medium", "long"], default="short", help="Thời lượng: short (30-45s), medium (60-90s), long (2-3 phút)")
    parser.add_argument("--aspect-ratio", type=str, choices=["9:16", "16:9", "1:1"], default="9:16", help="Tỷ lệ khung hình: 9:16 (dọc Reels/Shorts), 16:9 (ngang Youtube), 1:1 (vuông)")
    parser.add_argument("--engine", type=str, choices=["google_veo2", "google_imagen", "flux_hd"], default="google_veo2", help="Engine phân cảnh: google_veo2 (Góc quay điện ảnh), google_imagen (4K), flux_hd")
    parser.add_argument("--font-size", type=int, default=18, help="Cỡ chữ phụ đề (mặc định: 18)")
    parser.add_argument("--sub-position", type=str, choices=["bottom", "center", "top"], default="bottom", help="Vị trí phụ đề: bottom (đáy), center (giữa), top (đỉnh)")
    parser.add_argument("--output", type=str, default="", help="Đường dẫn file video đầu ra")
    args = parser.parse_args()

    python_exe = sys.executable
    scripts_dir = ROOT_DIR / "scripts"
    temp_dir = ROOT_DIR / "shared_media" / "temp"
    outputs_dir = ROOT_DIR / "shared_media" / "outputs"
    temp_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    final_output = Path(args.output) if args.output else (outputs_dir / "final_reel.mp4")

    # Cấu hình thời lượng
    if args.duration == "long":
        duration_label = "Phim ngắn / Deep-Dive (2 - 3 phút)"
        req_duration_text = "kịch bản chuyên sâu dài 2 - 3 phút (~2200 - 2800 ký tự tiếng Việt, chia làm 14 - 16 phân cảnh liên tục phát triển kịch tính, mỗi cảnh 10-12 giây)"
        default_num_scenes = 14
        music_duration = 200
    elif args.duration == "medium":
        duration_label = "Reels Tiêu chuẩn (60 - 90 giây)"
        req_duration_text = "kịch bản hoàn chỉnh 60 - 90 giây (~1200 - 1500 ký tự tiếng Việt, gồm hook mở đầu gây sốc, 4 luận điểm bất ngờ và kết luận mạnh, chia làm 10 phân cảnh chuyển nhanh)"
        default_num_scenes = 10
        music_duration = 110
    else:
        duration_label = "Short Reels (30 - 45 giây)"
        req_duration_text = "kịch bản ngắn gọn 30 - 45 giây (~600 - 750 ký tự tiếng Việt, chia làm 7 phân cảnh chuyển nhanh liên tục mỗi cảnh 4-6 giây)"
        default_num_scenes = 7
        music_duration = 60

    print("\n" + "="*60)
    print("🎬 AI VIDEO FACTORY - BẮT ĐẦU QUY TRÌNH SẢN XUẤT TỰ ĐỘNG")
    print(f"⏱️  Định dạng: {duration_label} (Mục tiêu: {default_num_scenes} phân cảnh storyboard)")
    print("="*60 + "\n")

    # BƯỚC 1: Nghiên cứu xu hướng
    print("🔍 [1/5] Đang nghiên cứu bối cảnh tin tức xu hướng...")
    cmd_research = [python_exe, str(scripts_dir / "research_agent.py")]
    if args.topic:
        cmd_research.extend(["--topic", args.topic])
    res_research = subprocess.run(cmd_research, stdout=subprocess.PIPE, encoding="utf-8", check=True)
    research_data = json.loads(res_research.stdout.strip())
    topic = research_data.get("topic", "Khám phá khoa học")
    context = research_data.get("context", "")
    print(f"   -> Chủ đề: {topic}")

    # BƯỚC 2: Sinh kịch bản (Hỗ trợ Google Gemini API 0đ & Custom LLMs)
    print("\n✍️  [2/5] Đang tạo kịch bản viral Reels...")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    llm_key = os.getenv("CUSTOM_LLM_API_KEY", "") or gemini_key
    llm_url = os.getenv("CUSTOM_LLM_API_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
    llm_model = os.getenv("CUSTOM_LLM_MODEL_NAME", "gemini-1.5-flash")

    # Nếu dùng Gemini key nhưng URL chưa đặt
    if gemini_key and "googleapis.com" not in llm_url:
        llm_url = "https://generativelanguage.googleapis.com/v1beta/openai"

    script_text = ""
    image_prompts = []
    caption = ""

    if llm_key:
        try:
            import requests
            headers = {"Authorization": f"Bearer {llm_key}", "Content-Type": "application/json"}
            system_prompt = (
                "Bạn là đạo diễn kịch bản video triệu view chuyên nghiệp. "
                "Nhiệm vụ: Viết kịch bản video VIRAL và tạo danh sách phân cảnh hình ảnh CHẤT LƯỢNG ĐIỆN ẢNH.\n\n"
                "QUY TẮC QUAN TRỌNG cho image_prompt:\n"
                "1. PHẢI viết bằng tiếng Anh chi tiết (40-60 từ mỗi prompt)\n"
                "2. Mỗi prompt PHẢI bao gồm: chủ thể chính, hành động cụ thể, bối cảnh chi tiết, "
                "góc máy (aerial/close-up/wide/low angle/bird eye), "
                "ánh sáng (golden hour/neon glow/dramatic rim light/volumetric fog), "
                "bảng màu (teal-orange/moody blue/warm golden/cyberpunk neon)\n"
                "3. Kết thúc MỌI prompt bằng master_style để đảm bảo NHẤT QUÁN thị giác xuyên suốt\n"
                "4. KHÔNG dùng prompt chung chung kiểu 'futuristic city'. Phải có composition cụ thể và khác biệt mỗi cảnh\n"
                "5. Mỗi cảnh phải có góc máy KHÁC NHAU (xen kẽ close-up, wide, aerial, low angle)\n\n"
                "BẮT BUỘC trả về JSON hợp lệ:\n"
                "{\n"
                '  "hook": "Câu mở đầu giữ chân 3 giây đầu - cực kỳ giật gân gây tò mò",\n'
                '  "master_style": "cinematic 8k uhd, photorealistic, shallow depth of field, dramatic volumetric lighting, vertical portrait 9:16",\n'
                '  "script_text": "Toàn bộ lời thoại tiếng Việt tự nhiên cuốn hút, không viết tắt",\n'
                '  "scenes": [\n'
                '    {"scene_id": 1, "image_prompt": "Close-up shot of [subject] with [action], [environment], golden hour rim lighting, teal and orange color grade, [master_style]"},\n'
                '    {"scene_id": 2, "image_prompt": "Wide aerial view of [subject] in [location], dramatic storm clouds, volumetric god rays, moody blue atmosphere, [master_style]"}\n'
                '  ],\n'
                '  "image_prompts": ["detailed english prompt 1", "detailed english prompt 2"],\n'
                '  "fb_caption": "Tiêu đề Reels hấp dẫn + Hashtags viral"\n'
                "}"
            )
            full_prompt = f"{system_prompt}\n\nChủ đề: {topic}\nBối cảnh: {context}\nYêu cầu: Hãy viết {req_duration_text}. Trả về đúng định dạng JSON."
            
            if "googleapis.com" in llm_url or llm_key.startswith("AQ."):
                candidates = [llm_model, "gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3-flash-preview"]
                content = ""
                for c_model in candidates:
                    if not c_model: continue
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{c_model}:generateContent?key={llm_key}"
                    try:
                        r = requests.post(url, json={"contents": [{"parts": [{"text": full_prompt}]}]}, timeout=25)
                        if r.status_code == 200:
                            content = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                            llm_model = c_model
                            break
                    except Exception:
                        continue

                if not content:
                    raise RuntimeError(f"Không thể kết nối Gemini ({candidates})")

                if content.startswith("```json"): content = content[7:-3].strip()
                elif content.startswith("```"): content = content[3:-3].strip()
            else:
                endpoint = f"{llm_url.rstrip('/')}/chat/completions"
                payload = {
                    "model": llm_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": full_prompt}
                    ],
                    "response_format": {"type": "json_object"}
                }
                res = requests.post(endpoint, headers=headers, json=payload, timeout=30)
                res.raise_for_status()
                content = res.json()["choices"][0]["message"]["content"]
                if content.startswith("```json"): content = content[7:-3].strip()
                elif content.startswith("```"): content = content[3:-3].strip()

            parsed = json.loads(content)
            script_text = parsed.get("script_text", "")
            scenes_list = parsed.get("scenes", [])
            if scenes_list and isinstance(scenes_list, list):
                image_prompts = [s.get("image_prompt", "") for s in scenes_list if isinstance(s, dict) and s.get("image_prompt")]
            if not image_prompts:
                image_prompts = parsed.get("image_prompts", [])
            caption = parsed.get("fb_caption", "")
            print(f"   -> [Gemini/LLM] Đã sinh kịch bản thành công bằng model: {llm_model} ({len(image_prompts)} phân cảnh)")
        except Exception as e:
            logger.warning(f"Không thể kết nối LLM/Gemini ({e}). Sử dụng mẫu kịch bản chuẩn.")

    if not script_text:
        script_text = (
            f"Bạn có tin không? {topic} đang tạo nên một cơn sốt chấn động trong giới công nghệ và khoa học! "
            f"Các chuyên gia hàng đầu vừa phát hiện ra những bí ẩn chưa từng được tiết lộ, mở ra một bước ngoặt hoàn toàn mới. "
            f"Điều này không chỉ thay đổi cách thế giới vận hành, mà còn tác động trực tiếp đến tương lai của mỗi chúng ta chỉ trong vài năm tới. "
            f"Hãy tưởng tượng mọi giới hạn công nghệ trước đây đều bị phá vỡ trong chớp mắt! "
            f"Bạn nghĩ sao về bước ngoặt lịch sử này? Hãy để lại ý kiến dưới phần bình luận và bấm Follow kênh ngay để không bỏ lỡ những bí mật tiếp theo!"
        )
        master = "cinematic 8k uhd, photorealistic, dramatic volumetric lighting, shallow depth of field, vertical 9:16"
        image_prompts = [
            f"Extreme close-up of a scientist eye reflecting holographic data about {topic}, neon blue light, dark lab background, {master}",
            f"Wide aerial drone shot of massive futuristic research facility studying {topic}, golden hour sunset, warm orange tones, {master}",
            f"Dramatic low angle shot of advanced quantum computer processing {topic} data, teal and orange color grade, glowing cables, {master}",
            f"Close-up of glowing neural network visualization connected to {topic}, dark background with floating particle effects, {master}",
            f"Epic wide panoramic shot of futuristic cityscape transformed by {topic} technology, volumetric god rays through clouds, {master}",
            f"Intimate portrait of diverse team of researchers celebrating {topic} breakthrough, warm golden rim lighting, bokeh, {master}",
            f"Abstract macro shot of microscopic details related to {topic}, bioluminescent cyan and magenta colors, creamy bokeh, {master}",
        ]
        caption = f"🔥 {topic} - Bí ẩn tương lai! #reels #khoahoc #congnghe #viral #xuhuong"

    print(f"   -> Lời thoại (~35s): {script_text[:80]}...")

    # BƯỚC 3: Sinh giọng đọc (TTS) & phụ đề SRT
    print("\n🎙️  [3/5] Đang sinh giọng đọc tiếng Việt (Edge-TTS) & phụ đề đồng bộ...")
    voice_file = temp_dir / "voiceover.mp3"
    sub_file = temp_dir / "subtitles.srt"
    cmd_tts = [
        python_exe, str(scripts_dir / "generate_tts.py"),
        "--text", script_text,
        "--output", str(voice_file),
        "--output-sub", str(sub_file)
    ]
    subprocess.run(cmd_tts, check=True)
    print("   -> Đã tạo giọng đọc & phụ đề SRT thành công.")

    # BƯỚC 4: Sinh nhạc nền & Tải hình ảnh HD 9:16 (Phân cảnh đồng bộ)
    prompts_to_use = [p for p in image_prompts if p]
    if len(prompts_to_use) < default_num_scenes:
        master_tag = "cinematic 8k, photorealistic vertical 9:16, dramatic lighting"
        for k in range(len(prompts_to_use) + 1, default_num_scenes + 1):
            prompts_to_use.append(f"Scene {k} of {topic}, {master_tag}")

    num_scenes = len(prompts_to_use)
    print(f"\n🎵  [4/5] Đang tạo nhạc nền & tải {num_scenes} phân cảnh hình ảnh HD 9:16...")
    music_file = temp_dir / "background_music.mp3"
    cmd_music = [
        python_exe, str(scripts_dir / "generate_music.py"),
        "--duration", str(music_duration),
        "--output", str(music_file)
    ]
    subprocess.run(cmd_music, check=True)

    img_files = []
    for i, p in enumerate(prompts_to_use, start=1):
        if args.engine == "google_veo2":
            scene_file = temp_dir / f"scene_{i:02d}.mp4"
            print(f"   -> [Google Veo 2] Đang tạo phân cảnh video {i}/{num_scenes} ({args.aspect_ratio})...")
            cmd_scene = [
                python_exe, str(scripts_dir / "fetch_veo.py"),
                "--prompt", p,
                "--aspect-ratio", args.aspect_ratio,
                "--duration", "5.0",
                "--scene-idx", str(i),
                "--output", str(scene_file)
            ]
        else:
            scene_file = temp_dir / f"scene_{i:02d}.jpg"
            print(f"   -> Đang chuẩn bị ảnh phân cảnh {i}/{num_scenes}...")
            cmd_scene = [
                python_exe, str(scripts_dir / "fetch_image.py"),
                "--prompt", p,
                "--aspect-ratio", args.aspect_ratio,
                "--output", str(scene_file)
            ]
        subprocess.run(cmd_scene, check=True)
        if scene_file.exists():
            img_files.append(scene_file)

    # BƯỚC 5: Ghép video hoàn chỉnh bằng FFmpeg
    print(f"\n🎞️  [5/5] Đang render video {len(img_files)} phân cảnh ({args.aspect_ratio}) Engine {args.engine}...")
    cmd_render = [
        python_exe, str(scripts_dir / "render_video.py"),
        "--images", *[str(f) for f in img_files],
        "--voice", str(voice_file),
        "--music", str(music_file),
        "--sub", str(sub_file),
        "--aspect-ratio", args.aspect_ratio,
        "--font-size", str(args.font_size),
        "--sub-position", args.sub_position,
        "--output", str(final_output)
    ]
    subprocess.run(cmd_render, check=True)

    print("\n" + "="*60)
    print("🎉 SẢN XUẤT THÀNH CÔNG!")
    print(f"📍 Video thành phẩm: {final_output.resolve()}")
    print(f"📝 Caption đề xuất:\n{caption}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
