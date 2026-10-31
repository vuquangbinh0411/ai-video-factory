#!/usr/bin/env python3
"""
scripts/web_ui.py
Giao diện người dùng Web trực quan (AI Video Factory Studio Pro)
Tích hợp 2 Phòng Chức Năng:
1. 🏭 Xưởng AI Tự Động (AI Factory): Cào tin tức, kịch bản viral, đa mô hình (Veo 2, Imagen 3, Flux), render 1-click.
2. ✂️ Phòng Dựng Hậu Kỳ (Post-Production Studio): Timeline Subtitle Editor theo phong cách Google Flow / CapCut + Audio & Music Remixer.
"""

import sys
import os
import json
import time
import shutil
import threading
import subprocess
import urllib.parse
from pathlib import Path
import logging
logger = logging.getLogger("web_ui")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

import webbrowser
import requests
import base64
import re

# Đảm bảo UTF-8 an toàn
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from dotenv import load_dotenv, set_key
load_dotenv(ROOT_DIR / ".env")

PORT = 7860
CONFIG_FILE = ROOT_DIR / "providers_config.json"

DEFAULT_PROVIDERS = {
    "active_provider": "oxion",
    "providers": {
        "oxion": {
            "name": "Oxion AI",
            "icon": "fa-bolt",
            "color": "from-cyan-500 to-blue-600",
            "base_url": "https://oxionai.com/v1",
            "api_key": "",
            "selected_model": "gemini-3.7-flash",
            "models": ["gemini-3.7-flash", "deepseek-v4-flash-0731", "deepseek-v4-pro-max", "claude-sonnet-5", "claude-opus-4.8", "gpt-5.5", "grok-4.5"],
            "description": "Nền tảng Oxion AI (hỗ trợ nhiều model Claude, DeepSeek, GPT, Gemini)"
        },
        "gemini": {
            "name": "Google Gemini (0 đồng)",
            "icon": "fa-wand-magic-sparkles",
            "color": "from-indigo-500 to-purple-600",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "api_key": "",
            "selected_model": "gemini-2.0-flash",
            "models": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-2.5-pro"],
            "description": "Google AI Studio chính hãng (Miễn phí 1.500 lượt/ngày)"
        },
        "deepseek": {
            "name": "DeepSeek API",
            "icon": "fa-brain",
            "color": "from-blue-600 to-indigo-700",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "",
            "selected_model": "deepseek-chat",
            "models": ["deepseek-chat", "deepseek-reasoner"],
            "description": "DeepSeek V3 / R1 chính hãng (siêu thông minh, chi phí cực rẻ)"
        },
        "groq": {
            "name": "Groq Cloud (0 đồng)",
            "icon": "fa-forward-fast",
            "color": "from-orange-500 to-amber-600",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key": "",
            "selected_model": "llama-3.3-70b-versatile",
            "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
            "description": "Tốc độ xử lý LPU nhanh nhất thế giới (500 từ/giây, miễn phí)"
        },
        "openrouter": {
            "name": "OpenRouter",
            "icon": "fa-network-wired",
            "color": "from-emerald-500 to-teal-600",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "",
            "selected_model": "google/gemini-2.0-flash-exp:free",
            "models": ["google/gemini-2.0-flash-exp:free", "meta-llama/llama-3.3-70b-instruct:free", "anthropic/claude-3.5-sonnet"],
            "description": "Cổng kết nối hơn 100+ mô hình AI toàn cầu (có model free)"
        },
        "openai": {
            "name": "OpenAI",
            "icon": "fa-circle-notch",
            "color": "from-green-600 to-emerald-700",
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "selected_model": "gpt-4o-mini",
            "models": ["gpt-4o-mini", "gpt-4o"],
            "description": "OpenAI chính hãng (GPT-4o, GPT-4o-mini)"
        },
        "local": {
            "name": "Local LLM (Ollama / vLLM / LM Studio)",
            "icon": "fa-server",
            "color": "from-purple-600 to-pink-600",
            "base_url": "http://localhost:11434/v1",
            "api_key": "ollama",
            "selected_model": "qwen2.5:7b",
            "models": ["qwen2.5:7b", "llama3.2:3b", "deepseek-r1:7b", "mistral:7b"],
            "description": "Chạy mô hình offline trên máy tính (hoàn toàn miễn phí, riêng tư 100%)"
        }
    }
}

def load_providers_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return DEFAULT_PROVIDERS

def save_providers_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

def check_system_status():
    status = {"ffmpeg": False, "python": sys.version.split()[0], "shared_media": False, "active_provider": "Chưa chọn", "active_model": ""}
    try:
        r = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        status["ffmpeg"] = (r.returncode == 0)
    except Exception:
        pass
    sm = ROOT_DIR / "shared_media"
    status["shared_media"] = sm.exists() and (sm / "temp").exists() and (sm / "outputs").exists()
    cfg = load_providers_config()
    ap_id = cfg.get("active_provider", "oxion")
    pinfo = cfg.get("providers", {}).get(ap_id, {})
    status["active_provider"] = pinfo.get("name", ap_id)
    status["active_model"] = pinfo.get("selected_model", "")
    return status

# === BỘ PARSER VÀ CONVERTER PHỤ ĐỀ TIMELINE (CHO TAB HẬU KỲ) ===
def parse_srt_to_segments(srt_text: str):
    """Chuyển đổi chuỗi SRT thành danh sách thẻ segment trực quan"""
    if not srt_text:
        return []
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    segments = []
    for b in blocks:
        lines = [l.strip() for l in b.strip().split('\n') if l.strip()]
        if len(lines) >= 2:
            time_line = lines[1] if lines[0].isdigit() else lines[0]
            text_lines = lines[2:] if lines[0].isdigit() else lines[1:]
            m = re.search(r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})', time_line)
            if m:
                s_str, e_str = m.groups()
                def to_sec(t):
                    t = t.replace(',', '.')
                    parts = t.split(':')
                    return round(int(parts[0])*3600 + int(parts[1])*60 + float(parts[2]), 2)
                start_sec = to_sec(s_str)
                end_sec = to_sec(e_str)
                text = "\n".join(text_lines)
                segments.append({
                    "id": len(segments) + 1,
                    "sceneNum": len(segments) + 1,
                    "start": start_sec,
                    "end": end_sec,
                    "start_display": f"{start_sec:.2f}",
                    "end_display": f"{end_sec:.2f}",
                    "text": text
                })
    return segments

