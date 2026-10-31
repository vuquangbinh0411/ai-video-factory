#!/usr/bin/env python3
"""
scripts/generate_tts.py
Nhiệm vụ: Chuyển đổi văn bản kịch bản sang giọng nói tiếng Việt bằng Edge-TTS (Hoàn toàn miễn phí, chất lượng cao).
Giọng mặc định: vi-VN-HoaiMyNeural (Nữ miền Bắc truyền cảm).
"""

import sys
import os
import json
import asyncio
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
    import edge_tts
except ImportError:
    edge_tts = None

try:
    from dotenv import load_dotenv
    ROOT_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    ROOT_DIR = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger("generate_tts")

DEFAULT_VOICE = os.getenv("DEFAULT_TTS_VOICE", "vi-VN-HoaiMyNeural")
TEMP_DIR = Path(os.getenv("SHARED_MEDIA_DIR", str(ROOT_DIR / "shared_media"))) / "temp"

def chunk_srt_into_short_cues(raw_srt: str, max_words: int = 4, max_chars: int = 26) -> str:
    """
    Chia nhỏ các câu dài thành các cụm từ ngắn 3-5 từ (chuẩn TikTok/CapCut Reels).
    Tránh tình trạng cả câu 20-30 từ hiện cùng lúc chiếm hết màn hình video.
    """
    import re
    if not raw_srt or not raw_srt.strip():
        return raw_srt

    def parse_time(t_str):
        parts = t_str.split(':')
        s, ms = parts[2].split(',')
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(s) + int(ms) / 1000.0

    def format_time(sec):
        sec = max(0.0, sec)
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int(round((sec - int(sec)) * 1000))
        if ms >= 1000: ms = 999
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    blocks = re.findall(
        r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\Z)',
        raw_srt,
        re.DOTALL
    )
    if not blocks:
        return raw_srt

    new_blocks = []
    cue_counter = 1

    for _, start_str, end_str, text_content in blocks:
        t_start = parse_time(start_str)
        t_end = parse_time(end_str)
        total_duration = max(0.5, t_end - t_start)

        clean_text = ' '.join(text_content.split())
        words = clean_text.split()
        if not words:
            continue

        # Nếu câu đã ngắn (dưới 5 từ và dưới 28 ký tự), giữ nguyên
        if len(words) <= max_words and len(clean_text) <= max_chars:
            new_blocks.append(f"{cue_counter}\n{start_str} --> {end_str}\n{clean_text}\n")
            cue_counter += 1
            continue

        # Phân rã thành các cụm từ nhịp điệu ngắn 3-5 từ
        chunks = []
        curr = []
        curr_len = 0
        for w in words:
            curr.append(w)
            curr_len += len(w) + 1
            is_break_punct = any(w.endswith(p) for p in [',', ';', '.', '?', '!'])
            if len(curr) >= max_words or curr_len >= max_chars or (len(curr) >= 3 and is_break_punct):
                chunks.append(' '.join(curr))
                curr = []
                curr_len = 0

        if curr:
            if chunks and len(curr) <= 2:
                chunks[-1] += ' ' + ' '.join(curr)
            else:
                chunks.append(' '.join(curr))

        # Phân bổ thời gian tỉ lệ thuận theo độ dài ký tự
        total_chars = sum(len(c) for c in chunks) or 1
        c_start = t_start
        for c in chunks:
            c_dur = total_duration * (len(c) / total_chars)
            c_end = c_start + c_dur
            new_blocks.append(f"{cue_counter}\n{format_time(c_start)} --> {format_time(c_end)}\n{c}\n")
            cue_counter += 1
            c_start = c_end

    return "\n".join(new_blocks) + "\n"

def get_audio_duration(file_path: Path) -> float:
    """Lấy thời lượng file audio chính xác bằng ffprobe"""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return round(float(result.stdout.strip()), 2)
    except Exception as e:
        logger.warning(f"ffprobe không khả dụng hoặc lỗi ({e}), ước lượng thời lượng bằng metadata.")
        return 0.0

