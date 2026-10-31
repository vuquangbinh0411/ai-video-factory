#!/usr/bin/env python3
"""
scripts/generate_music.py
Nhiệm vụ: Tạo đoạn nhạc nền 60s phù hợp với không khí kịch bản Reels.
Mô hình: Giả lập / tích hợp chuẩn giao thức ACE-Step 1.5 Music Generation,
kèm bộ sinh âm nhạc Synth Ambient bằng FFmpeg (hoàn toàn miễn phí, 0 đồng, không cần API key).
"""

import sys
import os
import json
import argparse
import logging
import subprocess
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
    from dotenv import load_dotenv
    ROOT_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    ROOT_DIR = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger("generate_music")

ACE_STEP_API_URL = os.getenv("ACE_STEP_API_URL", "")
ACE_STEP_API_KEY = os.getenv("ACE_STEP_API_KEY", "")
TEMP_DIR = Path(os.getenv("SHARED_MEDIA_DIR", str(ROOT_DIR / "shared_media"))) / "temp"

def call_ace_step_api(prompt: str, duration: int, output_path: Path) -> bool:
    """Gọi API ACE-Step 1.5 nếu người dùng cấu hình Endpoint & Key"""
    if not ACE_STEP_API_URL or not ACE_STEP_API_KEY:
        return False

    logger.info(f"Đang gửi yêu cầu sinh nhạc tới ACE-Step 1.5 API: {ACE_STEP_API_URL}")
    payload = {
        "model": "ace-step-1.5",
        "prompt": prompt,
        "duration": duration,
        "format": "mp3",
        "sample_rate": 44100
    }
    headers = {
        "Authorization": f"Bearer {ACE_STEP_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(ACE_STEP_API_URL, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            if "audio/mpeg" in response.headers.get("Content-Type", ""):
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return True
            data = response.json()
            if "audio_url" in data:
                audio_res = requests.get(data["audio_url"], timeout=30)
                with open(output_path, "wb") as f:
                    f.write(audio_res.content)
                return True
    except Exception as e:
        logger.warning(f"ACE-Step 1.5 API gặp sự cố hoặc timeout ({e}). Kích hoạt bộ sinh nhạc Fallback 0 đồng.")
    return False

def generate_offline_synth_track(duration: int, output_path: Path, genre: str = "ambient") -> bool:
    """
    Tạo đoạn nhạc nền Synth đa thể loại bằng FFmpeg Audio Engine (0 đồng, không bản quyền).
    Thể loại hỗ trợ: ambient, epic, lofi, synthwave, cinematic, upbeat
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Đang sinh nhạc nền thể loại '{genre}' ({duration}s) bằng FFmpeg...")

    fade_out_start = max(1, duration - 4)

    genre = genre.lower().strip()
    if genre == "epic":
        # 85 BPM, Heavy sub bass (D1=36.7Hz) + Cinematic War Tom Pulse + Brass horn drone
        expr = (
            "0.14*sin(2*PI*36.7*t)*(0.7+0.3*sin(0.1*PI*t))"
            "+0.10*sin(2*PI*73.4*t)*(0.5+0.5*sin(0.2*PI*t))"
            "+0.09*sin(2*PI*110*t)*exp(-3*mod(t,0.70))"  # War drum kick
            "+0.07*sin(2*PI*146.8*t)*(0.5+0.5*sin(0.15*PI*t))"
            "+0.04*sin(2*PI*220*t)*(0.4+0.6*sin(0.08*PI*t))"
            "+0.03*sin(2*PI*440*t)*exp(-6*mod(t,0.35))"  # Accent hit
        )
        lpf, hpf, vol = "2500", "25", "0.90"
    elif genre == "lofi":
        # 75 BPM, Warm Rhodes chords (Am9, Dm7) + mellow kick + vinyl texture
        expr = (
            "0.09*sin(2*PI*55*t)*(0.6+0.4*sin(0.05*PI*t))"
            "+0.08*sin(2*PI*110*t)*(0.5+0.5*sin(0.1*PI*t))"
            "+0.07*sin(2*PI*164.8*t)*(0.5+0.5*sin(0.12*PI*t))"
            "+0.06*sin(2*PI*220*t)*(0.5+0.5*sin(0.08*PI*t))"
            "+0.05*sin(2*PI*261.6*t)*(0.4+0.6*sin(0.15*PI*t))"
            "+0.05*sin(2*PI*50*t)*exp(-6*mod(t,0.80))"   # Soft lofi kick
            "+0.01*sin(2*PI*9000*t)*exp(-20*mod(t,0.40))" # Soft hat
        )
        lpf, hpf, vol = "1800", "40", "0.80"
    elif genre == "synthwave":
        # 115 BPM, 80s driving bass octaves + bright arpeggio
        expr = (
            "0.11*sin(2*PI*65.4*t)*(0.6+0.4*sin(2*PI*1.9*t))"
            "+0.09*sin(2*PI*130.8*t)*(0.5+0.5*sin(2*PI*3.8*t))"
            "+0.07*sin(2*PI*261.6*t)*(0.5+0.5*sin(2*PI*7.6*t))"
            "+0.06*sin(2*PI*392*t)*(0.4+0.6*sin(2*PI*3.8*t))"
            "+0.07*sin(2*PI*60*t)*exp(-7*mod(t,0.52))"   # 4-on-the-floor kick
            "+0.02*sin(2*PI*7000*t)*exp(-25*mod(t,0.26))" # Snare/hat
        )
        lpf, hpf, vol = "3200", "30", "0.85"
    elif genre == "cinematic":
        # Dark mystery suspense drone + evolving sub harmonic
        expr = (
            "0.12*sin(2*PI*43.65*t)*(0.6+0.4*sin(0.06*PI*t))"
            "+0.09*sin(2*PI*65.4*t)*(0.5+0.5*sin(0.09*PI*t))"
            "+0.06*sin(2*PI*130.8*t)*(0.5+0.5*sin(0.14*PI*t))"
            "+0.05*sin(2*PI*196*t)*(0.5+0.5*sin(0.08*PI*t))"
            "+0.04*sin(2*PI*311.1*t)*(0.3+0.7*sin(0.05*PI*t))"
            "+0.03*sin(2*PI*40*t)*exp(-2*mod(t,2.0))"     # Tension heartbeat
        )
        lpf, hpf, vol = "2200", "20", "0.85"
    elif genre == "upbeat":
        # Fast rhythmic tech groove
        expr = (
            "0.10*sin(2*PI*65.4*t)*(0.5+0.5*sin(2*PI*2.0*t))"
            "+0.08*sin(2*PI*130.8*t)*(0.5+0.5*sin(2*PI*4.0*t))"
            "+0.06*sin(2*PI*261.6*t)*(0.4+0.6*sin(2*PI*8.0*t))"
            "+0.07*sin(2*PI*55*t)*exp(-8*mod(t,0.45))"
            "+0.02*sin(2*PI*6000*t)*exp(-28*mod(t,0.225))"
        )
        lpf, hpf, vol = "3500", "35", "0.85"
    else:  # Ambient (mặc định)
        expr = (
            "0.10*sin(2*PI*55*t)*(0.6+0.4*sin(0.08*PI*t))"
            "+0.08*sin(2*PI*65.41*t)*(0.5+0.5*sin(0.12*PI*t))"
            "+0.07*sin(2*PI*130.81*t)*(0.5+0.5*sin(0.18*PI*t))"
            "+0.06*sin(2*PI*164.81*t)*(0.5+0.5*sin(0.22*PI*t))"
            "+0.05*sin(2*PI*196.00*t)*(0.5+0.5*sin(0.28*PI*t))"
            "+0.04*sin(2*PI*246.94*t)*(0.5+0.5*sin(0.15*PI*t))"
            "+0.025*sin(2*PI*523.25*t)*(0.3+0.7*sin(1.5*PI*t))"
            "+0.020*sin(2*PI*659.26*t)*(0.3+0.7*sin(1.8*PI*t))"
            "+0.04*sin(2*PI*50*t)*exp(-5*mod(t,0.75))"
            "+0.012*sin(2*PI*8000*t)*exp(-30*mod(t,0.375))"
        )
        lpf, hpf, vol = "2000", "30", "0.85"

    filter_expr = (
        f"aevalsrc=exprs='{expr}':s=44100:d={duration},"
        f"lowpass=f={lpf},"
        f"highpass=f={hpf},"
        f"aecho=0.8:0.6:50:0.35,"
        f"aecho=0.8:0.5:100:0.25,"
        f"afade=t=in:d=2.0,"
        f"afade=t=out:st={fade_out_start}:d=3.0,"
        f"volume={vol}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", filter_expr,
        "-t", str(duration),
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        str(output_path)
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Lỗi khi sinh nhạc offline bằng FFmpeg: {e.stderr.decode()}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate 60s Background Music (ACE-Step 1.5 logic)")
    parser.add_argument("--genre", type=str, default="ambient", choices=["ambient", "epic", "lofi", "synthwave", "cinematic", "upbeat"], help="Thể loại nhạc nền")
    parser.add_argument("--prompt", type=str, default="Chill lofi ambient background beat, modern tech cinematic, 120 bpm", help="Prompt mô tả thể loại nhạc")
    parser.add_argument("--duration", type=int, default=60, help="Thời lượng nhạc tính theo giây (mặc định 60s)")
    parser.add_argument("--output", type=str, default="", help="File mp3 đầu ra")
    args = parser.parse_args()

    out_file = Path(args.output) if args.output else (TEMP_DIR / "background_music.mp3")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Bước 1: Thử gọi ACE-Step 1.5 nếu có cấu hình
    engine_used = "ace-step-1.5"
    success = call_ace_step_api(args.prompt, args.duration, out_file)

    # Bước 2: Fallback sang bộ sinh FFmpeg 0 đồng
    if not success:
        engine_used = "ffmpeg-ambient-synth-0dong"
        success = generate_offline_synth_track(args.duration, out_file, genre=args.genre)

    if success and out_file.exists():
        result = {
            "status": "success",
            "engine": engine_used,
            "music_path": str(out_file.resolve()),
            "duration": args.duration,
            "prompt": args.prompt
        }
        print(json.dumps(result, ensure_ascii=False))
    else:
        err = {"status": "error", "message": "Không thể tạo file nhạc nền"}
        print(json.dumps(err, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