def segments_to_srt(segments: list):
    """Chuyển đổi danh sách thẻ segments thành định dạng SRT chuẩn"""
    def to_srt_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int(round((sec - int(sec)) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    out = []
    for i, seg in enumerate(segments, 1):
        try:
            st = float(seg.get("start", 0))
            et = float(seg.get("end", st + 1.5))
        except Exception:
            st, et = 0.0, 1.5
        txt = str(seg.get("text", "")).strip()
        out.append(f"{i}\n{to_srt_time(st)} --> {to_srt_time(et)}\n{txt}\n")
    return "\n".join(out)

GLOBAL_STATE = {
    "is_running": False,
    "step": 0,
    "step_name": "",
    "progress": 0,
    "logs": [],
    "result": None,
    "error": None
}

ACTIVE_SUBPROCESSES = []

def run_tracked_cmd(cmd, **kwargs):
    proc = subprocess.Popen(cmd, **kwargs)
    ACTIVE_SUBPROCESSES.append(proc)
    try:
        proc.wait()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)
        return proc
    finally:
        if proc in ACTIVE_SUBPROCESSES:
            ACTIVE_SUBPROCESSES.remove(proc)

def kill_all_subprocesses():
    for proc in list(ACTIVE_SUBPROCESSES):
        try:
            proc.terminate()
            proc.kill()
        except Exception:
            pass
    ACTIVE_SUBPROCESSES.clear()
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/F", "/IM", "ffmpeg.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

def get_media_duration_safe(f_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(f_path)]
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return max(0.5, float(r.stdout.strip()))
    except Exception:
        return 5.0

def build_aligned_voiceover(segments, seg_audios, temp_dir, voice_file):
    """
    Tạo voiceover.mp3 khớp chuẩn theo từng phân đoạn, TUYỆT ĐỐI KHÔNG BỊ ĐÈ TIẾNG.
    - Mỗi đoạn thoại được co giãn nhịp điệu (atempo) hoặc cắt/pad vừa khít với thời lượng của cảnh (end - start).
    - Các đoạn được xếp nối tiếp nhau bằng concat audio nên 100% KHÔNG THỂ có hiện tượng 2 giọng nói cùng lúc.
    """
    padded_clips = []
    for i, (seg, s_audio) in enumerate(seg_audios):
        s_t = float(seg.get("start", 0.0))
        e_t = float(seg.get("end", s_t + 2.0))
        slot_dur = max(0.5, e_t - s_t)
        clip_out = temp_dir / f"aligned_seg_{i+1}.mp3"

        if s_audio and s_audio.exists() and s_audio.stat().st_size > 0:
            a_dur = get_media_duration_safe(s_audio)
            if a_dur > slot_dur:
                # Nếu giọng đọc dài hơn thời lượng cảnh: Tăng tốc độ đọc tự nhiên (atempo) để nói trọn vẹn câu
                speed = min(1.4, max(1.0, a_dur / (slot_dur - 0.05)))
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(s_audio),
                    "-filter:a", f"atempo={speed:.2f}",
                    "-t", str(slot_dur),
                    str(clip_out)
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                # Nếu giọng đọc ngắn hơn: Đệm khoảng lặng vào đuôi (apad) cho vừa khít cảnh
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(s_audio),
                    "-af", f"apad=whole_dur={slot_dur}",
                    "-t", str(slot_dur),
                    str(clip_out)
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Tạo đoạn im lặng chuẩn
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(slot_dur),
                str(clip_out)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        padded_clips.append(clip_out)

    if padded_clips:
        c_inputs = []
        for p_c in padded_clips:
            c_inputs.extend(["-i", str(p_c)])
        c_filter = f"concat=n={len(padded_clips)}:v=0:a=1[aout]"
        subprocess.run(["ffmpeg", "-y"] + c_inputs + ["-filter_complex", c_filter, "-map", "[aout]", "-c:a", "libmp3lame", "-b:a", "192k", str(voice_file)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "5", str(voice_file)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def generate_viral_script_ai(topic: str, context: str, duration_mode: str, req_duration_text: str, default_num_scenes: int, llm_key: str, llm_url: str, llm_model: str):
    system_prompt = (
        "Bạn là Chuyên Gia Biên Kịch & Đạo Diễn Điện Ảnh hàng đầu thế giới chuyên sáng tạo video cho Google Veo 2 / Google Flow.\n"
        "Nhiệm vụ của bạn:\n"
        "1. KỊCH BẢN TIẾNG VIỆT (script_text): Viết lời dẫn tiếng Việt viral cực kỳ cuốn hút, giữ chân người xem 100% thời lượng. Tuyệt đối không chào hỏi sáo rỗng. Đi thẳng vào vấn đề bằng một cú hook gây tò mò trong 3 giây đầu.\n"
        "2. PHÂN CẢNH VEO 2 ĐIỆN ẢNH (scenes):\n"
        "   - Mỗi cảnh BẮT BUỘC PHẢI THAY ĐỔI ĐA DẠNG VÀ PHÙ HỢP 100% VỚI NỘI DUNG CHỦ ĐỀ, TUYỆT ĐỐI KHÔNG lặp lại khuôn mẫu viễn tưởng (corporate research, server vault) nếu chủ đề là đời sống, gia đình, ẩm thực, tình cảm, thể thao!\n"
        "   - LỜI THOẠI PHÂN CẢNH (narration): Lời bình tiếng Việt ngắn gọn, súc tích (10 đến 18 từ), đánh trúng cảm xúc, cô đọng vừa vặn trên 1-2 dòng phụ đề, TUYỆT ĐỐI KHÔNG viết quá dài làm tràn màn hình video dọc 9:16.\n"
        "   - 'veo_prompt' là một câu tiếng Anh hoàn chỉnh (50-80 từ) mô tả cụ thể: [Góc máy & chuyển động phù hợp bối cảnh], [Nhân vật & hành động, cảm xúc chân thực], [Ánh sáng & không gian bối cảnh], [Phong cách điện ảnh 35mm, photorealistic, 8k].\n"
        "Trả về định dạng JSON thuần túy có cấu trúc:\n"
        "{\n"
        '  "script_text": "Toàn bộ kịch bản lời đọc tiếng Việt (kết hợp mạch lạc các câu narration)",\n'
        '  "scenes": [\n'
        '    {\n'
        '      "scene_num": 1,\n'
        '      "camera": "Tên góc máy tiếng Anh ngắn gọn",\n'
        '      "narration": "Lời bình tiếng Việt ngắn gọn, súc tích 10-18 từ, vừa vặn khung hình",\n'
        '      "veo_prompt": "Prompt tiếng Anh điện ảnh chi tiết hoàn chỉnh cho Google Veo 2"\n'
        '    }\n'
        '  ],\n'
        '  "fb_caption": "Tiêu đề & hashtag viral"\n'
        "}"
    )
    full_prompt = (
        f"CHỦ ĐỀ BẮT BUỘC: \"{topic}\"\n"
        f"Thông tin bối cảnh chi tiết:\n{context if context else f'Khai thác sâu sắc, chân thực và kịch tính về chủ đề: {topic}'}\n"
        f"Yêu cầu thời lượng: {req_duration_text}\n"
        f"Số phân cảnh cần tạo: {default_num_scenes}\n"
        f"LƯU Ý ĐẶC BIỆT: Toàn bộ {default_num_scenes} phân cảnh và câu thoại BẮT BUỘC PHẢI KHẮC HỌA ĐÚNG CHỦ ĐỀ \"{topic}\", tuyệt đối không được chuyển đề tài."
    )

    script_text = ""
    scenes_result = []
    image_prompts = []
    caption = ""

    if llm_key:
        key_pool = [k.strip() for k in llm_key.replace("\n", ",").split(",") if k.strip()]
        for k_idx, active_key in enumerate(key_pool):
            try:
                if "googleapis.com" in llm_url or active_key.startswith("AQ.") or active_key.startswith("AIza"):
                    candidates = [llm_model, "gemini-3.1-flash-lite", "gemini-2.5-pro", "gemini-3.5-flash"]
                    for candidate in candidates:
                        if not candidate: continue
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent?key={active_key}"
                        payload = {
                            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{full_prompt}"}]}],
                            "generationConfig": {"temperature": 0.8, "response_mime_type": "application/json"}
                        }
                        r = requests.post(url, json=payload, timeout=30)
                        if r.status_code == 200:
                            data = r.json()
                            content = data["candidates"][0]["content"]["parts"][0]["text"]
                            parsed = json.loads(content)
                            script_text = parsed.get("script_text", "")
                            scenes_raw = parsed.get("scenes", [])
                            for s in scenes_raw:
                                p_text = s.get("veo_prompt") or s.get("image_prompt", "")
                                if p_text:
                                    image_prompts.append(p_text)
                                    scenes_result.append({
                                        "scene_num": s.get("scene_num", len(scenes_result) + 1),
                                        "camera": s.get("camera", "Cinematic shot"),
                                        "narration": s.get("narration", ""),
                                        "veo_prompt": p_text
                                    })
                            caption = parsed.get("fb_caption", "")
                            logger.info(f"[KEY ROTATION] ✅ Key {k_idx+1} gọi thành công kịch bản điện ảnh ({candidate})")
                            break
                        elif r.status_code == 429:
                            logger.warning(f"[KEY ROTATION] ⚠️ Key {k_idx+1} bị lỗi Quota 429. Chuyển sang key tiếp theo...")
                            break
                    if script_text:
                        break
                else:
                    headers = {"Authorization": f"Bearer {active_key}", "Content-Type": "application/json"}
                    payload = {
                        "model": llm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": full_prompt}
                        ],
                        "response_format": {"type": "json_object"}
                    }
                    r = requests.post(f"{llm_url}/chat/completions", headers=headers, json=payload, timeout=30)
                    if r.status_code == 200:
                        parsed = r.json()["choices"][0]["message"]["content"]
                        parsed_json = json.loads(parsed)
                        script_text = parsed_json.get("script_text", "")
                        scenes_raw = parsed_json.get("scenes", [])
                        for s in scenes_raw:
                            p_text = s.get("veo_prompt") or s.get("image_prompt", "")
                            if p_text:
                                image_prompts.append(p_text)
                                scenes_result.append({
                                    "scene_num": s.get("scene_num", len(scenes_result) + 1),
                                    "camera": s.get("camera", "Cinematic shot"),
                                    "narration": s.get("narration", ""),
                                    "veo_prompt": p_text
                                })
                        caption = parsed_json.get("fb_caption", "")
                        break
            except Exception as e:
                logger.error(f"[KEY ROTATION] Lỗi key {k_idx+1}: {e}")

    return script_text, scenes_result, image_prompts, caption



def run_pipeline_thread(topic: str, custom_script: str, voice: str, duration_mode: str = "short", font_size: int = 18, aspect_ratio: str = "9:16", engine: str = "google_veo2", sub_position: str = "bottom"):
    global GLOBAL_STATE
    GLOBAL_STATE["is_running"] = True
    GLOBAL_STATE["step"] = 0
    GLOBAL_STATE["progress"] = 5
    GLOBAL_STATE["logs"] = []
    GLOBAL_STATE["result"] = None
    GLOBAL_STATE["error"] = None

    python_exe = sys.executable
    scripts_dir = ROOT_DIR / "scripts"
    temp_dir = ROOT_DIR / "shared_media" / "temp"
    outputs_dir = ROOT_DIR / "shared_media" / "outputs"
    temp_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    final_output = outputs_dir / "final_reel.mp4"

    def log(msg):
        GLOBAL_STATE["logs"].append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    try:
        if duration_mode == "long":
            duration_label = "Phim ngắn (2 - 3 phút)"
            req_duration_text = "kịch bản chuyên sâu dài 2 - 3 phút (~2200 - 2800 ký tự tiếng Việt, chia làm 14 phân cảnh)"
            default_num_scenes = 14
            music_duration = 200
        elif duration_mode == "medium":
            duration_label = "Reels Tiêu chuẩn (60 - 90 giây)"
            req_duration_text = "kịch bản hoàn chỉnh 60 - 90 giây (~1200 - 1500 ký tự tiếng Việt, chia làm 10 phân cảnh)"
            default_num_scenes = 10
            music_duration = 110
        else:
            duration_label = "Short Reels (30 - 45 giây)"
            req_duration_text = "kịch bản ngắn gọn 30 - 45 giây (~600 - 750 ký tự tiếng Việt, chia làm 7 phân cảnh)"
            default_num_scenes = 7
            music_duration = 60

        log(f"🎬 Bắt đầu sản xuất: {duration_label} • Tỷ lệ: {aspect_ratio} • Engine: {engine} • Vị trí Sub: {sub_position}")

        # Bước 1: Nghiên cứu xu hướng
        GLOBAL_STATE["step"] = 1
        GLOBAL_STATE["step_name"] = "Nghiên cứu tin tức xu hướng..."
        GLOBAL_STATE["progress"] = 15
        cmd_research = [python_exe, str(scripts_dir / "research_agent.py")]
        if topic:
            cmd_research.extend(["--topic", topic])
        res_res = subprocess.run(cmd_research, stdout=subprocess.PIPE, encoding="utf-8", check=True)
        res_data = json.loads(res_res.stdout.strip())
        chosen_topic = res_data.get("topic", "Công nghệ tương lai")
        chosen_context = res_data.get("context", "")
        log(f"Đã chọn chủ đề: {chosen_topic}")

        # Bước 2: Kịch bản AI
        GLOBAL_STATE["step"] = 2
        GLOBAL_STATE["step_name"] = f"Đạo diễn kịch bản ({default_num_scenes} phân cảnh)..."
        GLOBAL_STATE["progress"] = 35
        load_dotenv(ROOT_DIR / ".env")
        llm_key = os.getenv("CUSTOM_LLM_API_KEY", "")
        llm_url = os.getenv("CUSTOM_LLM_API_URL", "https://generativelanguage.googleapis.com/v1beta")
        llm_model = os.getenv("CUSTOM_LLM_MODEL_NAME", "gemini-3.1-flash-lite")

        script_text = custom_script.strip()
        image_prompts = []
        caption = ""
        if not script_text:
            log(f"Đang sinh kịch bản viral cuốn hút với AI ({llm_model})...")
            script_text, _, image_prompts, caption = generate_viral_script_ai(
                topic=chosen_topic, context=chosen_context, duration_mode=duration_mode,
                req_duration_text=req_duration_text, default_num_scenes=default_num_scenes,
                llm_key=llm_key, llm_url=llm_url, llm_model=llm_model
            )
        else:
            log(f"Sử dụng kịch bản tùy chỉnh của bạn ({len(script_text)} ký tự).")

        # Bước 3: Giọng đọc TTS & Phụ đề ngắn gọn
        GLOBAL_STATE["step"] = 3
        GLOBAL_STATE["step_name"] = "Sinh giọng đọc & Phụ đề Short-Cue..."
        GLOBAL_STATE["progress"] = 50
        voice_file = temp_dir / "voiceover.mp3"
        sub_file = temp_dir / "subtitles.srt"
        cmd_tts = [
            python_exe, str(scripts_dir / "generate_tts.py"),
            "--text", script_text, "--voice", voice,
            "--output", str(voice_file), "--output-sub", str(sub_file)
        ]
        run_tracked_cmd(cmd_tts)
        log("Đã tạo giọng đọc tiếng Việt và chia nhỏ cụm từ phụ đề nhịp điệu!")

        # Bước 4: Nhạc nền & Hình ảnh / Video clips
        GLOBAL_STATE["step"] = 4
        GLOBAL_STATE["step_name"] = f"Tạo nhạc nền & Phân cảnh ({engine})..."
        GLOBAL_STATE["progress"] = 65
        music_file = temp_dir / "background_music.mp3"
        cmd_music = [python_exe, str(scripts_dir / "generate_music.py"), "--duration", str(music_duration), "--genre", "ambient", "--output", str(music_file)]
        run_tracked_cmd(cmd_music)

        prompts_to_use = [p for p in image_prompts if p]
        if len(prompts_to_use) < default_num_scenes:
            master_tag = "award-winning 35mm photo, shot on Hasselblad, dramatic cinematic lighting, hyperrealistic textures, vertical 9:16"
            while len(prompts_to_use) < default_num_scenes:
                idx = len(prompts_to_use) + 1
                prompts_to_use.append(f"Cinematic scene {idx} about {chosen_topic}, stunning composition, volumetric lighting, {master_tag}")

        image_files = []
        if engine == "google_veo2":
            log("Kích hoạt Google Veo 2: Quay góc máy điện ảnh camera physics...")
            for i, p in enumerate(prompts_to_use[:default_num_scenes], 1):
                out_clip = temp_dir / f"scene_{i:02d}.mp4"
                cmd_v = [python_exe, str(scripts_dir / "fetch_veo.py"), "--prompt", p, "--output", str(out_clip), "--duration", "5", "--aspect-ratio", aspect_ratio]
                run_tracked_cmd(cmd_v)
                image_files.append(str(out_clip))
                log(f"Veo 2: Đã tạo clip chuyển động phân cảnh #{i}")
        else:
            fetch_script = "fetch_images.py" if engine == "google_imagen" else "fetch_images_flux.py"
            for i, p in enumerate(prompts_to_use[:default_num_scenes], 1):
                out_img = temp_dir / f"scene_{i:02d}.jpg"
                cmd_img = [python_exe, str(scripts_dir / fetch_script), "--prompt", p, "--output", str(out_img)]
                run_tracked_cmd(cmd_img)
                image_files.append(str(out_img))
                log(f"Đã tạo ảnh phân cảnh #{i}")

        # Bước 5: Render FFmpeg
        GLOBAL_STATE["step"] = 5
        GLOBAL_STATE["step_name"] = "Ghép Video, Chuyển cảnh & Phụ đề..."
        GLOBAL_STATE["progress"] = 85
        cmd_render = [
            python_exe, str(scripts_dir / "render_video.py"),
            "--images", *image_files,
            "--voice", str(voice_file),
            "--music", str(music_file),
            "--subtitles", str(sub_file),
            "--aspect-ratio", aspect_ratio,
            "--font-size", str(font_size),
            "--sub-position", sub_position,
            "--output", str(final_output)
        ]
        run_tracked_cmd(cmd_render)

        GLOBAL_STATE["progress"] = 100
        GLOBAL_STATE["step_name"] = "Hoàn tất xuất sắc!"
        log("🎉 XUẤT XƯỞNG THÀNH CÔNG VIDEO FINAL_REEL.MP4!")

        GLOBAL_STATE["result"] = {
            "video_url": f"/video/final_reel.mp4?t={int(time.time())}",
            "video_path": str(final_output.resolve()),
            "title": chosen_topic,
            "script": script_text,
            "caption": caption or f"🔥 {chosen_topic} #reels #viral #video",
            "size_kb": final_output.stat().st_size // 1024
        }
    except Exception as e:
        GLOBAL_STATE["error"] = str(e)
        GLOBAL_STATE["step_name"] = "Gặp sự cố"
        log(f"❌ LỖI: {e}")
    finally:
        GLOBAL_STATE["is_running"] = False

class StudioRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        url_path = urllib.parse.urlparse(self.path).path

        if url_path == "/" or url_path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))

        elif url_path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(check_system_status()).encode("utf-8"))

        elif url_path == "/api/providers":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(load_providers_config()).encode("utf-8"))

        elif url_path == "/api/progress":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(GLOBAL_STATE).encode("utf-8"))

        elif url_path == "/api/trending":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            cmd = [sys.executable, str(ROOT_DIR / "scripts" / "research_agent.py")]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, encoding="utf-8")
            self.wfile.write(res.stdout.encode("utf-8"))

        elif url_path == "/api/trending_all":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            cmd = [sys.executable, str(ROOT_DIR / "scripts" / "research_agent.py"), "--all"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, encoding="utf-8")
            self.wfile.write(res.stdout.encode("utf-8"))

        elif url_path == "/api/editor_data":
            # Dữ liệu phục vụ Tab Phòng Dựng Hậu Kỳ
            sub_file = ROOT_DIR / "shared_media" / "temp" / "subtitles.srt"
            srt_content = sub_file.read_text(encoding="utf-8") if sub_file.exists() else ""
            segments = parse_srt_to_segments(srt_content)
            
            video_file = ROOT_DIR / "shared_media" / "outputs" / "final_reel.mp4"
            has_video = video_file.exists()
            
            voice_file = ROOT_DIR / "shared_media" / "temp" / "voiceover.mp3"
            music_file = ROOT_DIR / "shared_media" / "temp" / "background_music.mp3"

            music_genres = [
                {"id": "ambient", "name": "Chill Ambient (Lo-fi nhẹ nhàng)", "icon": "fa-cloud-moon"},
                {"id": "epic", "name": "Epic Cinematic (Hùng tráng, dồn dập)", "icon": "fa-bolt"},
                {"id": "synthwave", "name": "Retro Synthwave (Điện tử 80s)", "icon": "fa-wave-square"},
                {"id": "cinematic", "name": "Dark Suspense (Bí ẩn, kịch tính)", "icon": "fa-mask"},
                {"id": "lofi", "name": "Warm Lofi (Ấm áp, thư thái)", "icon": "fa-mug-hot"},
                {"id": "upbeat", "name": "Upbeat Tech (Năng động, cuốn hút)", "icon": "fa-forward-fast"},
                {"id": "current", "name": "Giữ nguyên nhạc nền hiện tại", "icon": "fa-rotate-left"},
                {"id": "custom", "name": "Tải lên file MP3 của bạn...", "icon": "fa-cloud-arrow-up"},
                {"id": "none", "name": "Tắt nhạc nền (Chỉ giọng đọc)", "icon": "fa-volume-xmark"}
            ]

            res = {
                "status": "success",
                "has_video": has_video,
                "has_voice": voice_file.exists(),
                "has_music": music_file.exists(),
                "segments": segments,
                "music_genres": music_genres,
                "video_url": f"/video/final_reel.mp4?t={int(time.time())}" if has_video else ""
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))

        elif url_path == "/api/download_srt":
            sub_file = ROOT_DIR / "shared_media" / "temp" / "subtitles.srt"
            if sub_file.exists():
                content = sub_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/x-subrip; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="subtitles.srt"')
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Chưa có file phụ đề SRT.")

        elif url_path == "/api/download_video":
            video_file = ROOT_DIR / "shared_media" / "outputs" / "final_reel.mp4"
            if video_file.exists():
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Disposition", 'attachment; filename="final_reel.mp4"')
                self.send_header("Content-Length", str(video_file.stat().st_size))
                self.end_headers()
                with open(video_file, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
            else:
                self.send_error(404, "Chưa có video để tải.")

        elif url_path.startswith("/video/"):
            video_file = ROOT_DIR / "shared_media" / "outputs" / "final_reel.mp4"
            if video_file.exists():
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(video_file.stat().st_size))
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    with open(video_file, "rb") as f:
                        shutil.copyfileobj(f, self.wfile)
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, Exception):
                    pass
            else:
                self.send_error(404, "Chưa có video nào được tạo.")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        try:
            self._handle_do_POST()
        except Exception as e:
            logger.error(f"Lỗi hệ thống khi xử lý POST {self.path}: {e}", exc_info=True)
            try:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}).encode("utf-8"))
            except Exception:
                pass

    def _handle_do_POST(self):
        url_path = urllib.parse.urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        body = json.loads(post_data.decode("utf-8")) if post_data else {}

        if url_path == "/api/test_provider":
            base_url = body.get("base_url", "").rstrip("/")
            raw_key = body.get("api_key", "").strip()
            model = body.get("model", "gemini-3.1-flash-lite")

            if not raw_key:
                res = {"status": "error", "message": "Vui lòng nhập ít nhất 1 API Key!"}
            else:
                keys = [k.strip() for k in raw_key.replace("\n", ",").split(",") if k.strip()]
                results = []
                all_ok = True

                for idx, key in enumerate(keys):
                    key_masked = key[:6] + "..." + key[-4:] if len(key) > 10 else key
                    try:
                        if "googleapis.com" in base_url or key.startswith("AQ.") or key.startswith("AIza"):
                            candidates = [model, "gemini-3.1-flash-lite", "gemini-2.5-pro", "gemini-3.5-flash"]
                            success_model = None
                            last_err = None
                            for candidate in candidates:
                                if not candidate: continue
                                test_url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent?key={key}"
                                try:
                                    r = requests.post(test_url, json={"contents": [{"parts": [{"text": "hi"}]}]}, timeout=5)
                                    if r.status_code == 200:
                                        success_model = candidate
                                        break
                                    else:
                                        last_err = f"HTTP {r.status_code}"
                                except Exception as ex:
                                    last_err = str(ex)
                            if success_model:
                                results.append(f"• Key {idx+1} ({key_masked}): ✅ Hoạt động ({success_model})")
                            else:
                                all_ok = False
                                results.append(f"• Key {idx+1} ({key_masked}): ❌ Lỗi ({last_err})")
                        else:
                            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                            payload = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                            r = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=5)
                            if r.status_code == 200:
                                results.append(f"• Key {idx+1} ({key_masked}): ✅ Hoạt động ({model})")
                            else:
                                all_ok = False
                                results.append(f"• Key {idx+1} ({key_masked}): ❌ HTTP {r.status_code}")
                    except Exception as e:
                        all_ok = False
                        results.append(f"• Key {idx+1} ({key_masked}): ❌ Lỗi ({str(e)[:80]})")

                msg_lines = "<br>".join(results)
                if len(keys) > 1:
                    status_str = "success" if any("✅" in r for r in results) else "error"
                    summary = f"🎉 <b>Đã xác thực Multi-Key Pool ({len(keys)} tài khoản):</b><br>{msg_lines}<br><span class='text-[10px] text-emerald-400 font-bold'>✨ Sẵn sàng cơ chế tự động luân phiên khi hết Quota!</span>"
                else:
                    status_str = "success" if all_ok else "error"
                    summary = results[0] if results else "Chưa có key"

                res = {"status": status_str, "message": summary}

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))

        elif url_path == "/api/save_provider":
            pid = body.get("provider_id", "")
            key = body.get("api_key", "").strip()
            model = body.get("model", "").strip()
            base_url = body.get("base_url", "").strip()
            set_active = body.get("set_active", False)

            cfg = load_providers_config()
            if pid in cfg.get("providers", {}):
                if key: cfg["providers"][pid]["api_key"] = key
                if model: cfg["providers"][pid]["selected_model"] = model
                if base_url: cfg["providers"][pid]["base_url"] = base_url

            if set_active:
                cfg["active_provider"] = pid
                env_file = ROOT_DIR / ".env"
                pinfo = cfg["providers"][pid]
                set_key(str(env_file), "CUSTOM_LLM_API_URL", pinfo["base_url"])
                set_key(str(env_file), "CUSTOM_LLM_API_KEY", pinfo["api_key"])
                set_key(str(env_file), "CUSTOM_LLM_MODEL_NAME", pinfo["selected_model"])
                if pid == "gemini":
                    set_key(str(env_file), "GEMINI_API_KEY", pinfo["api_key"])

            save_providers_config(cfg)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": "Đã lưu và cập nhật mô hình!"}).encode("utf-8"))

        elif url_path == "/api/generate":
            if GLOBAL_STATE["is_running"]:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Đang có tiến trình render chạy dở!"}).encode("utf-8"))
                return

            topic = body.get("topic", "")
            custom_script = body.get("script", "")
            voice = body.get("voice", "vi-VN-HoaiMyNeural")
            duration_mode = body.get("duration_mode", "short")
            font_size = int(body.get("font_size", 18))
            aspect_ratio = body.get("aspect_ratio", "9:16")
            align_mode = body.get("align_mode", "center")
            engine = body.get("engine", "google_veo2")
            sub_position = body.get("sub_position", "bottom")

            t = threading.Thread(target=run_pipeline_thread, args=(topic, custom_script, voice, duration_mode, font_size, aspect_ratio, engine, sub_position), daemon=True)
            t.start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started"}).encode("utf-8"))

        elif url_path == "/api/upload_music":
            b64_data = body.get("music_base64", "")
            if b64_data:
                if "," in b64_data:
                    b64_data = b64_data.split(",", 1)[1]
                raw_bytes = base64.b64decode(b64_data)
                custom_out = ROOT_DIR / "shared_media" / "temp" / "custom_music.mp3"
                custom_out.parent.mkdir(parents=True, exist_ok=True)
                custom_out.write_bytes(raw_bytes)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": "Đã tải lên nhạc nền thành công!"}).encode("utf-8"))
            else:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Dữ liệu file nhạc không hợp lệ"}).encode("utf-8"))

        elif url_path == "/api/export_remix":
            # XUẤT HẬU KỲ SIÊU TỐC 2-3 GIÂY (PHÒNG DỰNG TAB 2)
            segments = body.get("segments", [])
            font_name = body.get("font_name", "Google Sans")
            font_size = int(body.get("font_size", 18))
            font_bold = bool(body.get("font_bold", True))
            primary_color = body.get("primary_color", "#FFFFFF")
            outline_color = body.get("outline_color", "#000000")
            outline_size = int(body.get("outline_size", 2))
            position_y = float(body.get("position_y", 75.0))
            bg_box = bool(body.get("bg_box", False))
            bg_opacity = float(body.get("bg_opacity", 0.5))

            music_choice = body.get("music_choice", "current")
            voice_volume = float(body.get("voice_volume", 100)) / 100.0
            music_volume = float(body.get("music_volume", 12)) / 100.0
            audio_ducking = bool(body.get("audio_ducking", True))
            aspect_ratio = body.get("aspect_ratio", "9:16")

            temp_dir = ROOT_DIR / "shared_media" / "temp"
            outputs_dir = ROOT_DIR / "shared_media" / "outputs"
            temp_dir.mkdir(parents=True, exist_ok=True)
            outputs_dir.mkdir(parents=True, exist_ok=True)

            sub_file = temp_dir / "subtitles.srt"
            if segments:
                srt_text = segments_to_srt(segments)
                sub_file.write_text(srt_text, encoding="utf-8")

            # Định vị file video gốc
            raw_video = temp_dir / "temp_raw_video.mp4"
            final_video = outputs_dir / "final_reel.mp4"
            temp_va = temp_dir / "temp_video_audio.mp4"

            if not raw_video.exists() or raw_video.stat().st_size < 1000:
                ref_v = temp_va if temp_va.exists() else final_video
                if ref_v.exists():
                    subprocess.run(["ffmpeg", "-y", "-i", str(ref_v), "-an", "-c:v", "copy", str(raw_video)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if not raw_video.exists():
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Chưa có video gốc để remix. Hãy tạo video ở Tab 1 trước!"}).encode("utf-8"))
                return

            voice_file = temp_dir / "voiceover.mp3"
            if not voice_file.exists():
                voice_file = None

            # Giải quyết nhạc nền
            music_file = None
            if music_choice == "none":
                music_file = None
            elif music_choice == "custom":
                c_mp3 = temp_dir / "custom_music.mp3"
                if c_mp3.exists():
                    music_file = c_mp3
            elif music_choice in ("ambient", "epic", "lofi", "synthwave", "cinematic", "upbeat"):
                lib_dir = ROOT_DIR / "shared_media" / "music_library"
                lib_dir.mkdir(parents=True, exist_ok=True)
                lib_mp3 = lib_dir / f"{music_choice}.mp3"
                if not lib_mp3.exists():
                    from generate_music import generate_offline_synth_track
                    generate_offline_synth_track(60, lib_mp3, genre=music_choice)
                music_file = lib_mp3
            else: # current
                curr_mp3 = temp_dir / "background_music.mp3"
                if curr_mp3.exists():
                    music_file = curr_mp3

            from render_video import remix_and_export_video
            res_remix = remix_and_export_video(
                source_video=raw_video,
                voice_path=voice_file,
                music_path=music_file,
                sub_path=sub_file if sub_file.exists() else None,
                output_video=final_video,
                voice_volume=voice_volume,
                music_volume=music_volume,
                audio_ducking=audio_ducking,
                font_name=font_name,
                font_size=font_size,
                font_bold=font_bold,
                primary_color=primary_color,
                outline_color=outline_color,
                outline_size=outline_size,
                position_y=position_y,
                bg_box=bg_box,
                bg_opacity=bg_opacity,
                aspect_ratio=aspect_ratio,
                align_mode=align_mode
            )

            res_remix["video_url"] = f"/video/final_reel.mp4?t={int(time.time())}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res_remix, ensure_ascii=False).encode("utf-8"))

        elif url_path == "/api/flow_generate_prompts":
            topic = body.get("topic", "").strip() or "Khám phá bí mật công nghệ tương lai"
            duration_mode = body.get("duration_mode", "short")
            aspect_ratio = body.get("aspect_ratio", "9:16")
            voice = body.get("voice", "vi-VN-HoaiMyNeural")

            load_dotenv(ROOT_DIR / ".env")
            llm_key = os.getenv("CUSTOM_LLM_API_KEY", "")
            llm_url = os.getenv("CUSTOM_LLM_API_URL", "https://generativelanguage.googleapis.com/v1beta")
            llm_model = os.getenv("CUSTOM_LLM_MODEL_NAME", "gemini-3.1-flash-lite")

            num_scenes = 12 if duration_mode == "long" else (8 if duration_mode == "medium" else 5)
            req_text = f"kịch bản {num_scenes} phân cảnh kịch tính"

            script_text, scenes_ai, image_prompts, caption = generate_viral_script_ai(
                topic=topic, context="", duration_mode=duration_mode,
                req_duration_text=req_text, default_num_scenes=num_scenes,
                llm_key=llm_key, llm_url=llm_url, llm_model=llm_model
            )

            temp_dir = ROOT_DIR / "shared_media" / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            voice_file = temp_dir / "voiceover.mp3"
            sub_file = temp_dir / "subtitles.srt"

            def run_bg_tts(t, v, ov, os_sub):
                try:
                    subprocess.run([sys.executable, str(ROOT_DIR / "scripts" / "generate_tts.py"), "--text", t, "--voice", v, "--output", str(ov), "--output-sub", str(os_sub)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            threading.Thread(target=run_bg_tts, args=(script_text, voice, voice_file, sub_file), daemon=True).start()

            camera_modes = [
                "Drone cinematic sweep, high angle establishing shot, volumetric amber mist",
                "Dutch angle tilted camera, intense dramatic suspense, glowing neon rim light",
                "Macro focus extreme close-up, shallow depth of field f/1.4, hyperrealistic micro textures",
                "Smooth tracking dolly shot following subject movement, anamorphic lens flare",
                "FPV dynamic dive camera movement, high kinetic energy, immersive depth",
                "360 degree orbit reveal camera movement around center subject, epic scale",
                "Low angle heroic push-in shot, cinematic studio lighting, 8k uhd"
            ]

            scenes = []
            master_lines = [
                f"# GOOGLE FLOW (VEO 2) MASTER STORYBOARD",
                f"Topic: {topic.upper()}",
                f"Aspect Ratio: {aspect_ratio}",
                f"Aesthetic: Award-winning 35mm photo, shot on Hasselblad, dramatic cinematic lighting, photorealistic textures, 8k uhd\n"
            ]

            if scenes_ai and len(scenes_ai) > 0:
                for s in scenes_ai[:num_scenes]:
                    cam = s.get("camera", "Cinematic view")
                    flow_p = s.get("veo_prompt", "")
                    scenes.append({
                        "scene_num": s["scene_num"],
                        "camera": cam,
                        "flow_prompt": flow_p,
                        "narration": s.get("narration", "")
                    })
                    master_lines.append(f"Scene {s['scene_num']} [{cam}]:\n{flow_p}\n")
            else:
                for i, p in enumerate(image_prompts[:num_scenes], 1):
                    cam = camera_modes[(i - 1) % len(camera_modes)]
                    flow_p = f"{cam}, {p}"
                    scenes.append({
                        "scene_num": i,
                        "camera": cam,
                        "flow_prompt": flow_p
                    })
                    master_lines.append(f"Scene {i} [{cam}]:\n{flow_p}\n")

            try:
                (temp_dir / "last_topic.txt").write_text(topic, encoding="utf-8")
                (temp_dir / "flow_scenes.json").write_text(json.dumps(scenes, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                logger.warning(f"Lỗi lưu cache chủ đề: {e}")

            res = {
                "status": "success",
                "topic": topic,
                "script_text": script_text,
                "scenes": scenes,
                "master_prompt": "\n".join(master_lines),
                "flow_project_url": "https://flow.google.com/project/4b843d6d-9973-4d99-afad-3a40db3b1880"
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))

        elif url_path == "/api/flow_import_video":
            b64_data = body.get("video_base64", "")
            if not b64_data:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Không nhận được dữ liệu video"}).encode("utf-8"))
                return

            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
            video_bytes = base64.b64decode(b64_data)

            temp_dir = ROOT_DIR / "shared_media" / "temp"
            outputs_dir = ROOT_DIR / "shared_media" / "outputs"
            temp_dir.mkdir(parents=True, exist_ok=True)
            outputs_dir.mkdir(parents=True, exist_ok=True)

            raw_video = temp_dir / "temp_raw_video.mp4"
            final_video = outputs_dir / "final_reel.mp4"
            temp_va = temp_dir / "temp_video_audio.mp4"

            raw_video.write_bytes(video_bytes)
            temp_va.write_bytes(video_bytes)
            final_video.write_bytes(video_bytes)

            from render_video import get_media_duration
            duration = get_media_duration(raw_video)

            res = {
                "status": "success",
                "message": f"Đã nạp video từ Google Flow thành công ({len(video_bytes)//1024} KB, {duration:.1f}s)!",
                "video_url": f"/video/final_reel.mp4?t={int(time.time())}",
                "duration": duration
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))

        elif url_path == "/api/flow_concat_videos":
            videos = body.get("videos", [])
            aspect_ratio = body.get("aspect_ratio", "9:16")
            voice = body.get("voice", "vi-VN-HoaiMyNeural")

            if not videos:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Không nhận được danh sách phân cảnh video"}).encode("utf-8"))
                return

            temp_dir = ROOT_DIR / "shared_media" / "temp"
            outputs_dir = ROOT_DIR / "shared_media" / "outputs"
            temp_dir.mkdir(parents=True, exist_ok=True)
            outputs_dir.mkdir(parents=True, exist_ok=True)

            clip_files = []
            for i, vid in enumerate(videos):
                b64_data = vid.get("base64", "")
                if "," in b64_data:
                    b64_data = b64_data.split(",", 1)[1]
                video_bytes = base64.b64decode(b64_data)
                clip_path = temp_dir / f"flow_scene_{i+1}.mp4"
                clip_path.write_bytes(video_bytes)
                clip_files.append(clip_path)

            def get_duration_safe(f_path):
                try:
                    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(f_path)]
                    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    return max(1.0, float(r.stdout.strip()))
                except Exception:
                    return 5.0

            clip_durations = [get_duration_safe(c) for c in clip_files]

            # --- 1. XÂY DỰNG FILE PHỤ ĐỀ (subtitles.srt) KHỚP CHUẨN 100% THEO THỜI LƯỢNG TỪNG CẢNH ---
            def format_srt_time(sec):
                sec = max(0.0, float(sec))
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s = int(sec % 60)
                ms = int(round((sec - int(sec)) * 1000))
                if ms >= 1000: ms = 999
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            sub_cues = []
            cum_time = 0.0
            narrations = []

            for i, vid in enumerate(videos):
                dur = clip_durations[i]
                t_start = cum_time
                t_end = cum_time + dur
                cum_time = t_end

                txt = (vid.get("narration") or vid.get("prompt") or "").strip()
                if not txt:
                    txt = f"Cảnh {vid.get('scene_num', i+1)}: {vid.get('camera', 'Điện ảnh')}"
                narrations.append(txt)

                # Giữ đúng 1 thẻ phụ đề duy nhất cho mỗi phân cảnh (chuẩn tỷ lệ 1-1, không tách đôi làm lệch số cảnh)
                words = txt.split()
                if len(words) > 6 and "\n" not in txt:
                    mid = (len(words) + 1) // 2
                    fmt_text = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])
                else:
                    fmt_text = txt

                sc_num = vid.get("scene_num", i + 1)
                sub_cues.append((i + 1, t_start, t_end, fmt_text, sc_num))

            sub_file = temp_dir / "subtitles.srt"
            srt_lines = []
            for c_idx, s_t, e_t, c_text, sc_num in sub_cues:
                srt_lines.append(f"{c_idx}\n{format_srt_time(s_t)} --> {format_srt_time(e_t)}\n{c_text}\n")
            sub_file.write_text("\n".join(srt_lines), encoding="utf-8")

            # --- 2. XÂY DỰNG FILE GIỌNG ĐỌC (voiceover.mp3) KHỚP CHUẨN TỪNG CẢNH ---
            voice_file = temp_dir / "voiceover.mp3"
            has_any_narration = any(bool(n.strip()) for n in narrations)

            if has_any_narration:
                try:
                    import asyncio
                    import edge_tts

                    async def synthesize_scene_voices():
                        async def gen_scene_audio(text, out_p):
                            if not text:
                                return False
                            comm = edge_tts.Communicate(text, voice)
                            await comm.save(str(out_p))
                            return True

                        tasks = []
                        scene_audio_files = []
                        for i, n_txt in enumerate(narrations):
                            scene_out = temp_dir / f"scene_tts_{i+1}.mp3"
                            scene_audio_files.append(scene_out)
                            tasks.append(gen_scene_audio(n_txt, scene_out))

                        await asyncio.gather(*tasks)
                        return scene_audio_files

                    scene_audios = asyncio.run(synthesize_scene_voices())

                    # Pad từng audio file theo đúng thời lượng clip_durations[i]
                    padded_audio_files = []
                    for i, (s_audio, dur) in enumerate(zip(scene_audios, clip_durations)):
                        pad_out = temp_dir / f"scene_padded_{i+1}.mp3"
                        if s_audio.exists() and s_audio.stat().st_size > 0:
                            subprocess.run([
                                "ffmpeg", "-y", "-i", str(s_audio),
                                "-af", f"apad=whole_dur={dur}",
                                "-t", str(dur),
                                str(pad_out)
                            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            subprocess.run([
                                "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                                "-t", str(dur),
                                str(pad_out)
                            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        padded_audio_files.append(pad_out)

                    a_inputs = []
                    for p_a in padded_audio_files:
                        a_inputs.extend(["-i", str(p_a)])
                    a_filter = f"concat=n={len(padded_audio_files)}:v=0:a=1[aout]"
                    subprocess.run(["ffmpeg", "-y"] + a_inputs + ["-filter_complex", a_filter, "-map", "[aout]", "-c:a", "libmp3lame", "-b:a", "192k", str(voice_file)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    logger.warning(f"Lỗi tạo voiceover phân cảnh đồng bộ: {e}")

            w, h = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)

            inputs = []
            filter_parts = []
            concat_inputs = []
            for i, clip in enumerate(clip_files):
                inputs.extend(["-i", str(clip)])
                filter_parts.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}]")
                concat_inputs.append(f"[v{i}]")

            filter_complex = "; ".join(filter_parts) + "; " + "".join(concat_inputs) + f"concat=n={len(clip_files)}:v=1:a=0[outv]"

            raw_stitched = temp_dir / "temp_raw_video.mp4"
            final_video = outputs_dir / "final_reel.mp4"
            temp_va = temp_dir / "temp_video_audio.mp4"

            # 3. Nối video (không kèm tiếng cũ)
            cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", filter_complex, "-map", "[outv]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-an", str(raw_stitched)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if proc.returncode != 0:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": f"Lỗi ghép video FFmpeg: {proc.stderr[-300:]}"}, ensure_ascii=False).encode("utf-8"))
                return

            total_duration = get_duration_safe(raw_stitched)

            # 4. Xử lý Nhạc nền (BGM) & Hòa âm với Giọng đọc
            music_choice = body.get("music_choice", "epic")
            music_lib_dir = ROOT_DIR / "shared_media" / "music_library"
            bgm_file = temp_dir / "background_music.mp3"
            has_bgm = False

            if music_choice and music_choice != "none":
                sel_music = music_lib_dir / f"{music_choice}.mp3"
                if sel_music.exists():
                    try:
                        shutil.copy2(sel_music, bgm_file)
                        has_bgm = True
                    except Exception as e:
                        logger.warning(f"Không thể copy file nhạc {sel_music}: {e}")
                elif bgm_file.exists():
                    has_bgm = True

            has_voice = voice_file.exists() and voice_file.stat().st_size > 0

            # 5. Kiểm tra âm thanh gốc của từng phân cảnh (nếu người dùng chọn giữ tiếng gốc)
            def check_has_audio(p):
                try:
                    c = ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(p)]
                    out = subprocess.run(c, capture_output=True, text=True).stdout.strip()
                    return bool(out)
                except Exception:
                    return False

            has_custom_orig = any(vid.get("audio_mode") == "original" and check_has_audio(clip_files[idx]) for idx, vid in enumerate(videos))
            ambient_file = temp_dir / "scene_ambient.mp3"
            has_ambient = False

            if has_custom_orig:
                try:
                    amb_clips = []
                    for idx, vid in enumerate(videos):
                        dur = clip_durations[idx]
                        amb_out = temp_dir / f"amb_{idx+1}.mp3"
                        if vid.get("audio_mode") == "original" and check_has_audio(clip_files[idx]):
                            subprocess.run([
                                "ffmpeg", "-y", "-i", str(clip_files[idx]),
                                "-vn", "-t", str(dur),
                                "-af", f"apad=whole_dur={dur}",
                                str(amb_out)
                            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            subprocess.run([
                                "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                                "-t", str(dur),
                                str(amb_out)
                            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        amb_clips.append(amb_out)

                    amb_ins = []
                    for ac in amb_clips:
                        amb_ins.extend(["-i", str(ac)])
                    amb_filt = f"concat=n={len(amb_clips)}:v=0:a=1[ambout]"
                    subprocess.run(["ffmpeg", "-y"] + amb_ins + ["-filter_complex", amb_filt, "-map", "[ambout]", "-c:a", "libmp3lame", "-b:a", "192k", str(ambient_file)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    has_ambient = ambient_file.exists() and ambient_file.stat().st_size > 0
                except Exception as e:
                    logger.warning(f"Lỗi trích xuất âm thanh phân cảnh gốc: {e}")

            # 6. Hòa âm tổng hợp (Voiceover 100% + BGM 12% + Ambient 30%)
            mixed_audio = temp_dir / "final_mixed_audio.mp3"
            fade_out_start = max(0.0, total_duration - 2.5)

            if has_voice and has_bgm and has_ambient:
                mix_f = (
                    "[0:a]volume=1.05[v];"
                    f"[1:a]volume=0.10,afade=t=in:d=1.5,afade=t=out:st={fade_out_start:.1f}:d=2.5,aloop=loop=-1:size=2e+09[m];"
                    "[2:a]volume=0.35[amb];"
                    "[v][m][amb]amix=inputs=3:duration=first:dropout_transition=2[aout]"
                )
                subprocess.run(["ffmpeg", "-y", "-i", str(voice_file), "-i", str(bgm_file), "-i", str(ambient_file), "-filter_complex", mix_f, "-map", "[aout]", "-t", str(total_duration), "-c:a", "libmp3lame", "-b:a", "192k", str(mixed_audio)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif has_voice and has_bgm:
                mix_f = (
                    "[0:a]volume=1.05[v];"
                    f"[1:a]volume=0.12,afade=t=in:d=1.5,afade=t=out:st={fade_out_start:.1f}:d=2.5,aloop=loop=-1:size=2e+09[m];"
                    "[v][m]amix=inputs=2:duration=first:dropout_transition=2[aout]"
                )
                subprocess.run(["ffmpeg", "-y", "-i", str(voice_file), "-i", str(bgm_file), "-filter_complex", mix_f, "-map", "[aout]", "-t", str(total_duration), "-c:a", "libmp3lame", "-b:a", "192k", str(mixed_audio)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif has_voice and has_ambient:
                mix_f = "[0:a]volume=1.05[v];[1:a]volume=0.4[amb];[v][amb]amix=inputs=2:duration=first:dropout_transition=2[aout]"
                subprocess.run(["ffmpeg", "-y", "-i", str(voice_file), "-i", str(ambient_file), "-filter_complex", mix_f, "-map", "[aout]", "-t", str(total_duration), "-c:a", "libmp3lame", "-b:a", "192k", str(mixed_audio)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif has_voice:
                mixed_audio = voice_file
            elif has_bgm:
                bgm_f = f"[0:a]volume=0.25,afade=t=in:d=1.5,afade=t=out:st={fade_out_start:.1f}:d=2.5,aloop=loop=-1:size=2e+09[m]"
                subprocess.run(["ffmpeg", "-y", "-i", str(bgm_file), "-filter_complex", bgm_f, "-map", "[m]", "-t", str(total_duration), "-c:a", "libmp3lame", "-b:a", "192k", str(mixed_audio)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                mixed_audio = None

            # 7. Ghép hình ảnh và âm thanh hoàn chỉnh
            mux_cmd = ["ffmpeg", "-y", "-i", str(raw_stitched)]
            if mixed_audio and mixed_audio.exists():
                mux_cmd.extend(["-i", str(mixed_audio), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(final_video)])
            else:
                mux_cmd.extend(["-c:v", "copy", "-an", str(final_video)])

            subprocess.run(mux_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            shutil.copy2(final_video, temp_va)

            duration = get_duration_safe(final_video)

            segments_payload = [
                {
                    "id": c_idx,
                    "sceneNum": sc_num,
                    "start": round(s_t, 2),
                    "end": round(e_t, 2),
                    "start_display": f"{s_t:.2f}",
                    "end_display": f"{e_t:.2f}",
                    "text": c_text
                }
                for c_idx, s_t, e_t, c_text, sc_num in sub_cues
            ]

            res = {
                "status": "success",
                "message": f"Đã ghép thành công {len(clip_files)} phân cảnh ({duration:.1f}s) & đồng bộ khớp 100% kịch bản phụ đề!",
                "video_url": f"/video/final_reel.mp4?t={int(time.time())}",
                "duration": duration,
                "scene_count": len(clip_files),
                "segments": segments_payload
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))

        elif url_path == "/api/save_subtitles":
            segments = body.get("segments", [])
            temp_dir = ROOT_DIR / "shared_media" / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            sub_file = temp_dir / "subtitles.srt"

            def format_srt_time(sec):
                sec = max(0.0, float(sec))
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s = int(sec % 60)
                ms = int(round((sec - int(sec)) * 1000))
                if ms >= 1000: ms = 999
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            srt_lines = []
            for i, seg in enumerate(segments, 1):
                s_t = seg.get("start", 0.0)
                e_t = seg.get("end", s_t + 2.0)
                txt = seg.get("text", "").strip()
                srt_lines.append(f"{i}\n{format_srt_time(s_t)} --> {format_srt_time(e_t)}\n{txt}\n")
            sub_file.write_text("\n".join(srt_lines), encoding="utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": "Đã lưu phụ đề thành công!"}).encode("utf-8"))

        elif url_path == "/api/sync_subtitles_tts":
            segments = body.get("segments", [])
            voice = body.get("voice", "vi-VN-HoaiMyNeural")
            temp_dir = ROOT_DIR / "shared_media" / "temp"
            outputs_dir = ROOT_DIR / "shared_media" / "outputs"
            temp_dir.mkdir(parents=True, exist_ok=True)
            outputs_dir.mkdir(parents=True, exist_ok=True)

            sub_file = temp_dir / "subtitles.srt"
            voice_file = temp_dir / "voiceover.mp3"
            final_video = outputs_dir / "final_reel.mp4"

            def format_srt_time(sec):
                sec = max(0.0, float(sec))
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s = int(sec % 60)
                ms = int(round((sec - int(sec)) * 1000))
                if ms >= 1000: ms = 999
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            # 1. Ghi SRT
            srt_lines = []
            for i, seg in enumerate(segments, 1):
                s_t = seg.get("start", 0.0)
                e_t = seg.get("end", s_t + 2.0)
                txt = seg.get("text", "").strip()
                srt_lines.append(f"{i}\n{format_srt_time(s_t)} --> {format_srt_time(e_t)}\n{txt}\n")
            sub_file.write_text("\n".join(srt_lines), encoding="utf-8")

            # 2. Sinh audio cho từng segment và ghép theo timeline
            try:
                import asyncio
                import edge_tts

                async def gen_all_segs():
                    async def gen_seg_audio(txt, out_p):
                        if not txt: return
                        comm = edge_tts.Communicate(txt, voice)
                        await comm.save(str(out_p))

                    tasks = []
                    seg_audios = []
                    for i, seg in enumerate(segments):
                        seg_out = temp_dir / f"seg_tts_{i+1}.mp3"
                        seg_audios.append((seg, seg_out))
                        tasks.append(gen_seg_audio(seg.get("text", ""), seg_out))
                    await asyncio.gather(*tasks)
                    return seg_audios

                seg_audios = asyncio.run(gen_all_segs())

                # Ghép audio không bao giờ đè tiếng
                build_aligned_voiceover(segments, seg_audios, temp_dir, voice_file)

                if final_video.exists():
                    temp_remux = temp_dir / "temp_remux_voice.mp4"
                    subprocess.run(["ffmpeg", "-y", "-i", str(final_video), "-i", str(voice_file), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(temp_remux)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if temp_remux.exists() and temp_remux.stat().st_size > 0:
                        shutil.copy2(temp_remux, final_video)

                res = {
                    "status": "success",
                    "message": "Đã cập nhật giọng đọc và phụ đề khớp 100% theo các mốc thời gian!",
                    "video_url": f"/video/final_reel.mp4?t={int(time.time())}"
                }
            except Exception as e:
                res = {"status": "error", "message": f"Lỗi sinh audio đồng bộ: {e}"}

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))

        elif url_path == "/api/preview_script":
            topic = body.get("topic", "").strip() or "Khám phá khoa học và công nghệ mới"
            duration_mode = body.get("duration_mode", "short")
            load_dotenv(ROOT_DIR / ".env")
            llm_key = os.getenv("CUSTOM_LLM_API_KEY", "")
            llm_url = os.getenv("CUSTOM_LLM_API_URL", "https://generativelanguage.googleapis.com/v1beta")
            llm_model = os.getenv("CUSTOM_LLM_MODEL_NAME", "gemini-3.1-flash-lite")

            script_text, _, image_prompts, caption = generate_viral_script_ai(
                topic=topic, context="", duration_mode=duration_mode,
                req_duration_text="kịch bản ngắn gọn 30 - 45 giây", default_num_scenes=7,
                llm_key=llm_key, llm_url=llm_url, llm_model=llm_model
            )
            res = {"status": "success", "script": script_text, "caption": caption, "prompts_count": len(image_prompts)}
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif url_path == "/api/open_folder":
            folder = ROOT_DIR / "shared_media" / "outputs"
            if sys.platform == "win32":
                os.startfile(folder)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        elif url_path == "/api/shutdown":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "shutdown", "message": "Đang tắt hoàn toàn ứng dụng..."}).encode("utf-8"))
            GLOBAL_STATE["is_running"] = False
            kill_all_subprocesses()
            def delayed_exit():
                time.sleep(0.5)
                os._exit(0)
            threading.Thread(target=delayed_exit, daemon=True).start()

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="vi" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Video Factory Studio Pro</title>
  <!-- Tailwind CSS & FontAwesome -->
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <!-- Google Fonts Hỗ trợ tiếng Việt -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:ital,wght@0,400;0,600;0,700;0,900;1,700&family=Montserrat:wght@400;600;700;900&family=Roboto:wght@400;500;700;900&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            dark: { 950: '#07080a', 900: '#0d0f12', 850: '#13161b', 800: '#1a1e24', 700: '#272c35' },
            brand: { 500: '#3b82f6', 600: '#2563eb' }
          },
          fontFamily: {
            sans: ['"Google Sans"', 'Montserrat', '"Be Vietnam Pro"', 'Roboto', 'sans-serif']
          }
        }
      }
    }
  </script>
  <style>
    body { background-color: #090a0d; color: #f3f4f6; font-family: 'Google Sans', 'Be Vietnam Pro', sans-serif; }
    .glass-card { background: rgba(19, 22, 27, 0.75); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .glass-card:hover { border-color: rgba(255, 255, 255, 0.15); }
    .active-nav-tab { background: linear-gradient(135deg, #2563eb, #7c3aed); color: #fff; box-shadow: 0 0 15px rgba(59, 130, 246, 0.4); }
    .seg-card { transition: all 0.15s ease; border: 1px solid #272c35; }
    .seg-card:hover { border-color: #3b82f6; transform: translateY(-1px); }
    .seg-card.active-seg { border-color: #60a5fa !important; background: rgba(59, 130, 246, 0.15) !important; box-shadow: 0 0 12px rgba(96, 165, 250, 0.3); }
    /* Tùy chỉnh thanh trượt Range */
    input[type=range] { accent-color: #3b82f6; }
    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0d0f12; }
    ::-webkit-scrollbar-thumb { background: #272c35; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #3b82f6; }
  </style>
</head>
<body class="min-h-screen flex flex-col">

  <!-- HEADER THANH ĐIỀU HƯỚNG -->
  <header class="glass-card sticky top-0 z-50 px-6 py-3 border-b border-gray-800 flex flex-wrap items-center justify-between gap-4">
    <!-- Logo & Title -->
    <div class="flex items-center gap-3">
      <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/30">
        <i class="fa-solid fa-film text-lg"></i>
      </div>
      <div>
        <h1 class="text-lg font-black tracking-wide bg-gradient-to-r from-blue-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent">AI VIDEO FACTORY</h1>
        <div class="flex items-center gap-2 text-xs text-gray-400">
          <span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>Google Flow & Studio Pro</span>
        </div>
      </div>
    </div>

    <!-- 2 TABS CHUYỂN ĐỔI CHÍNH -->
    <div class="flex items-center bg-dark-900 p-1.5 rounded-2xl border border-gray-800">
      <button id="btnTabFactory" onclick="switchMainTab('factory')" class="active-nav-tab px-5 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition-all">
        <i class="fa-solid fa-wand-magic-sparkles"></i> 🏭 Xưởng AI Tự Động
      </button>
      <button id="btnTabStudio" onclick="switchMainTab('studio')" class="px-5 py-2 rounded-xl text-sm font-bold text-gray-400 hover:text-white flex items-center gap-2 transition-all">
        <i class="fa-solid fa-sliders"></i> ✂️ Phòng Dựng Hậu Kỳ
        <span class="px-1.5 py-0.5 text-[10px] uppercase font-black bg-gradient-to-r from-amber-500 to-rose-500 text-white rounded-md">Pro</span>
      </button>
    </div>

    <!-- Nút Models & Tắt App -->
    <div class="flex items-center gap-3">
      <button onclick="openModal('modelsModal')" class="px-4 py-2 text-xs font-bold rounded-xl bg-gradient-to-r from-blue-700 via-indigo-600 to-purple-600 hover:from-blue-600 hover:to-indigo-500 text-white flex items-center gap-2 transition shadow-lg shadow-indigo-500/25 border border-indigo-400/40">
        <i class="fa-solid fa-key text-amber-300"></i>
        <span>CẤU HÌNH API KEY (PRO)</span>
        <span id="activeModelLabel" class="px-1.5 py-0.5 rounded bg-black/30 text-[10px] text-blue-200 font-mono">Gemini</span>
      </button>
      <button onclick="shutdownApp()" class="px-3.5 py-2 text-xs font-bold rounded-xl bg-rose-950/40 border border-rose-800/80 hover:bg-rose-600 text-rose-300 hover:text-white flex items-center gap-2 transition" title="Tắt hoàn toàn server và các tiến trình">
        <i class="fa-solid fa-power-off"></i> Tắt App
      </button>
    </div>
  </header>

  <!-- NỘI DUNG CHÍNH (2 TAB) -->
  <main class="flex-1 max-w-[1720px] w-full mx-auto p-4 sm:p-6">

    <!-- ==================== TAB 1: XƯỞNG AI TỰ ĐỘNG ==================== -->
    <div id="tabFactoryView" class="block space-y-6">

      <!-- ==================== BƯỚC 1: RADAR TIN TỨC XU HƯỚNG (ĐẦU TIÊN) ==================== -->
      <div class="glass-card rounded-2xl p-5 border border-indigo-500/30 bg-gradient-to-r from-blue-950/25 via-dark-900 to-indigo-950/25 space-y-4">
        <div class="flex flex-wrap justify-between items-center gap-3 border-b border-gray-800 pb-3">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-blue-500 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
              <i class="fa-solid fa-radar text-base"></i>
            </div>
            <div>
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded text-[10px] font-black uppercase bg-blue-600 text-white">BƯỚC 1</span>
                <h2 class="text-sm font-black text-white">RADAR TIN TỨC XU HƯỚNG (GOOGLE TRENDS & BÁO CHÍ)</h2>
              </div>
              <p class="text-xs text-gray-400">Chọn 1 tin nóng để AI tự động đạo diễn kịch bản và góc máy Veo 2 ở Bước 2 bên dưới.</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span id="trendingCountLabel" class="text-xs font-mono font-bold text-indigo-400 px-2.5 py-1 bg-dark-950 rounded-lg border border-gray-800">Đang quét...</span>
            <button onclick="fetchTrendingTopics(true)" class="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-dark-850 hover:bg-dark-800 border border-gray-700 hover:border-blue-400 text-gray-200 flex items-center gap-1.5 transition shadow">
              <i class="fa-solid fa-rotate text-blue-400"></i> Cào Lại Tin Nóng
            </button>
          </div>
        </div>

        <!-- Bộ Lọc Danh Mục Tin Nóng -->
        <div class="flex flex-wrap gap-1.5 items-center">
          <button onclick="filterTrendingCategory('all', this)" class="cat-pill px-3 py-1 rounded-lg text-xs font-bold bg-amber-500 text-dark-950 border border-amber-400 shadow-sm transition">Tất Cả</button>
          <button onclick="filterTrendingCategory('google_trends', this)" class="cat-pill px-3 py-1 rounded-lg text-xs font-semibold bg-dark-900 border border-gray-800 text-gray-400 hover:text-white transition">🔥 Google Trends VN</button>
          <button onclick="filterTrendingCategory('tech_ai', this)" class="cat-pill px-3 py-1 rounded-lg text-xs font-semibold bg-dark-900 border border-gray-800 text-gray-400 hover:text-white transition">🤖 Công Nghệ & AI</button>
          <button onclick="filterTrendingCategory('science_space', this)" class="cat-pill px-3 py-1 rounded-lg text-xs font-semibold bg-dark-900 border border-gray-800 text-gray-400 hover:text-white transition">🚀 Khoa Học & Vũ Trụ</button>
          <button onclick="filterTrendingCategory('business_crypto', this)" class="cat-pill px-3 py-1 rounded-lg text-xs font-semibold bg-dark-900 border border-gray-800 text-gray-400 hover:text-white transition">💰 Kinh Doanh & Tiền Số</button>
          <button onclick="filterTrendingCategory('world_mystery', this)" class="cat-pill px-3 py-1 rounded-lg text-xs font-semibold bg-dark-900 border border-gray-800 text-gray-400 hover:text-white transition">🌍 Thế Giới & Bí Ẩn</button>
          <button onclick="filterTrendingCategory('lifestyle_viral', this)" class="cat-pill px-3 py-1 rounded-lg text-xs font-semibold bg-dark-900 border border-gray-800 text-gray-400 hover:text-white transition">✨ Đời Sống</button>
          <button onclick="filterTrendingCategory('entertainment', this)" class="cat-pill px-3 py-1 rounded-lg text-xs font-semibold bg-dark-900 border border-gray-800 text-gray-400 hover:text-white transition">🎬 Giải Trí</button>
        </div>

        <!-- Grid Danh Sách Tin Nóng -->
        <div id="trendingList" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 max-h-72 overflow-y-auto pr-1">
          <div class="text-xs text-gray-500 py-6 text-center col-span-full">Đang tải tin tức xu hướng mới nhất...</div>
        </div>

        <!-- Toast Thông Báo Đã Chọn Tin -->
        <div id="selectedTopicToast" class="hidden p-3 rounded-xl bg-dark-950 border border-emerald-500/40 text-xs text-gray-200 flex items-center justify-between"></div>
      </div>

      <!-- ==================== CẦU NỐI GOOGLE FLOW: BƯỚC 2 & BƯỚC 3 ==================== -->
      <div id="flowBridgeStep2" class="glass-card rounded-2xl p-5 border border-amber-500/30 bg-gradient-to-r from-blue-950/30 via-indigo-950/20 to-purple-950/30 space-y-4">
        <div class="flex flex-wrap justify-between items-center gap-3 border-b border-gray-800 pb-3">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-amber-500 to-rose-500 flex items-center justify-center text-white shadow-lg shadow-amber-500/20">
              <i class="fa-solid fa-bolt text-base"></i>
            </div>
            <div>
              <h2 class="text-sm font-black text-white flex items-center gap-2">
                CẦU NỐI XƯỞNG PHIM GOOGLE FLOW (VEO 2 PRO)
                <span class="px-2 py-0.5 text-[10px] uppercase font-black bg-amber-500/20 border border-amber-400/40 text-amber-300 rounded-md">Veo 2 Engine</span>
              </h2>
              <p class="text-xs text-gray-400">Sinh Prompt điện ảnh từ tin hot vừa chọn, đưa sang Google Flow dựng phim, nạp video về xưởng hậu kỳ 2 giây.</p>
            </div>
          </div>
          <a href="https://flow.google.com/project/4b843d6d-9973-4d99-afad-3a40db3b1880" target="_blank" class="px-4 py-2 rounded-xl text-xs font-bold bg-dark-850 hover:bg-dark-800 border border-gray-700 hover:border-amber-400 text-amber-300 flex items-center gap-2 transition shadow">
            <i class="fa-solid fa-arrow-up-right-from-square"></i> Mở Dự Án Google Flow (4b843d6d)
          </a>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- BƯỚC 2: SINH KỊCH BẢN & MASTER PROMPT VEO 2 -->
          <div class="bg-dark-900/80 p-4 rounded-xl border border-gray-800 space-y-3">
            <div class="flex justify-between items-center">
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded text-[10px] font-black uppercase bg-indigo-600 text-white">BƯỚC 2</span>
                <span class="text-xs font-bold text-blue-300">Sinh Kịch Bản & Master Prompt Veo 2</span>
              </div>
            </div>

            <!-- Ô nhập chủ đề (Được tự động điền từ Bước 1) -->
            <div class="space-y-2">
              <label class="text-[11px] font-semibold text-gray-400 block">Chủ đề video (bấm vào tin ở Bước 1 hoặc gõ tùy ý):</label>
              <div class="flex gap-2">
                <input type="text" id="flowTopicInput" placeholder="Ví dụ: Vụ hack tỷ USD tại Binance..." class="flex-1 bg-dark-950 border border-gray-700 focus:border-blue-500 rounded-xl px-3.5 py-2.5 text-xs text-white outline-none">
                <button id="btnGenFlowPrompt" onclick="generateGoogleFlowPrompts()" class="px-4 py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-md shadow-blue-500/20 transition flex items-center gap-1.5 shrink-0">
                  <i class="fa-solid fa-wand-magic-sparkles"></i> 🚀 Sinh Prompt Veo 2
                </button>
              </div>

              <!-- Tùy chọn thời lượng & giọng đọc -->
              <div class="grid grid-cols-3 gap-2 pt-1">
                <div>
                  <label class="text-[10px] text-gray-400 block mb-0.5">Thời lượng:</label>
                  <select id="durationSelect" class="w-full bg-dark-950 border border-gray-800 rounded-lg p-1.5 text-xs text-white">
                    <option value="short" selected>Short (30-45s)</option>
                    <option value="medium">Reels (60-90s)</option>
                    <option value="long">Phim (2-3 phút)</option>
                  </select>
                </div>
                <div>
                  <label class="text-[10px] text-gray-400 block mb-0.5">Khung hình:</label>
                  <select id="aspectSelect" class="w-full bg-dark-950 border border-gray-800 rounded-lg p-1.5 text-xs text-white">
                    <option value="9:16" selected>Dọc 9:16 (TikTok/Reels)</option>
                    <option value="16:9">Ngang 16:9 (YouTube)</option>
                  </select>
                </div>
                <div>
                  <label class="text-[10px] text-gray-400 block mb-0.5">Giọng đọc tiếng Việt:</label>
                  <select id="voiceSelect" class="w-full bg-dark-950 border border-gray-800 rounded-lg p-1.5 text-xs text-white">
                    <option value="vi-VN-HoaiMyNeural" selected>Hoài My (Nữ)</option>
                    <option value="vi-VN-NamMinhNeural">Nam Minh (Nam)</option>
                  </select>
                </div>
              </div>
            </div>

            <div id="flowPromptResultBox" class="space-y-2 pt-1">
              <div class="text-[11px] text-gray-500 italic">👉 Chọn một tin hot ở Bước 1 rồi bấm <b>"🚀 Sinh Prompt Veo 2"</b>. AI sẽ tự động đạo diễn kịch bản và góc máy điện ảnh!</div>
            </div>
          </div>

          <!-- BƯỚC 3: NẠP & GHÉP NHIỀU CẢNH GOOGLE FLOW -->
          <div class="bg-dark-900/80 p-4 rounded-xl border border-gray-800 space-y-3 flex flex-col justify-between">
            <div class="space-y-1">
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded text-[10px] font-black uppercase bg-emerald-600 text-white">BƯỚC 3</span>
                <span class="text-xs font-bold text-emerald-300">Nạp & Ghép Nhiều Cảnh Google Flow</span>
              </div>
              <p class="text-[11px] text-gray-400">Chọn cùng lúc nhiều cảnh (Cảnh 1 ➔ 5) để AI tự nhận diện thứ tự & ghép thành 1 video hoàn chỉnh.</p>
            </div>

            <!-- Dropzone Hỗ Trợ Đa File -->
            <div id="flowDropZone" class="border-2 border-dashed border-gray-700 hover:border-emerald-500/60 rounded-xl p-3.5 text-center cursor-pointer transition bg-dark-950/60" onclick="document.getElementById('flowVideoFileInput').click()">
              <input type="file" id="flowVideoFileInput" accept="video/mp4,video/quicktime,video/webm" multiple onchange="handleGoogleFlowFiles(this)" class="hidden">
              <div class="flex items-center justify-center gap-2 mb-1">
                <div class="w-8 h-8 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center text-sm shadow-inner">
                  <i class="fa-solid fa-layer-group"></i>
                </div>
                <div class="text-left">
                  <p class="text-xs font-bold text-gray-200">Kéo thả 1 hoặc NHIỀU video từ Google Flow vào đây</p>
                  <p class="text-[10px] text-gray-500">Tự động phân bổ vào Cảnh 1 ➔ 5 theo thứ tự & từ khóa kịch bản</p>
                </div>
              </div>
            </div>

            <!-- Khối Bảng Phân Cảnh (Scene Slots Board) -->
            <div id="flowScenesBox" class="space-y-2 bg-dark-950 p-3 rounded-xl border border-gray-800">
              <div class="flex justify-between items-center border-b border-gray-800/80 pb-2">
                <div class="flex items-center gap-2">
                  <span class="text-[10px] font-black px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    <span id="flowSceneCountBadge">0/5</span> PHÂN CẢNH
                  </span>
                  <span class="text-[11px] text-gray-400 font-medium">Bảng ghép nối phân cảnh</span>
                </div>
                <div class="flex items-center gap-2">
                  <button type="button" onclick="compactAndPackSceneSlots()" class="text-[11px] text-amber-400 hover:text-amber-300 flex items-center gap-1 font-semibold" title="Dồn tất cả các video đã nạp về tuần tự Cảnh 1, 2, 3...">
                    <i class="fa-solid fa-arrow-down-1-9 text-[10px]"></i> 🔄 Dồn tuần tự 1 ➔ N
                  </button>
                  <button type="button" onclick="clearFlowScenes()" class="text-[11px] text-rose-400 hover:text-rose-300 flex items-center gap-1">
                    <i class="fa-solid fa-trash-can text-[10px]"></i> Xóa hết
                  </button>
                </div>
              </div>

              <!-- List các thẻ cảnh dạng slot -->
              <div id="flowScenesList" class="space-y-1.5 max-h-56 overflow-y-auto pr-1"></div>

              <!-- Tùy chọn Nhạc Nền (BGM) & Âm Thanh -->
              <div class="flex items-center justify-between gap-2 p-2 rounded-xl bg-dark-900 border border-gray-800 text-xs">
                <div class="flex items-center gap-2">
                  <i class="fa-solid fa-music text-amber-400"></i>
                  <span class="text-gray-300 font-semibold text-[11px]">Nhạc nền (BGM):</span>
                </div>
                <select id="flowBgmSelect" class="bg-dark-950 border border-gray-700 text-amber-300 text-xs rounded-lg px-2 py-1 outline-none cursor-pointer font-medium">
                  <option value="epic" selected>⚡ Epic Cinematic (Hùng tráng)</option>
                  <option value="lofi">☕ Warm Lofi (Thư giãn, ấm áp)</option>
                  <option value="cinematic">🕵️ Dark Suspense (Kịch tính, bí ẩn)</option>
                  <option value="ambient">🎵 Chill Ambient (Êm dịu)</option>
                  <option value="synthwave">🌆 Retro Synthwave (Điện tử 80s)</option>
                  <option value="upbeat">⏩ Upbeat Tech (Năng động)</option>
                  <option value="none">🔇 Tắt nhạc nền (Chỉ giọng đọc)</option>
                </select>
              </div>

              <!-- Nút Ghép Nối -->
              <button id="btnConcatScenes" onclick="startConcatFlowScenes()" class="w-full py-2.5 rounded-xl font-bold text-xs bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-lg shadow-emerald-600/25 transition flex items-center justify-center gap-2">
                <i class="fa-solid fa-wand-magic-sparkles"></i> 🎬 Ghép Tất Cả Phân Cảnh & Khớp Sub Sang Phòng Dựng
              </button>
            </div>

            <div id="flowImportStatus" class="text-xs text-center min-h-[1.25rem] font-medium"></div>
          </div>
        </div>
      </div>

    </div>
    <!-- ==================== TAB 2: PHÒNG DỰNG HẬU KỲ (TIMELINE SUBTITLE & BGM) ==================== -->
    <div id="tabStudioView" class="hidden space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">

        <!-- CỘT TRÁI (7 CỘT): VIDEO PLAYER + OVERLAY & TIMELINE SUBTITLE EDITOR -->
        <div class="lg:col-span-7 space-y-5">
          
          <!-- Trình phát Video kèm Live CSS Subtitle Overlay -->
          <div class="glass-card rounded-2xl p-4 flex flex-col items-center justify-center relative overflow-hidden bg-dark-900 border border-gray-800">
            <div class="relative rounded-2xl overflow-hidden bg-black flex justify-center items-center shadow-2xl border border-gray-800/80" style="max-height: 460px; width: 100%;">
              <video id="studioVideo" controls class="max-h-[460px] w-auto rounded-xl" src="/video/final_reel.mp4" ontimeupdate="onStudioVideoTimeUpdate()"></video>
              
              <!-- LIVE SUBTITLE OVERLAY THEO THỜI GIAN THỰC -->
              <div id="liveSubOverlay" class="absolute pointer-events-none text-center px-4 font-bold select-none transition-all duration-75" style="top: 75%; left: 50%; transform: translate(-50%, -50%); width: 90%; text-align: center;">
                <span id="liveSubText" class="px-2 py-1 rounded inline-block text-white" style="font-size: 18px; text-shadow: 0 0 4px #000, 0 0 8px #000; white-space: pre-wrap; line-height: 1.35; word-break: break-word; text-align: center; max-width: 100%;">
                  (Bấm phát video hoặc chọn thẻ phụ đề bên dưới)
                </span>
              </div>
            </div>
            
            <div class="w-full flex justify-between items-center text-xs text-gray-400 mt-2 px-2">
              <span>Đang phát: <b id="studioPlayheadTime" class="text-blue-400 font-mono">0.00s</b></span>
              <span class="text-[11px] text-gray-500 italic">Kéo thanh trượt vị trí Y% ở cột bên phải để xem chữ nhảy trực tiếp</span>
            </div>
          </div>

          <!-- BỘ BIÊN TẬP TIMELINE PHỤ ĐỀ (GIỐNG ẢNH MẪU GOOGLE FLOW / VEED) -->
          <div class="glass-card rounded-2xl p-5 space-y-4">
            <div class="flex flex-wrap justify-between items-center gap-3 border-b border-gray-800 pb-3">
              <div class="flex items-center gap-3">
                <h3 class="text-base font-bold text-white flex items-center gap-2">
                  <i class="fa-solid fa-layer-group text-blue-400"></i> Subtitle Editor
                </h3>
                <span id="editorTimeIndicator" class="px-2.5 py-0.5 rounded-lg bg-dark-850 border border-gray-700 text-xs font-mono text-blue-300">0.00S</span>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <button type="button" id="btnSmartWrapAll" onclick="smartWrapAllSubtitles()" class="px-3 py-1.5 rounded-xl bg-purple-700 hover:bg-purple-600 text-white font-bold text-xs flex items-center gap-1.5 shadow-md shadow-purple-700/20 transition" title="Tự động ngắt các câu dài thành 2 dòng cân đối, tránh tràn mép màn hình dọc 9:16">
                  <i class="fa-solid fa-align-center"></i> ⏎ Tự Động Xuống 2 Dòng
                </button>
                <button type="button" id="btnAutoSyncScenes" onclick="autoSyncSubtitlesWithScenes()" class="px-3 py-1.5 rounded-xl bg-emerald-700 hover:bg-emerald-600 text-white font-bold text-xs flex items-center gap-1.5 shadow-md shadow-emerald-700/20 transition" title="Tự động chia thời lượng và gán lời thoại tương ứng với từng phân cảnh video">
                  <i class="fa-solid fa-wand-magic-sparkles"></i> 🎯 Khớp Chuẩn Phân Cảnh
                </button>
                <button type="button" id="btnRegenVoice" onclick="regenerateVoiceoverFromEditor()" class="px-3 py-1.5 rounded-xl bg-indigo-700 hover:bg-indigo-600 text-white font-bold text-xs flex items-center gap-1.5 shadow-md shadow-indigo-700/20 transition" title="Đọc lại giọng Voiceover khớp chuẩn theo các mốc thời gian phụ đề hiện tại">
                  <i class="fa-solid fa-microphone-lines"></i> 🎙️ Đọc Lại Voice Khớp Sub
                </button>
                <button type="button" onclick="addSubtitleSegment()" class="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-md shadow-blue-500/20 transition">
                  <i class="fa-solid fa-plus"></i> Add Segment
                </button>
              </div>
            </div>

            <!-- Danh sách thẻ Segments cuộn linh hoạt -->
            <div id="segmentsGrid" class="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[460px] overflow-y-auto pr-1">
              <div class="text-xs text-gray-500 py-6 text-center col-span-2">Đang tải các phân đoạn phụ đề...</div>
            </div>
          </div>

        </div>

        <!-- CỘT PHẢI (5 CỘT): TYPOGRAPHY, VISUAL STYLE, AUDIO REMIXER & EXPORT -->
        <div class="lg:col-span-5 space-y-5">
          
          <!-- PANEL 1: TYPOGRAPHY -->
          <div class="glass-card rounded-2xl p-5 space-y-4">
            <h3 class="text-sm font-bold text-white flex items-center gap-2 border-b border-gray-800 pb-2">
              <i class="fa-solid fa-font text-indigo-400"></i> Typography
            </h3>

            <div class="grid grid-cols-2 gap-3">
              <!-- Font Family -->
              <div>
                <label class="text-[11px] font-semibold text-gray-400 block mb-1">Font Family:</label>
                <select id="editFontFamily" onchange="applyLiveSubtitleStyles()" class="w-full bg-dark-900 border border-gray-700 rounded-xl p-2 text-xs text-white">
                  <option value="Google Sans" selected>Google Sans</option>
                  <option value="Montserrat">Montserrat</option>
                  <option value="Be Vietnam Pro">Be Vietnam Pro</option>
                  <option value="Roboto">Roboto</option>
                  <option value="Impact">Impact</option>
                  <option value="Arial">Arial</option>
                  <option value="Tahoma">Tahoma</option>
                </select>
              </div>

              <!-- Font Weight -->
              <div>
                <label class="text-[11px] font-semibold text-gray-400 block mb-1">Weight:</label>
                <select id="editFontWeight" onchange="applyLiveSubtitleStyles()" class="w-full bg-dark-900 border border-gray-700 rounded-xl p-2 text-xs text-white">
                  <option value="bold" selected>Bold</option>
                  <option value="normal">Regular</option>
                </select>
              </div>
            </div>

            <!-- Font Size Slider -->
            <div>
              <div class="flex justify-between items-center mb-1">
                <label class="text-[11px] font-semibold text-gray-400">Cỡ chữ (Size):</label>
                <span id="fontSizeDisplay" class="text-xs font-mono font-bold text-blue-400">18px</span>
              </div>
              <input type="range" id="editFontSize" min="12" max="36" value="18" oninput="applyLiveSubtitleStyles()" class="w-full h-1.5 bg-dark-900 rounded-lg cursor-pointer">
            </div>

            <!-- Căn lề phụ đề (Alignment) -->
            <div>
              <label class="text-[11px] font-semibold text-gray-400 block mb-1">Căn lề phụ đề (Alignment):</label>
              <div class="grid grid-cols-3 gap-2">
                <button type="button" id="btnAlignLeft" onclick="setTextAlignment('left')" class="py-1.5 px-2 rounded-lg text-xs font-semibold border border-gray-700 hover:border-indigo-500 text-gray-300 flex items-center justify-center gap-1.5 transition">
                  <i class="fa-solid fa-align-left"></i> Trái
                </button>
                <button type="button" id="btnAlignCenter" onclick="setTextAlignment('center')" class="py-1.5 px-2 rounded-lg text-xs font-semibold border border-indigo-500 bg-indigo-600/30 text-white flex items-center justify-center gap-1.5 transition">
                  <i class="fa-solid fa-align-center"></i> Giữa
                </button>
                <button type="button" id="btnAlignRight" onclick="setTextAlignment('right')" class="py-1.5 px-2 rounded-lg text-xs font-semibold border border-gray-700 hover:border-indigo-500 text-gray-300 flex items-center justify-center gap-1.5 transition">
                  <i class="fa-solid fa-align-right"></i> Phải
                </button>
              </div>
              <input type="hidden" id="editTextAlign" value="center">
            </div>

            <!-- Primary Text Color -->
            <div>
              <label class="text-[11px] font-semibold text-gray-400 block mb-1">Màu chữ chính:</label>
              <div class="flex items-center gap-2">
                <input type="color" id="editTextColor" value="#ffffff" onchange="applyLiveSubtitleStyles()" class="w-8 h-8 rounded-lg border-0 cursor-pointer bg-transparent">
                <div class="flex gap-1.5">
                  <button onclick="setSubTextColor('#ffffff')" class="w-6 h-6 rounded-md bg-white border border-gray-500 shadow" title="Trắng"></button>
                  <button onclick="setSubTextColor('#ffff00')" class="w-6 h-6 rounded-md bg-yellow-400 border border-gray-500 shadow" title="Vàng"></button>
                  <button onclick="setSubTextColor('#00ffff')" class="w-6 h-6 rounded-md bg-cyan-400 border border-gray-500 shadow" title="Cyan"></button>
                  <button onclick="setSubTextColor('#ff3b30')" class="w-6 h-6 rounded-md bg-rose-500 border border-gray-500 shadow" title="Đỏ neon"></button>
                </div>
              </div>
            </div>
          </div>

          <!-- PANEL 2: VISUAL STYLE & VỊ TRÍ Y% -->
          <div class="glass-card rounded-2xl p-5 space-y-4">
            <h3 class="text-sm font-bold text-white flex items-center gap-2 border-b border-gray-800 pb-2">
              <i class="fa-solid fa-wand-magic text-purple-400"></i> Visual Style
            </h3>

            <!-- Position Y Slider (Tương tự ảnh mẫu) -->
            <div>
              <div class="flex justify-between items-center mb-1">
                <label class="text-[11px] font-semibold text-gray-400">Vị trí trục dọc (Position Y):</label>
                <span id="posYDisplay" class="text-xs font-mono font-bold text-purple-400">75%</span>
              </div>
              <input type="range" id="editPosY" min="10" max="90" value="75" oninput="applyLiveSubtitleStyles()" class="w-full h-1.5 bg-dark-900 rounded-lg cursor-pointer">
              <div class="flex justify-between text-[10px] text-gray-500 mt-1">
                <span>10% (Trên cao)</span>
                <span>50% (Ở giữa)</span>
                <span>75% (Chuẩn ảnh mẫu)</span>
                <span>88% (Dưới đáy)</span>
              </div>
            </div>

            <!-- Outline Slider & Color -->
            <div>
              <div class="flex justify-between items-center mb-1">
                <label class="text-[11px] font-semibold text-gray-400">Độ dày viền (Outline):</label>
                <span id="outlineDisplay" class="text-xs font-mono font-bold text-purple-400">2px</span>
              </div>
              <div class="flex items-center gap-3">
                <input type="range" id="editOutlineSize" min="0" max="8" value="2" oninput="applyLiveSubtitleStyles()" class="w-full h-1.5 bg-dark-900 rounded-lg cursor-pointer">
                <input type="color" id="editOutlineColor" value="#000000" onchange="applyLiveSubtitleStyles()" class="w-8 h-8 rounded-lg border-0 cursor-pointer bg-transparent">
              </div>
            </div>

            <!-- Background Box & Transparency -->
            <div class="grid grid-cols-2 gap-3 items-center pt-1">
              <div class="flex items-center gap-2">
                <input type="checkbox" id="editBgBox" onchange="applyLiveSubtitleStyles()" class="w-4 h-4 rounded text-blue-600 bg-dark-900 border-gray-700">
                <label for="editBgBox" class="text-xs text-gray-300 font-semibold cursor-pointer">Dải nền mờ sau chữ</label>
              </div>
              <div>
                <div class="flex justify-between items-center mb-1">
                  <label class="text-[10px] text-gray-400">Độ mờ (Opacity):</label>
                  <span id="bgOpacityDisplay" class="text-[10px] font-mono text-gray-300">0.5</span>
                </div>
                <input type="range" id="editBgOpacity" min="0" max="1" step="0.1" value="0.5" oninput="applyLiveSubtitleStyles()" class="w-full h-1 bg-dark-900 rounded cursor-pointer">
              </div>
            </div>
          </div>

          <!-- PANEL 3: BỘ TRỘN & LỒNG NHẠC NỀN (AUDIO REMIXER) -->
          <div class="glass-card rounded-2xl p-5 space-y-4">
            <h3 class="text-sm font-bold text-white flex items-center gap-2 border-b border-gray-800 pb-2">
              <i class="fa-solid fa-music text-emerald-400"></i> Studio Audio & Music Remixer
            </h3>

            <!-- Âm lượng Giọng đọc -->
            <div>
              <div class="flex justify-between items-center mb-1">
                <label class="text-[11px] font-semibold text-gray-400">Âm lượng giọng đọc (Voice):</label>
                <span id="voiceVolDisplay" class="text-xs font-mono font-bold text-emerald-400">100%</span>
              </div>
              <input type="range" id="editVoiceVol" min="0" max="200" value="100" oninput="document.getElementById('voiceVolDisplay').innerText=this.value+'%'" class="w-full h-1.5 bg-dark-900 rounded-lg cursor-pointer">
            </div>

            <!-- Chọn bài nhạc nền -->
            <div>
              <label class="text-[11px] font-semibold text-gray-400 block mb-1">Chọn nhạc nền (BGM):</label>
              <select id="editMusicSelect" onchange="onMusicSelectChange()" class="w-full bg-dark-900 border border-gray-700 rounded-xl p-2 text-xs text-white">
                <option value="current" selected>🔁 Giữ nguyên nhạc hiện tại</option>
                <option value="epic">⚡ Epic Cinematic (Hùng tráng, dồn dập)</option>
                <option value="lofi">☕ Warm Lofi (Ấm áp, thư giãn)</option>
                <option value="synthwave">🌆 Retro Synthwave (Điện tử 80s)</option>
                <option value="cinematic">🕵️ Dark Suspense (Kịch tính, bí ẩn)</option>
                <option value="ambient">🎵 Chill Ambient (Lo-fi nhẹ nhàng)</option>
                <option value="upbeat">⏩ Upbeat Tech (Năng động, cuốn hút)</option>
                <option value="custom">📁 Tải lên file MP3 của riêng bạn...</option>
                <option value="none">🔇 Tắt nhạc nền (Chỉ giữ giọng đọc)</option>
              </select>
            </div>

            <!-- Hàng tải file MP3 tùy chỉnh -->
            <div id="customMusicRow" class="hidden bg-dark-950 p-2.5 rounded-xl border border-gray-800 space-y-2">
              <label class="text-[11px] text-gray-400 block">Tải file MP3 / WAV từ máy:</label>
              <input type="file" id="customMusicFile" accept="audio/mp3,audio/wav,audio/*" onchange="uploadCustomMusic(this)" class="text-xs text-gray-400 file:mr-2 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500">
              <div id="uploadMusicStatus" class="text-[11px] text-emerald-400 italic"></div>
            </div>

            <!-- Âm lượng nhạc nền & Ducking -->
            <div class="grid grid-cols-2 gap-3 items-center">
              <div>
                <div class="flex justify-between items-center mb-1">
                  <label class="text-[10px] text-gray-400">Âm lượng nhạc:</label>
                  <span id="musicVolDisplay" class="text-[10px] font-mono font-bold text-emerald-400">12%</span>
                </div>
                <input type="range" id="editMusicVol" min="0" max="100" value="12" oninput="document.getElementById('musicVolDisplay').innerText=this.value+'%'" class="w-full h-1 bg-dark-900 rounded cursor-pointer">
              </div>

              <div class="flex items-center gap-2 pt-2">
                <input type="checkbox" id="editDucking" checked class="w-4 h-4 rounded text-blue-600 bg-dark-900 border-gray-700">
                <label for="editDucking" class="text-xs text-gray-300 font-semibold cursor-pointer">Tự né tiếng (Ducking)</label>
              </div>
            </div>
          </div>

          <!-- PANEL 4: XUẤT VIDEO & DOWNLOADS (NHƯ ẢNH MẪU) -->
          <div class="glass-card rounded-2xl p-5 space-y-3">
            <div class="flex gap-3">
              <!-- Nút Download .SRT -->
              <button onclick="downloadSrtFile()" class="flex-1 py-3 rounded-xl font-bold text-xs bg-dark-850 hover:bg-dark-800 border border-gray-700 hover:border-blue-500 text-gray-200 flex items-center justify-center gap-2 transition">
                <i class="fa-solid fa-file-arrow-down text-blue-400"></i> Download .SRT
              </button>
              
              <!-- Nút Tải Video .MP4 -->
              <button onclick="downloadVideoFile()" class="flex-1 py-3 rounded-xl font-bold text-xs bg-dark-850 hover:bg-dark-800 border border-gray-700 hover:border-emerald-500 text-gray-200 flex items-center justify-center gap-2 transition">
                <i class="fa-solid fa-download text-emerald-400"></i> Tải Video (.MP4)
              </button>
            </div>

            <!-- Nút Export & Save Video To Lớn Nổi Bật -->
            <button id="btnExportVideo" onclick="exportPostProductionVideo()" class="w-full py-4 rounded-xl font-black text-sm bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white shadow-xl shadow-blue-500/30 flex items-center justify-center gap-2 transition">
              <i class="fa-solid fa-wand-magic-sparkles text-base"></i> EXPORT & SAVE VIDEO (Xuất Ngay 2-3s)
            </button>
            <div id="exportStatusMsg" class="text-xs text-center font-medium min-h-[1.25rem]"></div>
          </div>

        </div>

      </div>
    </div>

  </main>

  <!-- MODAL QUẢN LÝ MÔ HÌNH AI -->
  <div id="modelsModal" class="hidden fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="glass-card rounded-2xl max-w-lg w-full p-6 space-y-4 border border-gray-700">
      <div class="flex justify-between items-center border-b border-gray-800 pb-3">
        <h3 class="text-base font-bold text-white flex items-center gap-2">
          <i class="fa-solid fa-microchip text-indigo-400"></i> Quản Lý Mô Hình AI Hub
        </h3>
        <button onclick="closeModal('modelsModal')" class="text-gray-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>

      <div class="space-y-3">
        <div>
          <label class="text-xs font-semibold text-gray-300 block mb-1">Nhà cung cấp AI:</label>
          <select id="modalProviderSelect" onchange="onModalProviderChange()" class="w-full bg-dark-900 border border-gray-700 rounded-xl p-2.5 text-xs text-white">
            <option value="oxion">Oxion AI (Nhiều model Claude, DeepSeek, GPT)</option>
            <option value="gemini">Google Gemini AI Studio (Miễn phí 1500 req/ngày)</option>
            <option value="deepseek">DeepSeek API (Chính hãng V3 / R1)</option>
            <option value="groq">Groq Cloud (LPU 500 wps miễn phí)</option>
            <option value="openrouter">OpenRouter (100+ model)</option>
            <option value="openai">OpenAI (GPT-4o, GPT-4o-mini)</option>
            <option value="local">Local LLM (Ollama offline 100%)</option>
          </select>
        </div>

        <div>
          <div class="flex justify-between items-center mb-1">
            <label class="text-xs font-semibold text-gray-300">API Key (Bảo Mật & Hỗ trợ Multi-Key Pool):</label>
            <span class="text-[10px] text-amber-400 font-bold">Dán nhiều key cách nhau bằng dấu phẩy</span>
          </div>
          <div class="relative">
            <input type="password" id="modalApiKeyInput" placeholder="Dán 1 hoặc nhiều API Key (Key_1, Key_2...)..." class="w-full bg-dark-900 border border-gray-700 focus:border-blue-500 rounded-xl pl-3 pr-10 py-2.5 text-xs text-white outline-none font-mono tracking-wider">
            <button type="button" onclick="toggleApiKeyVisibility('modalApiKeyInput', this)" class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white p-1 text-xs transition" title="Ẩn/Hiện Key">
              <i class="fa-solid fa-eye-slash"></i>
            </button>
          </div>
          <p class="text-[10px] text-emerald-400 mt-1 flex items-center gap-1">
            <i class="fa-solid fa-shield-halved text-[10px]"></i> <b>Bảo mật:</b> Mặc định mã hóa ẩn dạng password. Tự động luân phiên sang Key 2 khi Key 1 hết Quota!
          </p>
        </div>

        <div>
          <label class="text-xs font-semibold text-gray-300 block mb-1">Tên Model:</label>
          <input type="text" id="modalModelInput" placeholder="gemini-3.7-flash, deepseek-chat..." class="w-full bg-dark-900 border border-gray-700 rounded-xl px-3 py-2 text-xs text-white outline-none">
        </div>

        <div id="modalTestResult" class="text-xs min-h-[1.5rem] italic"></div>
      </div>

      <div class="flex justify-end gap-2 pt-2 border-t border-gray-800">
        <button onclick="testModalProvider()" class="px-4 py-2 rounded-xl text-xs font-bold bg-dark-850 hover:bg-dark-800 text-gray-300 border border-gray-700">Kiểm Tra Key</button>
        <button onclick="saveModalProvider()" class="px-5 py-2 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white shadow">Lưu & Sử Dụng</button>
      </div>
    </div>
  </div>

  <!-- MODAL XEM TRƯỚC VIDEO PHÂN CẢNH -->
  <div id="videoPreviewModal" class="hidden fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="glass-card rounded-2xl max-w-lg w-full p-4 space-y-3 border border-gray-700 bg-dark-900 shadow-2xl">
      <div class="flex justify-between items-center pb-2 border-b border-gray-800">
        <h3 id="previewModalTitle" class="text-xs font-bold text-white flex items-center gap-2 truncate">
          <i class="fa-solid fa-play text-emerald-400"></i> Xem trước video
        </h3>
        <button onclick="closeVideoPreview()" class="text-gray-400 hover:text-white p-1 text-sm"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="rounded-xl overflow-hidden bg-black flex justify-center items-center" style="max-height: 420px;">
        <video id="previewModalPlayer" controls autoplay class="max-h-[400px] w-auto rounded-lg"></video>
      </div>
      <div class="flex justify-end pt-1">
        <button onclick="closeVideoPreview()" class="px-4 py-1.5 rounded-lg text-xs font-bold bg-dark-800 hover:bg-gray-700 text-gray-300">Đóng</button>
      </div>
    </div>
  </div>

  <!-- JAVASCRIPT ĐIỀU KHIỂN TOÀN BỘ HỆ THỐNG -->
  <script>
    let SUBTITLE_SEGMENTS = [];
    let CURRENT_PROVIDERS_CFG = null;
    let IS_POLLING_PROGRESS = false;

    // Khởi tạo trang web
    window.addEventListener('DOMContentLoaded', () => {
      fetchSystemStatus();
      loadEditorData();
      restoreSavedFlowPrompts();
      fetchTrendingTopics(false); // Ưu tiên load từ cache localStorage, KHÔNG gọi API thừa!
      renderFlowScenesUI();
    });

    // Chuyển đổi Tab Chính (Factory vs Studio)
    function toggleApiKeyVisibility(inputId, btn) {
      const input = document.getElementById(inputId);
      if (!input) return;
      const isPass = (input.type === 'password');
      input.type = isPass ? 'text' : 'password';
      const icon = btn.querySelector('i');
      if (icon) {
        icon.className = isPass ? 'fa-solid fa-eye' : 'fa-solid fa-eye-slash';
      }
    }

    function switchMainTab(tab) {
      const facView = document.getElementById('tabFactoryView');
      const stuView = document.getElementById('tabStudioView');
      const btnFac = document.getElementById('btnTabFactory');
      const btnStu = document.getElementById('btnTabStudio');

      if (tab === 'studio') {
        if (facView) facView.classList.add('hidden');
        if (stuView) stuView.classList.remove('hidden');
        if (btnFac) {
          btnFac.className = 'px-5 py-2 rounded-xl text-sm font-bold text-gray-400 hover:text-white flex items-center gap-2 transition-all';
        }
        if (btnStu) {
          btnStu.className = 'px-5 py-2 rounded-xl text-sm font-bold bg-gradient-to-r from-amber-500 to-rose-500 text-white shadow-lg shadow-amber-500/25 flex items-center gap-2 transition-all';
        }
        loadEditorData();
      } else {
        if (stuView) stuView.classList.add('hidden');
        if (facView) facView.classList.remove('hidden');
        if (btnStu) {
          btnStu.className = 'px-5 py-2 rounded-xl text-sm font-bold text-gray-400 hover:text-white flex items-center gap-2 transition-all';
        }
        if (btnFac) {
          btnFac.className = 'px-5 py-2 rounded-xl text-sm font-bold bg-blue-600 text-white shadow-lg shadow-blue-600/30 flex items-center gap-2 transition-all';
        }
        const concatBtn = document.getElementById('btnConcatScenes');
        if (concatBtn) {
          concatBtn.disabled = false;
          concatBtn.classList.remove('opacity-50');
        }
      }
    }

    function updateFlowScenePrompt(sceneNum, newPrompt) {
      sceneNum = parseInt(sceneNum, 10);
      if (window.LATEST_FLOW_SCENES) {
        const sc = window.LATEST_FLOW_SCENES.find(s => s.scene_num === sceneNum);
        if (sc) {
          sc.flow_prompt = newPrompt;
        }
      }
    }

    function renderFlowPromptsResult(data) {
      const box = document.getElementById('flowPromptResultBox');
      if (!box || !data || !data.scenes) return;
      window.LATEST_FLOW_MASTER_PROMPT = data.master_prompt;
      window.LATEST_FLOW_SCENES = data.scenes || [];
      renderFlowScenesUI();

      let scenesHtml = data.scenes.map(s => `
        <div class="p-2.5 rounded-xl bg-dark-950 border border-gray-800 space-y-1.5 hover:border-blue-500/40 transition">
          <div class="flex justify-between items-center">
            <span class="text-[11px] font-black text-amber-400">Cảnh ${s.scene_num} <span class="text-gray-400 font-normal">(${(s.camera || '').split(',')[0]})</span></span>
            <button type="button" onclick="copyToClipboard('${(s.flow_prompt || '').replace(/'/g, "\\'")}', this)" class="text-[10px] px-2 py-0.5 rounded bg-dark-850 hover:bg-gray-700 text-gray-300 border border-gray-700 transition">Copy</button>
          </div>
          ${s.narration ? `<p class="text-[11px] text-gray-300 bg-dark-900/80 p-1.5 rounded border border-gray-800/80 leading-relaxed"><span class="text-amber-400 font-semibold">🎙️ Lời đọc (${s.narration.split(' ').length} từ):</span> ${s.narration}</p>` : ''}
          <div>
            <span class="text-[10px] text-emerald-400 font-semibold block mb-0.5"><i class="fa-solid fa-video text-[9px] mr-1"></i>Prompt Veo 2 (tiếng Anh điện ảnh):</span>
            <textarea onchange="updateFlowScenePrompt(${s.scene_num}, this.value)" rows="2" class="w-full bg-dark-900 border border-gray-700 rounded-lg p-1.5 text-[11px] text-gray-200 font-mono focus:border-blue-500 outline-none resize-none leading-relaxed">${s.flow_prompt || ''}</textarea>
          </div>
        </div>
      `).join('');

      box.innerHTML = `
        <div class="space-y-2">
          <div class="flex justify-between items-center">
            <span class="text-[11px] font-bold text-white">Đã sinh ${data.scenes.length} phân cảnh Veo 2:</span>
            <button onclick="copyToClipboard(window.LATEST_FLOW_MASTER_PROMPT, this)" class="px-2.5 py-1 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white flex items-center gap-1 shadow">
              <i class="fa-solid fa-copy"></i> Copy Toàn Bộ Prompt
            </button>
          </div>
          <div class="max-h-64 overflow-y-auto space-y-2 pr-1">
            ${scenesHtml}
          </div>
          <div class="text-[10px] text-emerald-400 italic">✅ Giọng đọc & phụ đề tiếng Việt đã sẵn sàng! Sang Bước 3 bên phải nạp video.</div>
        </div>
      `;
    }

    function restoreSavedFlowPrompts() {
      try {
        const savedTopic = localStorage.getItem('flow_saved_topic');
        if (savedTopic) {
          const inFlow = document.getElementById('flowTopicInput');
          const inMain = document.getElementById('topicInput');
          if (inFlow) inFlow.value = savedTopic;
          if (inMain) inMain.value = savedTopic;
          const toast = document.getElementById('selectedTopicToast');
          if (toast) {
            toast.innerHTML = `<span class="text-emerald-400 font-bold"><i class="fa-solid fa-circle-check"></i> ĐÃ CHỌN:</span> "${savedTopic}" <span class="text-gray-400">(Khôi phục từ phiên làm việc trước)</span>`;
            toast.classList.remove('hidden');
          }
        }
        const savedPrompts = localStorage.getItem('flow_saved_prompts');
        if (savedPrompts) {
          const data = JSON.parse(savedPrompts);
          if (data && data.scenes && data.scenes.length > 0) {
            renderFlowPromptsResult(data);
          }
        }
      } catch (e) {
        console.error("Lỗi khôi phục prompts:", e);
      }
    }
    
    // ================= XỬ LÝ GOOGLE FLOW BRIDGE =================
    async function generateGoogleFlowPrompts() {
      const flowIn = document.getElementById('flowTopicInput');
      const topic = (flowIn && flowIn.value.trim()) || document.getElementById('topicInput').value.trim() || 'Bí mật công nghệ tương lai';
      const duration = document.getElementById('durationSelect').value;
      const aspect = document.getElementById('aspectSelect').value;
      const voice = document.getElementById('voiceSelect').value;

      const btn = document.getElementById('btnGenFlowPrompt');
      const box = document.getElementById('flowPromptResultBox');
      const origHtml = btn.innerHTML;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang tạo...';
      btn.disabled = true;

      try {
        const res = await fetch('/api/flow_generate_prompts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            topic: topic,
            duration_mode: duration,
            aspect_ratio: aspect,
            voice: voice
          })
        });
        const data = await res.json();
        if (data.status === 'success') {
          localStorage.setItem('flow_saved_prompts', JSON.stringify(data));
          localStorage.setItem('flow_saved_topic', topic);
          renderFlowPromptsResult(data);
        } else {
          box.innerHTML = `<div class="text-xs text-rose-400">Lỗi: ${data.message || 'Không thể tạo'}</div>`;
        }
      } catch (err) {
        box.innerHTML = `<div class="text-xs text-rose-400">Lỗi kết nối: ${err}</div>`;
      } finally {
        btn.innerHTML = origHtml;
        btn.disabled = false;
      }
    }

    function copyToClipboard(text, btn) {
      navigator.clipboard.writeText(text);
      const origText = btn.innerText;
      btn.innerText = 'Đã Copy!';
      btn.classList.add('bg-emerald-600', 'text-white');
      setTimeout(() => {
        btn.innerText = origText;
        btn.classList.remove('bg-emerald-600');
      }, 1500);
    }

    // ================= QUẢN LÝ PHÂN CẢNH GHÉP NỐI THÔNG MINH (FLOW SCENE ENGINE) =================
    let flowSceneSlots = {}; // { [slotNum]: { file: File, reason: string, previewUrl: string } }
    let draggedSlotNum = null;

    function getActiveFlowScenes() {
      if (window.LATEST_FLOW_SCENES && window.LATEST_FLOW_SCENES.length > 0) {
        return window.LATEST_FLOW_SCENES;
      }
      return [
        { scene_num: 1, camera: 'Cận cảnh mở đầu (Hook)', flow_prompt: '', sub_vi: '' },
        { scene_num: 2, camera: 'Trung cảnh chi tiết (Setup)', flow_prompt: '', sub_vi: '' },
        { scene_num: 3, camera: 'Góc máy đặc tả (Detail)', flow_prompt: '', sub_vi: '' },
        { scene_num: 4, camera: 'Toàn cảnh mở rộng (Action)', flow_prompt: '', sub_vi: '' },
        { scene_num: 5, camera: 'Góc máy kết thúc (Call to Action)', flow_prompt: '', sub_vi: '' }
      ];
    }

    const FLOW_STOP_WORDS = new Set([
      'video', 'mp4', 'mov', 'webm', 'clip', 'cinematic', 'shot', 'camera', 'lens', 
      'lighting', 'photorealistic', 'ultra', '4k', '8k', 'uhd', 'render', 'veo', 'veo2', 
      'google', 'flow', 'generated', 'final', 'download', 'the', 'and', 'with', 'for', 
      'scene', 'canh', 'phan', 'part', 'export', 'output', 'preview', 'scaled', 'trimmed',
      '35mm', 'bokeh', 'resolution', 'hyperrealistic', 'high', 'quality', 'style', 'real',
      'shallow', 'depth', 'of', 'field', 'fps', 'hd'
    ]);

    function getCleanTokens(str) {
      if (!str) return [];
      return str.toLowerCase()
        .replace(/[^a-z0-9à-ỹ]/gi, ' ')
        .split(/\s+/)
        .filter(w => w.length > 2 && !FLOW_STOP_WORDS.has(w));
    }

    function getExplicitNum(filename, totalSlots) {
      const clean = filename.toLowerCase();
      const m1 = clean.match(/(?:scene|canh|part|shot|phân cảnh|c|s)[\s_\-]*(\d+)/i);
      if (m1) {
        const n = parseInt(m1[1], 10);
        if (n >= 1 && n <= totalSlots) return n;
      }
      const m2 = clean.match(/[\(\[\-_\s](\d+)[\)\]\s\._]/);
      if (m2) {
        const n = parseInt(m2[1], 10);
        if (n >= 1 && n <= totalSlots) return n;
      }
      const m3 = clean.match(/(\d+)\.[a-z0-9]+$/i);
      if (m3) {
        const n = parseInt(m3[1], 10);
        if (n >= 1 && n <= totalSlots) return n;
      }
      return null;
    }

    function handleGoogleFlowFiles(input) {
      if (!input.files || input.files.length === 0) return;
      const files = Array.from(input.files);
      assignMultipleFilesToScenes(files);
      input.value = '';
    }

    function compactAndPackSceneSlots() {
      const currentSlots = Object.keys(flowSceneSlots)
        .map(k => parseInt(k, 10))
        .filter(k => flowSceneSlots[k] && flowSceneSlots[k].file)
        .sort((a, b) => a - b);
      
      if (currentSlots.length === 0) {
        alert("Chưa có video nào để sắp xếp!");
        return;
      }

      const newSlots = {};
      currentSlots.forEach((oldSlot, idx) => {
        const newSlot = idx + 1;
        newSlots[newSlot] = flowSceneSlots[oldSlot];
        newSlots[newSlot].reason = 'Đã dồn tuần tự vào Cảnh ' + newSlot;
      });

      flowSceneSlots = newSlots;
      renderFlowScenesUI();
    }

    function assignMultipleFilesToScenes(newFiles) {
      if (!newFiles || newFiles.length === 0) return;
      const scenes = getActiveFlowScenes();
      const totalSlots = Math.max(scenes.length, 5);

      // Sắp xếp tự nhiên theo tên (ví dụ: scene_1, scene_2 hoặc 1.mp4, 2.mp4...)
      const filesList = Array.from(newFiles);
      filesList.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }));

      // Bước 1: Nhận diện các file có số cảnh tường minh (Cảnh 1..5, scene 1, 1.mp4...)
      const unassignedFiles = [];
      const assignedSlots = new Set();

      filesList.forEach(file => {
        const expNum = getExplicitNum(file.name, Math.max(totalSlots, filesList.length));
        if (expNum && !flowSceneSlots[expNum]) {
          assignFileToSpecificSlot(expNum, file, 'Khớp số thứ tự file (Cảnh ' + expNum + ')');
          assignedSlots.add(expNum);
        } else {
          unassignedFiles.push(file);
        }
      });

      // Bước 2: Các file còn lại TUYỆT ĐỐI KHÔNG DÙNG SO KHỚP TỪ KHÓA ĐỂ ĐẢO VỊ TRÍ!
      // Gán tuần tự 100% từ Cảnh 1 trở đi vào các ô còn trống theo đúng thứ tự file nạp vào!
      let curSlot = 1;
      unassignedFiles.forEach((file) => {
        while (flowSceneSlots[curSlot] && flowSceneSlots[curSlot].file) {
          curSlot++;
        }
        assignFileToSpecificSlot(curSlot, file, 'Nạp tuần tự vào Cảnh ' + curSlot);
        assignedSlots.add(curSlot);
        curSlot++;
      });

      renderFlowScenesUI();
    }

    function assignFileToSpecificSlot(slotNum, file, reason) {
      if (!file) return;
      slotNum = parseInt(slotNum, 10);
      flowSceneSlots[slotNum] = {
        file: file,
        reason: reason || ('Gán thủ công vào Cảnh ' + slotNum),
        previewUrl: URL.createObjectURL(file)
      };
      renderFlowScenesUI();
    }

    function swapSceneSlots(slotA, slotB) {
      slotA = parseInt(slotA, 10);
      slotB = parseInt(slotB, 10);
      if (slotA === slotB) return;

      const temp = flowSceneSlots[slotA];
      flowSceneSlots[slotA] = flowSceneSlots[slotB];
      flowSceneSlots[slotB] = temp;

      if (flowSceneSlots[slotA]) {
        flowSceneSlots[slotA].reason = 'Đã chuyển sang Cảnh ' + slotA;
      }
      if (flowSceneSlots[slotB]) {
        flowSceneSlots[slotB].reason = 'Đã chuyển sang Cảnh ' + slotB;
      }

      renderFlowScenesUI();
    }

    function moveSceneSlot(slotNum, direction) {
      slotNum = parseInt(slotNum, 10);
      const scenes = getActiveFlowScenes();
      const maxSlots = Math.max(scenes.length, Object.keys(flowSceneSlots).length, 5);
      const targetSlot = slotNum + direction;
      if (targetSlot < 1 || targetSlot > maxSlots) return;
      swapSceneSlots(slotNum, targetSlot);
    }

    function reassignSlot(fromSlot, toSlot) {
      fromSlot = parseInt(fromSlot, 10);
      toSlot = parseInt(toSlot, 10);
      if (fromSlot === toSlot) return;
      swapSceneSlots(fromSlot, toSlot);
    }

    function promptChangeSlotVideo(slotNum) {
      let fileIn = document.getElementById('slotFileInput_' + slotNum);
      if (!fileIn) {
        fileIn = document.createElement('input');
        fileIn.type = 'file';
        fileIn.id = 'slotFileInput_' + slotNum;
        fileIn.accept = 'video/mp4,video/quicktime,video/webm';
        fileIn.className = 'hidden';
        document.body.appendChild(fileIn);
      }
      fileIn.onchange = (e) => {
        if (e.target.files && e.target.files[0]) {
          assignFileToSpecificSlot(slotNum, e.target.files[0], 'Người dùng tự chọn video cho Cảnh ' + slotNum);
        }
      };
      fileIn.click();
    }

    function clearSlotVideo(slotNum) {
      slotNum = parseInt(slotNum, 10);
      if (flowSceneSlots[slotNum]) {
        delete flowSceneSlots[slotNum];
        renderFlowScenesUI();
      }
    }

    function clearFlowScenes() {
      flowSceneSlots = {};
      renderFlowScenesUI();
    }

    // Video preview modal
    function previewSlotVideo(slotNum) {
      const slot = flowSceneSlots[slotNum];
      if (!slot || !slot.file) return;
      const modal = document.getElementById('videoPreviewModal');
      const player = document.getElementById('previewModalPlayer');
      const title = document.getElementById('previewModalTitle');
      if (!modal || !player) return;

      if (!slot.previewUrl) {
        slot.previewUrl = URL.createObjectURL(slot.file);
      }
      player.src = slot.previewUrl;
      if (title) title.innerHTML = `<i class="fa-solid fa-play text-emerald-400"></i> Xem trước Cảnh ${slotNum}: ${slot.file.name}`;
      modal.classList.remove('hidden');
      player.play().catch(e => console.log('Autoplay handled:', e));
    }

    function closeVideoPreview() {
      const modal = document.getElementById('videoPreviewModal');
      const player = document.getElementById('previewModalPlayer');
      if (player) {
        player.pause();
        player.src = '';
      }
      if (modal) modal.classList.add('hidden');
    }

    // HTML5 Drag and Drop Handlers for Scene Cards
    function onSceneDragStart(e, slotNum) {
      draggedSlotNum = slotNum;
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', slotNum);
      const card = document.getElementById('sceneCard_' + slotNum);
      if (card) card.classList.add('opacity-40');
    }

    function onSceneDragEnd(e, slotNum) {
      draggedSlotNum = null;
      const card = document.getElementById('sceneCard_' + slotNum);
      if (card) card.classList.remove('opacity-40');
    }

    function onSceneDragOver(e, slotNum) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      const card = document.getElementById('sceneCard_' + slotNum);
      if (card) card.classList.add('border-emerald-400', 'bg-emerald-950/40');
    }

    function onSceneDragLeave(e, slotNum) {
      e.preventDefault();
      const card = document.getElementById('sceneCard_' + slotNum);
      if (card) card.classList.remove('border-emerald-400', 'bg-emerald-950/40');
    }

    function onSceneDrop(e, targetSlotNum) {
      e.preventDefault();
      const card = document.getElementById('sceneCard_' + targetSlotNum);
      if (card) card.classList.remove('border-emerald-400', 'bg-emerald-950/40');

      // 1. Người dùng thả file trực tiếp từ máy tính vào thẻ cảnh này
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        const droppedFiles = Array.from(e.dataTransfer.files);
        if (droppedFiles.length === 1) {
          assignFileToSpecificSlot(targetSlotNum, droppedFiles[0], 'Kéo thả trực tiếp vào Cảnh ' + targetSlotNum);
          return;
        } else {
          assignMultipleFilesToScenes(droppedFiles);
          return;
        }
      }

      // 2. Kéo thả hoán đổi vị trí giữa 2 cảnh trong danh sách
      if (draggedSlotNum && draggedSlotNum !== targetSlotNum) {
        swapSceneSlots(draggedSlotNum, targetSlotNum);
      }
    }

    function renderSceneSelectOptions(currentVal, totalCount) {
      let opts = '';
      for (let i = 1; i <= totalCount; i++) {
        opts += `<option value="${i}" ${i === currentVal ? 'selected' : ''}>Cảnh ${i}</option>`;
      }
      return opts;
    }

    function updateSceneAudioMode(slotNum, mode) {
      slotNum = parseInt(slotNum, 10);
      if (flowSceneSlots[slotNum]) {
        flowSceneSlots[slotNum].audioMode = mode;
      }
    }

    function renderFlowScenesUI() {
      const box = document.getElementById('flowScenesBox');
      const list = document.getElementById('flowScenesList');
      const badge = document.getElementById('flowSceneCountBadge');
      if (!list) return;

      const scenes = getActiveFlowScenes();
      const totalSlots = Math.max(scenes.length, Object.keys(flowSceneSlots).length, 5);
      
      let filledCount = 0;
      let slotsHtml = '';

      for (let i = 1; i <= totalSlots; i++) {
        const slot = flowSceneSlots[i];
        const sc = scenes.find(s => s.scene_num === i);
        const cameraTitle = sc ? sc.camera.split(',')[0] : ('Phân cảnh ' + i);
        const subPreview = sc && sc.sub_vi ? sc.sub_vi : '';

        if (slot && slot.file) {
          filledCount++;
          const mbSize = (slot.file.size / (1024 * 1024)).toFixed(1);
          const currentAudioMode = slot.audioMode || 'bgm';
          slotsHtml += `
            <div id="sceneCard_${i}" draggable="true" ondragstart="onSceneDragStart(event, ${i})" ondragend="onSceneDragEnd(event, ${i})" ondragover="onSceneDragOver(event, ${i})" ondragleave="onSceneDragLeave(event, ${i})" ondrop="onSceneDrop(event, ${i})" class="p-2.5 rounded-xl bg-dark-900 border border-emerald-500/50 hover:border-emerald-400 space-y-1.5 shadow-sm transition-all cursor-grab active:cursor-grabbing">
              <div class="flex items-center justify-between gap-1.5">
                <div class="flex items-center gap-1.5 min-w-0">
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-black bg-emerald-600/30 text-emerald-400 border border-emerald-500/50 shrink-0">CẢNH ${i}</span>
                  <select onchange="reassignSlot(${i}, this.value)" class="bg-dark-950 border border-gray-700 text-gray-300 text-[10px] rounded px-1 py-0.5 outline-none cursor-pointer shrink-0" title="Chuyển sang cảnh khác">
                    ${renderSceneSelectOptions(i, totalSlots)}
                  </select>
                  <select onchange="updateSceneAudioMode(${i}, this.value)" class="bg-dark-950 border border-amber-500/50 text-amber-300 text-[10px] rounded px-1 py-0.5 outline-none cursor-pointer shrink-0 font-medium" title="Tùy chọn âm thanh cảnh này">
                    <option value="bgm" ${currentAudioMode === 'bgm' ? 'selected' : ''}>🎵 Nhạc BGM chung</option>
                    <option value="original" ${currentAudioMode === 'original' ? 'selected' : ''}>🔊 Giữ tiếng gốc clip</option>
                    <option value="mute" ${currentAudioMode === 'mute' ? 'selected' : ''}>🔇 Tắt âm clip gốc</option>
                  </select>
                  <span class="text-xs text-gray-200 font-semibold truncate" title="${slot.file.name}">
                    <i class="fa-solid fa-file-video text-emerald-400 mr-1"></i>${slot.file.name}
                  </span>
                  <span class="text-[10px] text-gray-500 font-mono shrink-0">${mbSize} MB</span>
                </div>
                <div class="flex items-center gap-1 shrink-0">
                  <button type="button" onclick="previewSlotVideo(${i})" class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-dark-800 hover:bg-emerald-600 text-emerald-400 hover:text-white border border-emerald-500/30 transition" title="Xem trước video này">
                    <i class="fa-solid fa-play text-[9px]"></i>
                  </button>
                  <button type="button" onclick="moveSceneSlot(${i}, -1)" ${i === 1 ? 'disabled' : ''} class="px-1.5 py-0.5 rounded text-[10px] bg-dark-800 hover:bg-gray-700 text-gray-300 disabled:opacity-25 disabled:hover:bg-dark-800 border border-gray-700 transition" title="Đổi lên trên">▲</button>
                  <button type="button" onclick="moveSceneSlot(${i}, 1)" ${i === totalSlots ? 'disabled' : ''} class="px-1.5 py-0.5 rounded text-[10px] bg-dark-800 hover:bg-gray-700 text-gray-300 disabled:opacity-25 disabled:hover:bg-dark-800 border border-gray-700 transition" title="Đổi xuống dưới">▼</button>
                  <button type="button" onclick="promptChangeSlotVideo(${i})" class="px-1.5 py-0.5 rounded text-[10px] bg-dark-800 hover:bg-blue-600 text-blue-300 hover:text-white border border-blue-500/30 transition" title="Đổi video khác cho cảnh này">
                    <i class="fa-solid fa-arrows-rotate text-[9px]"></i>
                  </button>
                  <button type="button" onclick="clearSlotVideo(${i})" class="px-1.5 py-0.5 rounded text-[10px] bg-dark-800 hover:bg-rose-600 text-rose-400 hover:text-white border border-rose-500/30 transition" title="Gỡ video khỏi cảnh này">
                    <i class="fa-solid fa-xmark text-[9px]"></i>
                  </button>
                </div>
              </div>
              <div class="flex items-center justify-between text-[10px] text-gray-400 pt-0.5">
                <div class="text-emerald-400/90 font-mono truncate flex items-center gap-1">
                  <i class="fa-solid fa-sparkles text-[9px]"></i> ${slot.reason || 'Đã gán cho Cảnh ' + i}
                </div>
                ${subPreview ? `<span class="text-gray-500 italic truncate ml-2 text-[9px] max-w-[45%]">"${subPreview}"</span>` : ''}
              </div>
            </div>
          `;
        } else {
          // Ô trống chưa nạp video
          slotsHtml += `
            <div id="sceneCard_${i}" ondragover="onSceneDragOver(event, ${i})" ondragleave="onSceneDragLeave(event, ${i})" ondrop="onSceneDrop(event, ${i})" class="p-2 rounded-xl bg-dark-900/40 border border-dashed border-gray-700 hover:border-emerald-500/60 transition-all flex items-center justify-between gap-2">
              <div class="flex items-center gap-2 min-w-0">
                <span class="px-1.5 py-0.5 rounded text-[10px] font-black bg-gray-800 text-gray-400 border border-gray-700 shrink-0">CẢNH ${i}</span>
                <div class="min-w-0">
                  <span class="text-xs text-gray-400 font-semibold truncate block">${cameraTitle}</span>
                  ${subPreview ? `<span class="text-[10px] text-gray-500 truncate block">"${subPreview.slice(0, 38)}..."</span>` : '<span class="text-[10px] text-gray-600 italic">Chưa nạp video</span>'}
                </div>
              </div>
              <div class="flex items-center gap-1 shrink-0">
                <button type="button" onclick="promptChangeSlotVideo(${i})" class="px-2 py-0.5 rounded text-[10px] font-bold bg-dark-800 hover:bg-emerald-600 border border-gray-700 hover:border-emerald-500 text-gray-300 hover:text-white transition flex items-center gap-1">
                  <i class="fa-solid fa-plus text-[9px]"></i> Chọn Video
                </button>
              </div>
            </div>
          `;
        }
      }

      list.innerHTML = slotsHtml;
      if (badge) badge.innerText = `${filledCount}/${totalSlots}`;

      const concatBtn = document.getElementById('btnConcatScenes');
      if (concatBtn) {
        concatBtn.disabled = false;
        concatBtn.classList.remove('opacity-50');
      }
    }

    async function startConcatFlowScenes() {
      const scenes = getActiveFlowScenes();
      const totalSlots = Math.max(scenes.length, Object.keys(flowSceneSlots).length, 5);

      const filledSlots = [];
      for (let i = 1; i <= totalSlots; i++) {
        if (flowSceneSlots[i] && flowSceneSlots[i].file) {
          filledSlots.push({ slotNum: i, ...flowSceneSlots[i] });
        }
      }

      if (filledSlots.length === 0) {
        alert("Vui lòng nạp ít nhất 1 video phân cảnh trước khi ghép!");
        return;
      }

      const btn = document.getElementById('btnConcatScenes');
      const statusEl = document.getElementById('flowImportStatus');
      btn.disabled = true;
      btn.classList.add('opacity-50');

      statusEl.className = 'text-xs text-center font-bold text-blue-400';
      statusEl.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang đọc ' + filledSlots.length + ' video phân cảnh...';

      try {
        const videoPayloads = [];
        for (let i = 0; i < filledSlots.length; i++) {
          const item = filledSlots[i];
          const sc = scenes.find(s => s.scene_num === item.slotNum);
          statusEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang nạp Cảnh ${item.slotNum} (${item.file.name})...`;
          const b64 = await readFileAsBase64(item.file);
          videoPayloads.push({
            filename: item.file.name,
            base64: b64,
            scene_num: item.slotNum,
            narration: sc ? (sc.narration || sc.sub_vi || '') : '',
            camera: sc ? (sc.camera || '') : '',
            prompt: sc ? (sc.flow_prompt || '') : '',
            audio_mode: item.audioMode || 'bgm'
          });
        }

        statusEl.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles fa-spin"></i> Đang ghép nối ' + videoPayloads.length + ' cảnh, hòa âm nhạc nền & đồng bộ phụ đề...';

        const aspect = document.getElementById('aspectSelect') ? document.getElementById('aspectSelect').value : '9:16';
        const voice = document.getElementById('voiceSelect') ? document.getElementById('voiceSelect').value : 'vi-VN-HoaiMyNeural';
        const bgmChoice = document.getElementById('flowBgmSelect') ? document.getElementById('flowBgmSelect').value : 'epic';

        const res = await fetch('/api/flow_concat_videos', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            videos: videoPayloads,
            aspect_ratio: aspect,
            voice: voice,
            music_choice: bgmChoice
          })
        });

        const data = await res.json();
        if (data.status === 'success') {
          statusEl.className = 'text-xs text-center font-bold text-emerald-400';
          statusEl.innerText = '🎉 ' + data.message;
          setTimeout(() => {
            switchToStudioWithVideo(data.segments);
          }, 1000);
        } else {
          statusEl.className = 'text-xs text-center font-bold text-rose-400';
          statusEl.innerText = '❌ ' + (data.message || 'Lỗi ghép video');
        }
      } catch (err) {
        statusEl.className = 'text-xs text-center font-bold text-rose-400';
        statusEl.innerText = '❌ Lỗi kết nối: ' + err;
      } finally {
        btn.disabled = false;
        btn.classList.remove('opacity-50');
        btn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> 🎬 Ghép Lại Các Phân Cảnh & Khớp Sub Sang Phòng Dựng';
      }
    }

    function readFileAsBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    }

    // Thiết lập kéo thả file trực tiếp vào DropZone chính
    document.addEventListener('DOMContentLoaded', () => {
      const dz = document.getElementById('flowDropZone');
      if (dz) {
        dz.addEventListener('dragover', (e) => {
          e.preventDefault();
          dz.classList.add('border-emerald-400', 'bg-emerald-950/20');
        });
        dz.addEventListener('dragleave', (e) => {
          e.preventDefault();
          dz.classList.remove('border-emerald-400', 'bg-emerald-950/20');
        });
        dz.addEventListener('drop', (e) => {
          e.preventDefault();
          dz.classList.remove('border-emerald-400', 'bg-emerald-950/20');
          if (e.dataTransfer && e.dataTransfer.files) {
            assignMultipleFilesToScenes(Array.from(e.dataTransfer.files));
          }
        });
      }
    });

    function switchToStudioWithVideo(customSegments) {
      switchMainTab('studio');
      const stVid = document.getElementById('studioVideo');
      if (stVid) {
        stVid.src = '/video/final_reel.mp4?t=' + Date.now();
        stVid.load();
      }
      if (customSegments && customSegments.length > 0) {
        SUBTITLE_SEGMENTS = customSegments;
        renderSubtitleSegments();
        applyLiveSubtitleStyles();
      } else {
        setTimeout(() => {
          loadEditorData();
        }, 200);
      }
    }

    // Tải dữ liệu phòng dựng Hậu Kỳ
    async function loadEditorData() {
      try {
        const res = await fetch('/api/editor_data');
        const data = await res.json();
        if (data.status === 'success') {
          SUBTITLE_SEGMENTS = data.segments || [];
          renderSubtitleSegments();
          applyLiveSubtitleStyles();
          if (data.video_url) {
            const stVid = document.getElementById('studioVideo');
            if (!stVid.src || stVid.src.endsWith('/')) {
              stVid.src = data.video_url;
            }
          }
        }
      } catch (e) {
        console.error("Lỗi nạp editor data:", e);
      }
    }

    // Render danh sách các thẻ Subtitle Segment (Khớp theo từng phân cảnh)
    function renderSubtitleSegments() {
      const container = document.getElementById('segmentsGrid');
      if (!SUBTITLE_SEGMENTS || SUBTITLE_SEGMENTS.length === 0) {
        container.innerHTML = '<div class="text-xs text-gray-500 py-6 text-center col-span-2">Chưa có phụ đề nào. Nhấn "+ Add Segment" hoặc "🎯 Khớp Chuẩn Phân Cảnh" để thêm tự động!</div>';
        return;
      }

      let html = '';
      SUBTITLE_SEGMENTS.forEach((seg, idx) => {
        const sceneLabel = seg.sceneNum || (idx + 1);
        html += `
          <div id="segCard_${seg.id}" class="seg-card glass-card rounded-xl p-3 bg-dark-850 space-y-2 cursor-pointer border border-gray-800/80 hover:border-blue-500/50 transition-all" onclick="seekToSegment(${seg.start}, ${seg.id})">
            <div class="flex justify-between items-center text-xs">
              <div class="flex items-center gap-1.5 font-mono text-gray-300">
                <span class="px-1.5 py-0.5 rounded text-[10px] font-black bg-blue-900/60 text-blue-300 border border-blue-700/50">CẢNH ${sceneLabel}</span>
                <input type="number" step="0.1" value="${seg.start}" onchange="updateSegTime(${seg.id}, 'start', this.value)" class="w-14 bg-dark-900 border border-gray-700 rounded px-1.5 py-0.5 text-center text-blue-300 text-xs">
                <span class="text-gray-500">→</span>
                <input type="number" step="0.1" value="${seg.end}" onchange="updateSegTime(${seg.id}, 'end', this.value)" class="w-14 bg-dark-900 border border-gray-700 rounded px-1.5 py-0.5 text-center text-indigo-300 text-xs">
                <span class="text-[10px] text-gray-500">(${(seg.end - seg.start).toFixed(1)}s)</span>
              </div>
              <div class="flex items-center gap-1">
                <button type="button" onclick="event.stopPropagation(); smartWrapSingleSeg(${seg.id})" class="text-[10px] px-2 py-0.5 rounded bg-gray-800 hover:bg-purple-900/60 hover:text-purple-300 text-gray-300 border border-gray-700 transition" title="Ngắt câu này thành 2 dòng cân đối">
                  ⏎ 2 Dòng
                </button>
                <button onclick="event.stopPropagation(); deleteSegment(${seg.id})" class="text-gray-500 hover:text-rose-400 p-1 transition" title="Xóa thẻ này">
                  <i class="fa-solid fa-trash-can text-xs"></i>
                </button>
              </div>
            </div>
            <textarea rows="3" oninput="updateSegText(${seg.id}, this.value)" placeholder="Nhập phụ đề... (Bấm Enter để xuống dòng tùy ý)" class="w-full bg-dark-900 border border-gray-800 focus:border-blue-500 rounded-lg p-2 text-xs text-white outline-none resize-y font-sans font-medium">${seg.text}</textarea>
          </div>
        `;
      });
      container.innerHTML = html;
    }

    // Tự động căn phụ đề khớp 100% theo các phân cảnh video
    async function autoSyncSubtitlesWithScenes() {
      const vid = document.getElementById('studioVideo');
      const totalDur = (vid && !isNaN(vid.duration) && vid.duration > 1) ? vid.duration : 25.0;

      let scenes = window.LATEST_FLOW_SCENES || [];
      if (scenes.length === 0) {
        try {
          const saved = localStorage.getItem('flow_saved_prompts');
          if (saved) {
            const data = JSON.parse(saved);
            scenes = data.scenes || [];
          }
        } catch (e) {}
      }

      const numScenes = scenes.length > 0 ? scenes.length : 5;
      const segDur = totalDur / numScenes;

      SUBTITLE_SEGMENTS = [];
      for (let i = 0; i < numScenes; i++) {
        const sc = scenes[i] || {};
        const sTime = parseFloat((i * segDur).toFixed(2));
        const eTime = parseFloat(((i + 1) * segDur).toFixed(2));
        const text = (sc.narration || sc.sub_vi || sc.flow_prompt || `Phân cảnh ${i + 1}`).trim();

        SUBTITLE_SEGMENTS.push({
          id: i + 1,
          start: sTime,
          end: eTime,
          text: text,
          sceneNum: i + 1
        });
      }

      renderSubtitleSegments();
      applyLiveSubtitleStyles();

      try {
        await fetch('/api/save_subtitles', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ segments: SUBTITLE_SEGMENTS })
        });
        alert(`🎯 Đã căn chỉnh ${numScenes} phân đoạn phụ đề khớp 100% theo mốc thời gian của từng cảnh video!`);
      } catch (e) {
        console.error("Lỗi lưu sub:", e);
      }
    }

    // Đọc lại giọng đọc Voiceover đồng bộ theo các mốc phụ đề hiện tại
    async function regenerateVoiceoverFromEditor() {
      if (!SUBTITLE_SEGMENTS || SUBTITLE_SEGMENTS.length === 0) {
        alert("Chưa có phân đoạn phụ đề nào để đọc!");
        return;
      }
      const btn = document.getElementById('btnRegenVoice');
      const origHtml = btn ? btn.innerHTML : '';
      if (btn) {
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang đọc lại...';
        btn.disabled = true;
      }

      try {
        const voice = document.getElementById('voiceSelect') ? document.getElementById('voiceSelect').value : 'vi-VN-HoaiMyNeural';
        const res = await fetch('/api/sync_subtitles_tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ segments: SUBTITLE_SEGMENTS, voice: voice })
        });
        const data = await res.json();
        if (data.status === 'success') {
          const stVid = document.getElementById('studioVideo');
          if (stVid) {
            stVid.src = data.video_url;
            stVid.load();
            stVid.play();
          }
          alert("🎉 " + data.message);
        } else {
          alert("❌ " + (data.message || 'Lỗi sinh voiceover'));
        }
      } catch (err) {
        alert("❌ Lỗi kết nối: " + err);
      } finally {
        if (btn) {
          btn.innerHTML = origHtml;
          btn.disabled = false;
        }
      }
    }

    function updateSegTime(id, key, val) {
      const seg = SUBTITLE_SEGMENTS.find(s => s.id === id);
      if (seg) {
        seg[key] = parseFloat(val) || 0;
      }
    }

    function updateSegText(id, val) {
      const seg = SUBTITLE_SEGMENTS.find(s => s.id === id);
      if (seg) {
        seg.text = val;
        applyLiveSubtitleStyles();
      }
    }

    function addSubtitleSegment() {
      const vid = document.getElementById('studioVideo');
      let curTime = (vid && !isNaN(vid.currentTime)) ? vid.currentTime : 0.0;
      
      const lastSeg = SUBTITLE_SEGMENTS[SUBTITLE_SEGMENTS.length - 1];
      let start = (curTime > 0.1) ? parseFloat(curTime.toFixed(2)) : (lastSeg ? lastSeg.end : 0.0);
      let end = parseFloat((start + 2.0).toFixed(2));

      const newId = (SUBTITLE_SEGMENTS.length ? Math.max(...SUBTITLE_SEGMENTS.map(s => s.id || 0)) : 0) + 1;
      const newSeg = {
        id: newId,
        start: start,
        end: end,
        text: "Nội dung phụ đề mới"
      };

      SUBTITLE_SEGMENTS.push(newSeg);
      SUBTITLE_SEGMENTS.sort((a, b) => a.start - b.start);
      renderSubtitleSegments();

      // Cuộn và focus trực tiếp vào ô nhập phụ đề của thẻ mới tạo
      setTimeout(() => {
        const newCard = document.getElementById('segCard_' + newId);
        if (newCard) {
          newCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
          highlightActiveCard(newId);
          const txt = newCard.querySelector('textarea');
          if (txt) {
            txt.focus();
            txt.select();
          }
        }
      }, 60);
    }
    window.addSubtitleSegment = addSubtitleSegment;
    window.addSegment = addSubtitleSegment;

    function deleteSegment(id) {
      SUBTITLE_SEGMENTS = SUBTITLE_SEGMENTS.filter(s => s.id !== id);
      renderSubtitleSegments();
    }

    function seekToSegment(startTime, id) {
      const vid = document.getElementById('studioVideo');
      vid.currentTime = startTime;
      vid.play();
      highlightActiveCard(id);
    }

    function highlightActiveCard(id) {
      document.querySelectorAll('.seg-card').forEach(el => el.classList.remove('active-seg'));
      const activeEl = document.getElementById('segCard_' + id);
      if (activeEl) {
        activeEl.classList.add('active-seg');
      }
    }

    // Khi Video Play, cập nhật Playhead & Đồng bộ Overlay
    function onStudioVideoTimeUpdate() {
      const vid = document.getElementById('studioVideo');
      const curTime = vid.currentTime;
      document.getElementById('studioPlayheadTime').innerText = curTime.toFixed(2) + 's';
      document.getElementById('editorTimeIndicator').innerText = curTime.toFixed(2) + 'S';

      // Tìm segment tương ứng
      const activeSeg = SUBTITLE_SEGMENTS.find(s => curTime >= s.start && curTime <= s.end);
      const subOverlayText = document.getElementById('liveSubText');
      if (activeSeg) {
        subOverlayText.innerText = activeSeg.text;
        subOverlayText.style.display = 'inline-block';
        highlightActiveCard(activeSeg.id);
      } else {
        if (SUBTITLE_SEGMENTS.length > 0) {
          subOverlayText.innerText = '';
          subOverlayText.style.display = 'none';
        }
      }
    }

    function smartWrapText(text) {
      if (!text) return "";
      if (text.includes("\n")) return text;
      const words = text.trim().split(/\s+/);
      if (words.length <= 5) return text;
      const mid = Math.ceil(words.length / 2);
      return words.slice(0, mid).join(" ") + "\n" + words.slice(mid).join(" ");
    }

    function smartWrapSingleSeg(id) {
      const seg = SUBTITLE_SEGMENTS.find(s => s.id === id);
      if (seg) {
        seg.text = smartWrapText(seg.text);
        renderSubtitleSegments();
        applyLiveSubtitleStyles();
      }
    }

    function smartWrapAllSubtitles() {
      if (!SUBTITLE_SEGMENTS || SUBTITLE_SEGMENTS.length === 0) return;
      SUBTITLE_SEGMENTS.forEach(seg => {
        seg.text = smartWrapText(seg.text);
      });
      renderSubtitleSegments();
      applyLiveSubtitleStyles();
    }

    function setTextAlignment(align) {
      const inp = document.getElementById('editTextAlign');
      if (inp) inp.value = align;
      ['btnAlignLeft', 'btnAlignCenter', 'btnAlignRight'].forEach(btnId => {
        const b = document.getElementById(btnId);
        if (!b) return;
        b.classList.remove('border-indigo-500', 'bg-indigo-600/30', 'text-white');
        b.classList.add('border-gray-700', 'text-gray-300');
      });
      const activeBtn = document.getElementById(
        align === 'left' ? 'btnAlignLeft' : (align === 'right' ? 'btnAlignRight' : 'btnAlignCenter')
      );
      if (activeBtn) {
        activeBtn.classList.remove('border-gray-700', 'text-gray-300');
        activeBtn.classList.add('border-indigo-500', 'bg-indigo-600/30', 'text-white');
      }
      applyLiveSubtitleStyles();
    }

    // Áp dụng Style lên Live Subtitle Overlay theo thời gian thực (CSS)
    function applyLiveSubtitleStyles() {
      const overlay = document.getElementById('liveSubOverlay');
      const textSpan = document.getElementById('liveSubText');

      const fontFam = document.getElementById('editFontFamily').value;
      const fontWt = document.getElementById('editFontWeight').value;
      const fontSize = document.getElementById('editFontSize').value;
      const fontColor = document.getElementById('editTextColor').value;
      const posY = document.getElementById('editPosY').value;
      const outlineSize = document.getElementById('editOutlineSize').value;
      const outlineColor = document.getElementById('editOutlineColor').value;
      const isBgBox = document.getElementById('editBgBox').checked;
      const bgOpacity = document.getElementById('editBgOpacity').value;

      // Cập nhật nhãn hiển thị số
      document.getElementById('fontSizeDisplay').innerText = fontSize + 'px';
      document.getElementById('posYDisplay').innerText = posY + '%';
      document.getElementById('outlineDisplay').innerText = outlineSize + 'px';
      document.getElementById('bgOpacityDisplay').innerText = bgOpacity;

      // Cập nhật vị trí Y%
      overlay.style.top = posY + '%';

      // Cập nhật font chữ & màu sắc
      textSpan.style.fontFamily = fontFam + ', sans-serif';
      textSpan.style.fontWeight = (fontWt === 'bold') ? '800' : '500';
      textSpan.style.fontSize = fontSize + 'px';
      textSpan.style.color = fontColor;

      // Căn lề text (Left, Center, Right)
      const textAlign = (document.getElementById('editTextAlign') ? document.getElementById('editTextAlign').value : 'center') || 'center';
      overlay.style.textAlign = textAlign;
      textSpan.style.textAlign = textAlign;

      // Outline hiệu ứng
      if (parseInt(outlineSize) > 0) {
        textSpan.style.textShadow = `
          -${outlineSize}px -${outlineSize}px 0 ${outlineColor},
           ${outlineSize}px -${outlineSize}px 0 ${outlineColor},
          -${outlineSize}px  ${outlineSize}px 0 ${outlineColor},
           ${outlineSize}px  ${outlineSize}px 0 ${outlineColor},
           0 2px 8px rgba(0,0,0,0.8)
        `;
      } else {
        textSpan.style.textShadow = 'none';
      }

      // Background Box
      if (isBgBox) {
        textSpan.style.backgroundColor = `rgba(0, 0, 0, ${bgOpacity})`;
        textSpan.style.padding = '4px 10px';
        textSpan.style.borderRadius = '6px';
      } else {
        textSpan.style.backgroundColor = 'transparent';
        textSpan.style.padding = '0';
      }
    }

    function setSubTextColor(hex) {
      document.getElementById('editTextColor').value = hex;
      applyLiveSubtitleStyles();
    }

    function onMusicSelectChange() {
      const choice = document.getElementById('editMusicSelect').value;
      const customRow = document.getElementById('customMusicRow');
      if (choice === 'custom') {
        customRow.classList.remove('hidden');
      } else {
        customRow.classList.add('hidden');
      }
    }

    // Tải lên MP3 tùy chỉnh
    function uploadCustomMusic(input) {
      if (!input.files || !input.files[0]) return;
      const file = input.files[0];
      const reader = new FileReader();
      const statusEl = document.getElementById('uploadMusicStatus');
      statusEl.innerText = 'Đang tải file...';

      reader.onload = async (e) => {
        try {
          const b64 = e.target.result;
          const res = await fetch('/api/upload_music', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ music_base64: b64 })
          });
          const data = await res.json();
          if (data.status === 'success') {
            statusEl.innerText = '✅ Đã tải file: ' + file.name;
          } else {
            statusEl.innerText = '❌ Lỗi: ' + data.message;
          }
        } catch (err) {
          statusEl.innerText = '❌ Lỗi tải lên: ' + err;
        }
      };
      reader.readAsDataURL(file);
    }

    // Nút Xuất Video Hậu Kỳ Siêu Tốc (2-3 Giây)
    async function exportPostProductionVideo() {
      const btn = document.getElementById('btnExportVideo');
      const statusEl = document.getElementById('exportStatusMsg');
      const origHtml = btn.innerHTML;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> ĐANG REMIX AUDIO & ÉP SUB (2-3 GIÂY)...';
      btn.disabled = true;
      statusEl.className = 'text-xs text-center font-medium text-blue-400';
      statusEl.innerText = 'Hệ thống đang xử lý FFmpeg...';

      const payload = {
        segments: SUBTITLE_SEGMENTS,
        font_name: document.getElementById('editFontFamily').value,
        font_size: parseInt(document.getElementById('editFontSize').value),
        font_bold: (document.getElementById('editFontWeight').value === 'bold'),
        primary_color: document.getElementById('editTextColor').value,
        outline_color: document.getElementById('editOutlineColor').value,
        outline_size: parseInt(document.getElementById('editOutlineSize').value),
        position_y: parseFloat(document.getElementById('editPosY').value),
        align_mode: document.getElementById('editTextAlign') ? document.getElementById('editTextAlign').value : 'center',
        bg_box: document.getElementById('editBgBox').checked,
        bg_opacity: parseFloat(document.getElementById('editBgOpacity').value),
        music_choice: document.getElementById('editMusicSelect').value,
        voice_volume: parseFloat(document.getElementById('editVoiceVol').value),
        music_volume: parseFloat(document.getElementById('editMusicVol').value),
        audio_ducking: document.getElementById('editDucking').checked,
        aspect_ratio: document.getElementById('aspectSelect').value
      };

      try {
        const res = await fetch('/api/export_remix', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === 'success') {
          statusEl.className = 'text-xs text-center font-bold text-emerald-400';
          statusEl.innerText = '🎉 XUẤT VIDEO THÀNH CÔNG! Đã nạp video mới vào trình phát.';
          const stVid = document.getElementById('studioVideo');
          stVid.src = data.video_url;
          stVid.load();
          stVid.play();
        } else {
          statusEl.className = 'text-xs text-center font-bold text-rose-400';
          statusEl.innerText = '❌ Lỗi xuất video: ' + (data.message || 'Gặp sự cố FFmpeg');
        }
      } catch (err) {
        statusEl.className = 'text-xs text-center font-bold text-rose-400';
        statusEl.innerText = '❌ Lỗi kết nối: ' + err;
      } finally {
        btn.innerHTML = origHtml;
        btn.disabled = false;
      }
    }

    function downloadSrtFile() {
      window.location.href = '/api/download_srt';
    }

    function downloadVideoFile() {
      window.location.href = '/api/download_video';
    }

    // ================= XỬ LÝ TAB 1: XƯỞNG AI TỰ ĐỘNG =================
    async function startGeneration() {
      const topic = document.getElementById('topicInput').value.trim();
      const script = document.getElementById('scriptInput').value.trim();
      const duration = document.getElementById('durationSelect').value;
      const aspect = document.getElementById('aspectSelect').value;
      const engine = document.getElementById('engineSelect').value;
      const voice = document.getElementById('voiceSelect').value;

      const btn = document.getElementById('btnStartGenerate');
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> ĐANG SẢN XUẤT TOÀN QUY TRÌNH...';

      try {
        const res = await fetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            topic: topic,
            script: script,
            duration_mode: duration,
            aspect_ratio: aspect,
            engine: engine,
            voice: voice,
            sub_position: 'bottom'
          })
        });
        const data = await res.json();
        if (data.status === 'started') {
          pollProgress();
        } else {
          alert("Lỗi: " + (data.error || 'Không thể bắt đầu'));
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-play"></i> BẮT ĐẦU TẠO VIDEO 1-CLICK';
        }
      } catch (e) {
        alert("Lỗi kết nối: " + e);
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-play"></i> BẮT ĐẦU TẠO VIDEO 1-CLICK';
      }
    }

    function pollProgress() {
      if (IS_POLLING_PROGRESS) return;
      IS_POLLING_PROGRESS = true;
      const interval = setInterval(async () => {
        try {
          const res = await fetch('/api/progress');
          const data = await res.json();
          
          document.getElementById('stepNameLabel').innerText = data.step_name || 'Đang xử lý...';
          document.getElementById('progressPercent').innerText = data.progress + '%';
          document.getElementById('progressBar').style.width = data.progress + '%';

          if (data.logs && data.logs.length > 0) {
            const consoleEl = document.getElementById('logConsole');
            consoleEl.innerHTML = data.logs.map(l => `<div>${l}</div>`).join('');
            consoleEl.scrollTop = consoleEl.scrollHeight;
          }

          if (!data.is_running && data.progress >= 100) {
            clearInterval(interval);
            IS_POLLING_PROGRESS = false;
            const btn = document.getElementById('btnStartGenerate');
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-play"></i> BẮT ĐẦU TẠO VIDEO 1-CLICK';
            
            // Cập nhật video preview
            if (data.result && data.result.video_url) {
              const facVid = document.getElementById('factoryVideoPreview');
              facVid.src = data.result.video_url;
              facVid.load();
            }
          } else if (!data.is_running && data.error) {
            clearInterval(interval);
            IS_POLLING_PROGRESS = false;
            const btn = document.getElementById('btnStartGenerate');
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-play"></i> BẮT ĐẦU TẠO VIDEO 1-CLICK';
          }
        } catch (e) {
          console.error(e);
        }
      }, 1500);
    }

    let ALL_TRENDING_TOPICS = [];

    async function fetchTrendingTopics(force = false) {
      const container = document.getElementById('trendingList');
      const countLabel = document.getElementById('trendingCountLabel');

      // 1. Kiểm tra cache localStorage nếu không phải bấm nút ép cào lại (Tránh gọi API liên tục lãng phí tài nguyên)
      if (!force) {
        try {
          const cached = localStorage.getItem('cached_trending_topics');
          const cachedTime = localStorage.getItem('cached_trending_time');
          // TTL 1 tiếng (3600000 ms)
          if (cached && cachedTime && (Date.now() - parseInt(cachedTime, 10) < 3600000)) {
            const list = JSON.parse(cached);
            if (list && list.length > 0) {
              ALL_TRENDING_TOPICS = list;
              if (countLabel) countLabel.innerText = list.length + ' tin nóng (Đã lưu cache)';
              renderTrendingList(list);
              return; // Dừng ngay, KHÔNG gọi API thừa!
            }
          }
        } catch (e) {}
      }

      if (container) {
        container.innerHTML = '<div class="text-xs text-blue-400 py-6 text-center col-span-full"><i class="fa-solid fa-spinner fa-spin text-base mb-1"></i><br>Đang cào dữ liệu tin tức nóng đa kênh (Google Trends, VNExpress...)...</div>';
      }
      try {
        const res = await fetch('/api/trending_all');
        const data = await res.json();
        const list = data.topics || data.trends || [];
        ALL_TRENDING_TOPICS = list;
        if (countLabel) countLabel.innerText = list.length + ' tin nóng';
        localStorage.setItem('cached_trending_topics', JSON.stringify(list));
        localStorage.setItem('cached_trending_time', Date.now().toString());
        renderTrendingList(list);
      } catch (e) {
        if (container) container.innerHTML = '<div class="text-xs text-rose-400 py-4 text-center col-span-full">Lỗi cào tin tức: ' + e + '</div>';
      }
    }

    function renderTrendingList(list, filterCat = 'all') {
      const container = document.getElementById('trendingList');
      if (!container) return;

      const filtered = (filterCat === 'all') ? list : list.filter(t => t.category_key === filterCat);

      if (!filtered || filtered.length === 0) {
        container.innerHTML = '<div class="text-xs text-gray-500 py-4 text-center col-span-full">Không có tin tức nào trong mục này.</div>';
        return;
      }

      container.innerHTML = filtered.map(t => {
        const safeTitle = t.title.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        return `
          <div onclick="selectTrendingTopic('${safeTitle}', this)" class="trend-card p-3 rounded-xl bg-dark-900 hover:bg-dark-850 border border-gray-800 hover:border-amber-400/80 cursor-pointer flex flex-col justify-between transition group shadow-sm">
            <div class="space-y-1">
              <div class="flex justify-between items-center gap-2">
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">${t.category || 'Tin hot'}</span>
                <span class="text-[10px] text-gray-500 group-hover:text-amber-400 transition"><i class="fa-solid fa-arrow-down text-[9px]"></i> Chọn tin này</span>
              </div>
              <h4 class="text-xs font-bold text-gray-200 group-hover:text-white line-clamp-2">${t.title}</h4>
            </div>
            ${t.snippet ? `<p class="text-[11px] text-gray-400 line-clamp-2 mt-1.5 italic">${t.snippet}</p>` : ''}
          </div>
        `;
      }).join('');
    }

    function filterTrendingCategory(catKey, btn) {
      document.querySelectorAll('.cat-pill').forEach(b => {
        b.className = 'cat-pill px-3 py-1 rounded-lg text-xs font-semibold bg-dark-900 border border-gray-800 text-gray-400 hover:text-white transition';
      });
      btn.className = 'cat-pill px-3 py-1 rounded-lg text-xs font-bold bg-amber-500 text-dark-950 border border-amber-400 shadow-sm transition';
      renderTrendingList(ALL_TRENDING_TOPICS, catKey);
    }

    function selectTrendingTopic(title, el) {
      document.querySelectorAll('.trend-card').forEach(c => c.classList.remove('border-emerald-500', 'bg-emerald-950/20'));
      if (el) el.classList.add('border-emerald-500', 'bg-emerald-950/20');
      
      const inFlow = document.getElementById('flowTopicInput');
      const inMain = document.getElementById('topicInput');
      if (inFlow) inFlow.value = title;
      if (inMain) inMain.value = title;

      const toast = document.getElementById('selectedTopicToast');
      if (toast) {
        toast.innerHTML = `<span class="text-emerald-400 font-bold"><i class="fa-solid fa-circle-check"></i> ĐÃ CHỌN:</span> "${title}" <span class="text-gray-400">(Sẵn sàng sinh kịch bản ở Bước 2 bên dưới)</span>`;
        toast.classList.remove('hidden');
      }

      const step2 = document.getElementById('flowBridgeStep2');
      if (step2) step2.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function setTopic(val) {
      document.getElementById('topicInput').value = val;
    }

    function openOutputDir() {
      fetch('/api/open_folder', { method: 'POST' });
    }

    async function shutdownApp() {
      if (confirm("Bạn có chắc chắn muốn tắt ứng dụng toàn diện (dừng server và mọi tiến trình FFmpeg)?")) {
        await fetch('/api/shutdown', { method: 'POST' });
        document.body.innerHTML = `
          <div class="min-h-screen flex flex-col items-center justify-center bg-black text-white p-6 space-y-4 text-center">
            <div class="w-16 h-16 rounded-full bg-emerald-600/20 text-emerald-400 flex items-center justify-center text-3xl">
              <i class="fa-solid fa-check"></i>
            </div>
            <h2 class="text-xl font-bold">Ứng Dụng Đã Tắt Hoàn Toàn!</h2>
            <p class="text-sm text-gray-400">Tất cả tiến trình ngầm đã được đóng an toàn. Bạn có thể đóng tab trình duyệt này.</p>
          </div>
        `;
      }
    }

    // ================= QUẢN LÝ MÔ HÌNH AI =================
    async function fetchSystemStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        document.getElementById('activeModelLabel').innerText = (data.active_provider || 'AI') + ' • ' + (data.active_model || 'Model');
      } catch (e) {}
    }

    function openModal(id) {
      document.getElementById(id).classList.remove('hidden');
      loadModalProviders();
    }
    function closeModal(id) {
      document.getElementById(id).classList.add('hidden');
    }

    async function loadModalProviders() {
      const res = await fetch('/api/providers');
      CURRENT_PROVIDERS_CFG = await res.json();
      const ap = CURRENT_PROVIDERS_CFG.active_provider || 'oxion';
      document.getElementById('modalProviderSelect').value = ap;
      onModalProviderChange();
    }

    function onModalProviderChange() {
      if (!CURRENT_PROVIDERS_CFG) return;
      const pid = document.getElementById('modalProviderSelect').value;
      const p = CURRENT_PROVIDERS_CFG.providers[pid] || {};
      document.getElementById('modalApiKeyInput').value = p.api_key || '';
      document.getElementById('modalModelInput').value = p.selected_model || '';
      document.getElementById('modalTestResult').innerText = '';
    }

    async function testModalProvider() {
      const pid = document.getElementById('modalProviderSelect').value;
      const p = (CURRENT_PROVIDERS_CFG && CURRENT_PROVIDERS_CFG.providers[pid]) || {};
      const key = document.getElementById('modalApiKeyInput').value;
      const model = document.getElementById('modalModelInput').value;
      const resultEl = document.getElementById('modalTestResult');
      resultEl.className = 'text-xs italic text-blue-400';
      resultEl.innerText = 'Đang kiểm tra kết nối...';

      try {
        const res = await fetch('/api/test_provider', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ base_url: p.base_url || '', api_key: key, model: model })
        });
        const data = await res.json();
        if (data.status === 'success') {
          resultEl.className = 'text-xs italic text-emerald-400 font-bold';
        } else {
          resultEl.className = 'text-xs italic text-rose-400 font-bold';
        }
        resultEl.innerText = data.message;
      } catch (err) {
        resultEl.className = 'text-xs italic text-rose-400';
        resultEl.innerText = 'Lỗi kết nối: ' + err;
      }
    }

    async function saveModalProvider() {
      const pid = document.getElementById('modalProviderSelect').value;
      const key = document.getElementById('modalApiKeyInput').value;
      const model = document.getElementById('modalModelInput').value;
      const p = (CURRENT_PROVIDERS_CFG && CURRENT_PROVIDERS_CFG.providers[pid]) || {};

      try {
        await fetch('/api/save_provider', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider_id: pid,
            api_key: key,
            model: model,
            base_url: p.base_url || '',
            set_active: true
          })
        });
        fetchSystemStatus();
        closeModal('modelsModal');
      } catch (err) {
        alert("Lỗi lưu provider: " + err);
      }
    }
  </script>
</body>
</html>
"""

def main():
    server_address = ('', PORT)
    httpd = ThreadingHTTPServer(server_address, StudioRequestHandler)
    print(f"============================================================")
    print(f"🎬 AI VIDEO FACTORY STUDIO PRO (GOOGLE FLOW ENGINE)")
    print(f"👉 Địa chỉ Web UI: http://127.0.0.1:{PORT}")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nĐang tắt server...")
        kill_all_subprocesses()
        httpd.server_close()

if __name__ == "__main__":
    main()