async def synthesize_speech(
    text: str,
    output_audio: Path,
    output_sub: Path = None,
    voice: str = DEFAULT_VOICE,
    rate: str = "+8%",
    pitch: str = "+0Hz"
) -> dict:
    """Gọi Edge-TTS sinh file audio và subtitle đồng bộ với cơ chế retry tự động"""
    output_audio.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Đang sinh giọng đọc với voice: {voice} | Độ dài văn bản: {len(text)} ký tự")

    max_attempts = 3
    last_err = None

    for attempt in range(1, max_attempts + 1):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)

            # edge-tts: SubMaker khởi tạo
            try:
                submaker = edge_tts.SubMaker()
                use_submaker = True
            except Exception:
                use_submaker = False

            audio_chunks = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks += chunk["data"]
                elif chunk["type"] in ("WordBoundary", "SentenceBoundary") and use_submaker:
                    try:
                        submaker.feed(chunk)
                    except Exception:
                        pass

            if audio_chunks:
                with open(output_audio, "wb") as audio_file:
                    audio_file.write(audio_chunks)

                # Xuất file phụ đề SRT nếu được yêu cầu
                if output_sub and use_submaker:
                    output_sub.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        raw_srt = submaker.get_srt()
                        srt_content = chunk_srt_into_short_cues(raw_srt, max_words=4, max_chars=26)
                        with open(output_sub, "w", encoding="utf-8") as sub_file:
                            sub_file.write(srt_content)
                        logger.info(f"Đã tạo file phụ đề SRT nhịp điệu ngắn: {output_sub}")
                    except Exception as e:
                        logger.warning(f"Không thể xuất SRT: {e}")

                duration = get_audio_duration(output_audio)
                return {
                    "status": "success",
                    "audio_path": str(output_audio.resolve()),
                    "sub_path": str(output_sub.resolve()) if output_sub and output_sub.exists() else None,
                    "voice": voice,
                    "duration": duration
                }
        except Exception as e:
            last_err = e
            logger.warning(f"Lần thử {attempt}/{max_attempts} gặp sự cố ({e}). Đang thử lại...")
            await asyncio.sleep(2)

    raise RuntimeError(f"Edge-TTS thất bại sau {max_attempts} lần thử: {last_err}")

def main():
    parser = argparse.ArgumentParser(description="Generate TTS bằng Microsoft Edge-TTS")
    parser.add_argument("--text", type=str, default="", help="Nội dung văn bản cần đọc")
    parser.add_argument("--text-file", type=str, default="", help="Đường dẫn file văn bản chứa kịch bản")
    parser.add_argument("--voice", type=str, default=DEFAULT_VOICE, help="Tên giọng đọc Edge TTS")
    parser.add_argument("--rate", type=str, default="+8%", help="Tốc độ đọc (ví dụ: +10% hoặc -5%)")
    parser.add_argument("--pitch", type=str, default="+0Hz", help="Cao độ giọng đọc")
    parser.add_argument("--output", type=str, default="", help="Đường dẫn file mp3 đầu ra")
    parser.add_argument("--output-sub", type=str, default="", help="Đường dẫn file srt phụ đề đầu ra")
    args = parser.parse_args()

    content = args.text
    if not content and args.text_file and Path(args.text_file).exists():
        content = Path(args.text_file).read_text(encoding="utf-8")

    if not content:
        content = "Chào mừng bạn đến với kênh AI Video Factory. Hôm nay chúng ta sẽ cùng khám phá một bí ẩn vô cùng thú vị!"

    out_audio = Path(args.output) if args.output else (TEMP_DIR / "voiceover.mp3")
    out_sub = Path(args.output_sub) if args.output_sub else (TEMP_DIR / "subtitles.srt")

    try:
        result = asyncio.run(synthesize_speech(
            text=content,
            output_audio=out_audio,
            output_sub=out_sub,
            voice=args.voice,
            rate=args.rate,
            pitch=args.pitch
        ))
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        logger.error(f"Lỗi khi tạo TTS: {e}", exc_info=True)
        err_res = {"status": "error", "message": str(e)}
        print(json.dumps(err_res, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
