#!/usr/bin/env python3
"""
scripts/render_video.py
Render video Reels 9:16 chất lượng cao với:
- Hiệu ứng Ken Burns đa dạng (6 pattern zoom + pan)
- Chuyển cảnh mượt mà (crossfade, dissolve, slide, wipe...)
- Color grading điện ảnh (contrast, saturation, vignette)
- Phụ đề lớn dễ đọc trên mobile
- Audio ducking chuyên nghiệp với fade in/out nhạc nền
"""

import sys
import os
import json
import shutil
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
    from dotenv import load_dotenv
    ROOT_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    ROOT_DIR = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger("render_video")

SHARED_DIR = Path(os.getenv("SHARED_MEDIA_DIR", str(ROOT_DIR / "shared_media")))
TEMP_DIR = SHARED_DIR / "temp"
OUTPUT_DIR = SHARED_DIR / "outputs"

# === CẤU HÌNH ĐA KÍCH THƯỚC KHUNG HÌNH (ASPECT RATIOS) ===
RESOLUTIONS = {
    "9:16": {"width": 1080, "height": 1920, "canvas_w": 1440, "canvas_h": 2560, "margin_v": 140, "font_size": 18, "label": "Dọc 9:16 (TikTok, Reels, Shorts)"},
    "16:9": {"width": 1920, "height": 1080, "canvas_w": 2560, "canvas_h": 1440, "margin_v": 80, "font_size": 22, "label": "Ngang 16:9 (YouTube, TV, Facebook)"},
    "1:1":  {"width": 1080, "height": 1080, "canvas_w": 1440, "canvas_h": 1440, "margin_v": 90, "font_size": 18, "label": "Vuông 1:1 (Instagram Feed, Facebook Post)"},
}

DEFAULT_FPS = 30
XFADE_DURATION = 0.7  # Thời lượng chuyển cảnh crossfade (giây)

# === 6 MOTION PATTERNS cho Ken Burns Effect ===
# Mỗi pattern: cách zoom và hướng pan (x, y)
# {frames} được thay bằng tổng số frame thực tế lúc runtime
MOTION_PATTERNS = [
    {
        "name": "zoom_in_pan_right",
        "zoom": "min(1.15+0.15*on/{frames},1.30)",
        "x": "(iw-iw/zoom)*on/{frames}",
        "y": "ih/2-(ih/zoom/2)",
    },
    {
        "name": "zoom_in_pan_left",
        "zoom": "min(1.15+0.15*on/{frames},1.30)",
        "x": "(iw-iw/zoom)*(1-on/{frames})",
        "y": "ih/2-(ih/zoom/2)",
    },
    {
        "name": "zoom_out_center",
        "zoom": "if(eq(on,0),1.35,max(1.35-0.35*on/{frames},1.0))",
        "x": "iw/2-(iw/zoom/2)",
        "y": "ih/2-(ih/zoom/2)",
    },
    {
        "name": "zoom_in_center",
        "zoom": "min(1.0+0.35*on/{frames},1.35)",
        "x": "iw/2-(iw/zoom/2)",
        "y": "ih/2-(ih/zoom/2)",
    },
    {
        "name": "pan_down_zoom_in",
        "zoom": "min(1.15+0.10*on/{frames},1.25)",
        "x": "iw/2-(iw/zoom/2)",
        "y": "(ih-ih/zoom)*on/{frames}",
    },
    {
        "name": "pan_up_zoom_in",
        "zoom": "min(1.15+0.10*on/{frames},1.25)",
        "x": "iw/2-(iw/zoom/2)",
        "y": "(ih-ih/zoom)*(1-on/{frames})",
    },
]

# Các hiệu ứng chuyển cảnh luân phiên
XFADE_TRANSITIONS = [
    "fade", "fadeblack", "slideleft", "dissolve",
    "wipeleft", "smoothleft", "circlecrop",
    "slideright", "wiperight", "smoothright",
]


def get_media_duration(file_path: Path) -> float:
    """Đo thời lượng file media bằng ffprobe"""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Không thể đo thời lượng {file_path} ({e}). Mặc định: 30.0s")
        return 30.0


def create_ken_burns_clip(
    image_path: Path,
    output_clip: Path,
    duration: float,
    fps: int = DEFAULT_FPS,
    pattern_idx: int = 0,
    aspect_ratio: str = "9:16"
) -> bool:
    """Tạo video clip từ ảnh tĩnh với hiệu ứng Ken Burns (Zoom + Pan) + Color Grading điện ảnh theo tỷ lệ khung hình"""
    output_clip.parent.mkdir(parents=True, exist_ok=True)
    frames = max(int(duration * fps), fps)

    res = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["9:16"])
    target_w, target_h = res["width"], res["height"]
    canvas_w, canvas_h = res["canvas_w"], res["canvas_h"]

    # Chọn motion pattern luân phiên
    pattern = MOTION_PATTERNS[pattern_idx % len(MOTION_PATTERNS)]
    zoom_expr = pattern["zoom"].replace("{frames}", str(frames))
    x_expr = pattern["x"].replace("{frames}", str(frames))
    y_expr = pattern["y"].replace("{frames}", str(frames))

    logger.info(f"  Ken Burns: {pattern['name']} | Tỉ lệ {aspect_ratio} ({target_w}x{target_h}) | {duration:.1f}s | {frames} frames")

    # Filter chain: upscale Lanczos → crop theo tỷ lệ → zoompan → unsharp → color grading → vignette
    vf = (
        f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={canvas_w}:{canvas_h},"
        f"zoompan=z='{zoom_expr}':d={frames}:x='{x_expr}':y='{y_expr}'"
        f":s={target_w}x{target_h}:fps={fps},"
        f"unsharp=3:3:0.8:3:3:0.0,"
        f"eq=contrast=1.06:brightness=0.01:saturation=1.15,"
        f"vignette=PI/5"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(output_clip)
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Lỗi tạo Ken Burns clip cho {image_path}: {e.stderr.decode()[:500]}")
        return False


def hex_to_ass_color(hex_str: str, alpha: int = 0) -> str:
    """Chuyển đổi mã màu hex (#RRGGBB) hoặc ASS sang định dạng ASS &HAABBGGRR"""
    if not hex_str:
        hex_str = "#FFFFFF"
    hex_str = hex_str.strip()
    if hex_str.startswith("&H"):
        return hex_str
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 6:
        r = hex_clean[0:2]
        g = hex_clean[2:4]
        b = hex_clean[4:6]
    elif len(hex_clean) == 3:
        r = hex_clean[0] * 2
        g = hex_clean[1] * 2
        b = hex_clean[2] * 2
    else:
        r, g, b = "FF", "FF", "FF"
    a_hex = f"{max(0, min(255, int(alpha))):02X}"
    return f"&H{a_hex}{b}{g}{r}"


def get_subtitle_style(
    font_size: int = 18,
    primary_color: str = "&H00FFFFFF",
    sub_position: str = "bottom",
    aspect_ratio: str = "9:16",
    font_name: str = "Arial",
    font_bold: bool = True,
    outline_color: str = "&H00000000",
    outline_size: int = 2,
    position_y: float | None = None,
    bg_box: bool = False,
    bg_opacity: float = 0.5,
    align_mode: str = "center"
) -> str:
    """Tạo chuỗi style phụ đề ASS chuyên nghiệp hỗ trợ font, cỡ, viền, vị trí Y% và màu nền"""
    res = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["9:16"])
    height = res["height"]
    
    # Map căn lề (align_mode: 'center' [mặc định], 'left', 'right')
    align_mode = (align_mode or "center").lower().strip()
    if align_mode == "left":
        offset = -1  # 2->1, 5->4, 8->7
    elif align_mode == "right":
        offset = 1   # 2->3, 5->6, 8->9
    else:
        offset = 0

    # Tính MarginV và Alignment
    if position_y is not None and 0 <= float(position_y) <= 100:
        base_align = 2  # Căn đáy để text mở rộng lên trên an toàn
        margin_v = max(10, int(height * ((100.0 - float(position_y)) / 100.0)))
    elif sub_position in ("center", "middle"):
        base_align = 5  # Chính giữa màn hình
        margin_v = 0
    elif sub_position == "top":
        base_align = 8  # Trên cao
        margin_v = 160 if aspect_ratio == "9:16" else (85 if aspect_ratio == "16:9" else 90)
    else:
        base_align = 2  # Dưới đáy
        margin_v = res["margin_v"]

    align = base_align + offset

    prim_ass = hex_to_ass_color(primary_color)
    outl_ass = hex_to_ass_color(outline_color)
    bold_val = 1 if font_bold else 0

    if bg_box:
        border_style = 3  # Hộp màu nền sau chữ
        alpha = int(max(0.0, min(1.0, 1.0 - bg_opacity)) * 255)
        back_ass = hex_to_ass_color("#000000", alpha=alpha)
    else:
        border_style = 1  # Viền chữ + Bóng đổ
        back_ass = "&H80000000"

    clean_font = font_name.strip() if font_name else "Arial"
    margin_lr = 45 if aspect_ratio == "9:16" else 80

    return (
        f"FontName={clean_font},FontSize={font_size},Bold={bold_val},"
        f"PrimaryColour={prim_ass},"
        f"OutlineColour={outl_ass},"
        f"BackColour={back_ass},"
        f"BorderStyle={border_style},Outline={outline_size},Shadow=1,"
        f"Alignment={align},MarginV={margin_v},MarginL={margin_lr},MarginR={margin_lr}"
    )



def burn_subtitles_to_video(
    source_video: Path,
    sub_path: Path,
    output_video: Path,
    font_size: int = 18,
    primary_color: str = "&H00FFFFFF",
    sub_position: str = "bottom",
    margin_v: int = 140,
    aspect_ratio: str = "9:16"
) -> bool:
    """Ghi đè phụ đề vào video với font chữ, màu sắc, vị trí (đáy, giữa, đỉnh) và tỷ lệ khung hình tùy chỉnh"""
    output_video.parent.mkdir(parents=True, exist_ok=True)
    sub_style = get_subtitle_style(
        font_size=font_size,
        primary_color=primary_color,
        sub_position=sub_position,
        aspect_ratio=aspect_ratio
    )
    sub_filename = sub_path.name
    vf_sub = f"subtitles='{sub_filename}':force_style='{sub_style}'"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(source_video.resolve()),
        "-vf", vf_sub,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "copy",
        str(output_video.resolve())
    ]
    try:
        subprocess.run(cmd, cwd=str(sub_path.parent), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Lỗi burn-in phụ đề: {e.stderr.decode()[:500] if e.stderr else e}")
        return False


def render_full_video(
    image_paths: list[Path],
    voice_path: Path,
    music_path: Path,
    sub_path: Path | None,
    output_video: Path,
    font_size: int = 18,
    sub_position: str = "bottom",
    aspect_ratio: str = "9:16"
) -> dict:
    """
    Quy trình render hoàn chỉnh:
    1. Tạo Ken Burns clips với 6 motion patterns luân phiên
    2. Ghép bằng xfade transitions (crossfade, dissolve, slide...)
    3. Mix audio: Voice 100% + Music 12% với fade in/out
    4. Burn-in phụ đề modern style (chữ vừa vặn, viền đen rõ nét)
    5. Xuất MP4 chất lượng cao
    """
    output_video.parent.mkdir(parents=True, exist_ok=True)

    # 1. Đo thời lượng giọng đọc
    voice_duration = get_media_duration(voice_path)
    total_duration = max(5.0, voice_duration)
    logger.info(f"Tổng thời lượng mục tiêu: {total_duration:.2f}s")

    num_images = len(image_paths)
    if num_images == 0:
        raise ValueError("Không có hình ảnh nào để render!")

    # Tính thời lượng mỗi clip, bù trừ overlap do crossfade
    # Công thức: total_output = N * clip_dur - (N-1) * xfade_dur
    xfade_dur = XFADE_DURATION if num_images > 1 else 0
    clip_duration = (total_duration + (num_images - 1) * xfade_dur) / num_images
    clip_duration = max(clip_duration, 2.0)  # Tối thiểu 2s mỗi clip
    logger.info(f"Số cảnh: {num_images} | Mỗi cảnh: {clip_duration:.2f}s | Crossfade: {xfade_dur}s")

    # 2. Tạo Ken Burns clips với motion patterns luân phiên
    clip_files = []
    res_cfg = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["9:16"])
    target_width = res_cfg["width"]
    target_height = res_cfg["height"]
    default_margin_v = res_cfg["margin_v"]

    for idx, item_path in enumerate(image_paths):
        clip_file = TEMP_DIR / f"clip_{idx:02d}.mp4"
        logger.info(f"Chuẩn bị clip phân cảnh {idx+1}/{num_images}...")
        if item_path.suffix.lower() == ".mp4":
            # Phân cảnh là video clip chuyển động từ Google Veo 2
            cmd_norm = [
                "ffmpeg", "-y",
                "-i", str(item_path.resolve()),
                "-t", f"{clip_duration:.2f}",
                "-vf", f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,fps={DEFAULT_FPS}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-an",
                str(clip_file.resolve())
            ]
            try:
                subprocess.run(cmd_norm, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
                clip_files.append(clip_file)
            except Exception as e:
                logger.warning(f"Lỗi chuẩn hóa video clip Veo 2 {item_path} ({e}), dùng fallback.")
                if create_ken_burns_clip(item_path, clip_file, clip_duration, pattern_idx=idx, aspect_ratio=aspect_ratio):
                    clip_files.append(clip_file)
        else:
            if create_ken_burns_clip(item_path, clip_file, clip_duration, pattern_idx=idx, aspect_ratio=aspect_ratio):
                clip_files.append(clip_file)

    if not clip_files:
        raise RuntimeError("Không tạo được clip Ken Burns nào!")

    # 3. Ghép video với chuyển cảnh xfade mượt mà
    temp_video_only = TEMP_DIR / "temp_video_stitched.mp4"

    if len(clip_files) == 1:
        shutil.copy2(clip_files[0], temp_video_only)
    else:
        # Xây dựng filter graph cho xfade transitions
        # Offset cho transition thứ i (0-indexed): (i+1) * (clip_duration - xfade_dur)
        filter_parts = []
        for i in range(len(clip_files) - 1):
            transition = XFADE_TRANSITIONS[i % len(XFADE_TRANSITIONS)]
            offset = (i + 1) * (clip_duration - xfade_dur)

            in1 = "[0:v]" if i == 0 else f"[v{i}]"
            in2 = f"[{i+1}:v]"
            out = "[vout]" if i == len(clip_files) - 2 else f"[v{i+1}]"

            filter_parts.append(
                f"{in1}{in2}xfade=transition={transition}:duration={xfade_dur:.3f}:offset={offset:.3f}{out}"
            )

        filter_complex = ";".join(filter_parts)
        logger.info(f"Đang áp dụng {len(filter_parts)} hiệu ứng chuyển cảnh...")

        cmd = ["ffmpeg", "-y"]
        for clip in clip_files:
            cmd.extend(["-i", str(clip)])
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            str(temp_video_only)
        ])
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

    # 4. Hòa âm: Voice 100% + Music 12% với fade in/out chuyên nghiệp
    temp_with_audio = TEMP_DIR / "temp_video_audio.mp4"
    fade_out_start = max(0, total_duration - 3.0)
    audio_filter = (
        "[1:a]volume=1.0[voice];"
        f"[2:a]volume=0.12,afade=t=in:d=2.0,afade=t=out:st={fade_out_start:.1f}:d=3.0,"
        f"aloop=loop=-1:size=2e+09[music];"
        "[voice][music]amix=inputs=2:duration=first:dropout_transition=3[aout]"
    )

    cmd_mix = [
        "ffmpeg", "-y",
        "-i", str(temp_video_only),
        "-i", str(voice_path),
        "-i", str(music_path),
        "-filter_complex", audio_filter,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(total_duration),
        str(temp_with_audio)
    ]
    subprocess.run(cmd_mix, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

    # 5. Burn-in phụ đề Modern Reels Style + Fade in/out toàn video
    final_target = output_video.resolve()
    temp_with_audio_abs = temp_with_audio.resolve()

    if sub_path and sub_path.exists() and sub_path.stat().st_size > 10:
        logger.info(f"Đang burn-in phụ đề (FontSize={font_size}, Position={sub_position}, Tỉ lệ {aspect_ratio})...")
        sub_style = get_subtitle_style(
            font_size=font_size,
            primary_color="&H00FFFFFF",
            sub_position=sub_position,
            aspect_ratio=aspect_ratio
        )
        sub_filename = sub_path.name
        fade_out_vf = max(0, total_duration - 1.0)
        vf_sub = (
            f"subtitles='{sub_filename}':force_style='{sub_style}',"
            f"fade=t=in:d=0.4,fade=t=out:st={fade_out_vf:.1f}:d=1.0"
        )

        cmd_sub = [
            "ffmpeg", "-y",
            "-i", str(temp_with_audio_abs),
            "-vf", vf_sub,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-c:a", "copy",
            str(final_target)
        ]
        try:
            subprocess.run(cmd_sub, cwd=str(sub_path.parent),
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
            logger.info("Burn-in phụ đề thành công!")
        except Exception as e:
            logger.warning(f"Không thể burn-in phụ đề ({e}). Dùng video không sub.")
            shutil.copy2(temp_with_audio_abs, final_target)
    else:
        if final_target.exists():
            final_target.unlink()
        shutil.copy2(temp_with_audio_abs, final_target)

    # 6. Dọn dẹp file tạm
    for c in clip_files:
        try: c.unlink()
        except: pass
    try:
        shutil.copy2(temp_video_only, TEMP_DIR / "temp_raw_video.mp4")
        temp_video_only.unlink()
    except: pass

    logger.info(f"✅ Render thành công: {final_target} ({target_width}x{target_height}, {final_target.stat().st_size // 1024} KB)")
    return {
        "status": "success",
        "video_path": str(final_target.resolve()),
        "duration": total_duration,
        "width": target_width,
        "height": target_height,
        "aspect_ratio": aspect_ratio,
        "fps": DEFAULT_FPS,
        "size_kb": final_target.stat().st_size // 1024
    }



def remix_and_export_video(
    source_video: Path,
    voice_path: Path | None,
    music_path: Path | None,
    sub_path: Path | None,
    output_video: Path,
    voice_volume: float = 1.0,
    music_volume: float = 0.12,
    audio_ducking: bool = True,
    font_name: str = "Google Sans",
    font_size: int = 18,
    font_bold: bool = True,
    primary_color: str = "#FFFFFF",
    outline_color: str = "#000000",
    outline_size: int = 2,
    position_y: float = 75.0,
    bg_box: bool = False,
    bg_opacity: float = 0.5,
    aspect_ratio: str = "9:16",
    align_mode: str = "center"
) -> dict:
    """
    Phòng dựng Hậu kỳ (Post-Production Studio Remixer):
    Trộn lại audio (voice + music với ducking) và ép phụ đề mới vào video chỉ trong 2-4 giây!
    """
    output_video.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = source_video.parent
    total_duration = get_media_duration(source_video)

    has_voice = voice_path and voice_path.exists() and voice_path.stat().st_size > 100
    has_music = music_path and music_path.exists() and music_path.stat().st_size > 100
    has_sub = sub_path and sub_path.exists() and sub_path.stat().st_size > 10

    # 1. Xây dựng bộ lọc Audio
    inputs = ["-i", str(source_video.resolve())]
    next_input_idx = 1
    v_idx = -1
    m_idx = -1

    if has_voice:
        inputs.extend(["-i", str(voice_path.resolve())])
        v_idx = next_input_idx
        next_input_idx += 1

    if has_music:
        inputs.extend(["-i", str(music_path.resolve())])
        m_idx = next_input_idx
        next_input_idx += 1

    fade_out_start = max(1.0, total_duration - 2.5)

    filter_complex_parts = []
    aout_label = None

    if has_voice and has_music:
        filter_complex_parts.append(f"[{v_idx}:a]volume={voice_volume:.2f},asplit=2[v_main][v_side];")
        filter_complex_parts.append(
            f"[{m_idx}:a]volume={music_volume:.2f},afade=t=in:d=1.5,afade=t=out:st={fade_out_start:.1f}:d=2.5,aloop=loop=-1:size=2e+09[m_raw];"
        )
        if audio_ducking:
            filter_complex_parts.append(
                f"[m_raw][v_side]sidechaincompress=threshold=0.08:ratio=4:attack=50:release=300[m_ducked];"
                f"[v_main][m_ducked]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
        else:
            filter_complex_parts.append(f"[v_main][m_raw]amix=inputs=2:duration=first:dropout_transition=2[aout]")
        aout_label = "[aout]"
    elif has_voice:
        filter_complex_parts.append(f"[{v_idx}:a]volume={voice_volume:.2f}[aout]")
        aout_label = "[aout]"
    elif has_music:
        filter_complex_parts.append(
            f"[{m_idx}:a]volume={music_volume:.2f},afade=t=in:d=1.5,afade=t=out:st={fade_out_start:.1f}:d=2.5,aloop=loop=-1:size=2e+09[aout]"
        )
        aout_label = "[aout]"

    # 2. Xây dựng bộ lọc Video & Phụ đề
    vf_filters = []
    if has_sub:
        sub_style = get_subtitle_style(
            font_size=font_size,
            primary_color=primary_color,
            font_name=font_name,
            font_bold=font_bold,
            outline_color=outline_color,
            outline_size=outline_size,
            position_y=position_y,
            bg_box=bg_box,
            bg_opacity=bg_opacity,
            aspect_ratio=aspect_ratio,
            align_mode=align_mode
        )
        sub_name = sub_path.name
        vf_filters.append(f"subtitles=filename={sub_name}:force_style='{sub_style}'")

    cmd = ["ffmpeg", "-y"] + inputs

    if filter_complex_parts and vf_filters:
        fc = "".join(filter_complex_parts)
        vf_str = ",".join(vf_filters)
        cmd.extend([
            "-filter_complex", f"{fc};[0:v]{vf_str}[vout]",
            "-map", "[vout]",
            "-map", aout_label,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(total_duration),
            str(output_video.resolve())
        ])
    elif filter_complex_parts:
        fc = "".join(filter_complex_parts)
        cmd.extend([
            "-filter_complex", fc,
            "-map", "0:v",
            "-map", aout_label,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(total_duration),
            str(output_video.resolve())
        ])
    elif vf_filters:
        vf_str = ",".join(vf_filters)
        cmd.extend([
            "-vf", vf_str,
            "-map", "0:v",
            "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "copy",
            "-t", str(total_duration),
            str(output_video.resolve())
        ])
    else:
        cmd.extend([
            "-c", "copy",
            str(output_video.resolve())
        ])

    logger.info(f"Đang chạy Hậu kỳ FFmpeg: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(sub_path.parent if has_sub else source_video.parent),
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

    return {
        "status": "success",
        "video_path": str(output_video.resolve()),
        "duration": total_duration,
        "size_kb": output_video.stat().st_size // 1024
    }


def main():
    parser = argparse.ArgumentParser(description="Render Reel Video: Ken Burns + Transitions + Multi-Aspect Ratio")
    parser.add_argument("--images", nargs="+", help="Danh sách các file ảnh")
    parser.add_argument("--images-json", type=str, default="", help="Mảng JSON chứa đường dẫn các ảnh")
    parser.add_argument("--voice", type=str, default="", help="File audio giọng đọc")
    parser.add_argument("--music", type=str, default="", help="File audio nhạc nền")
    parser.add_argument("--sub", type=str, default="", help="File srt phụ đề")
    parser.add_argument("--font-size", type=int, default=18, help="Cỡ chữ phụ đề (mặc định: 18)")
    parser.add_argument("--sub-position", type=str, default="bottom", choices=["bottom", "center", "top"], help="Vị trí phụ đề: bottom (đáy), center (giữa), top (đỉnh)")
    parser.add_argument("--aspect-ratio", type=str, default="9:16", choices=["9:16", "16:9", "1:1"], help="Tỷ lệ khung hình: 9:16, 16:9, 1:1")
    parser.add_argument("--output", type=str, default="", help="File video đầu ra")
    args = parser.parse_args()

    # Thu thập danh sách ảnh
    images = []
    if args.images_json:
        try:
            parsed = json.loads(args.images_json)
            images = [Path(p) for p in parsed]
        except Exception as e:
            logger.error(f"Lỗi parse --images-json: {e}")
    elif args.images:
        images = [Path(p) for p in args.images]
    else:
        images = sorted(list(TEMP_DIR.glob("scene_*.jpg")))

    voice_file = Path(args.voice) if args.voice else (TEMP_DIR / "voiceover.mp3")
    music_file = Path(args.music) if args.music else (TEMP_DIR / "background_music.mp3")
    sub_file = Path(args.sub) if args.sub else (TEMP_DIR / "subtitles.srt")
    out_video = Path(args.output) if args.output else (OUTPUT_DIR / "final_reel.mp4")

    if not images or not all(img.exists() for img in images):
        logger.error("Thiếu file ảnh đầu vào!")
        print(json.dumps({"status": "error", "message": "Không tìm thấy file ảnh"}, ensure_ascii=False))
        sys.exit(1)

    if not voice_file.exists():
        logger.error(f"Không tìm thấy file voiceover: {voice_file}")
        print(json.dumps({"status": "error", "message": "Thiếu file voiceover"}, ensure_ascii=False))
        sys.exit(1)

    if not music_file.exists():
        logger.warning(f"Không tìm thấy nhạc nền: {music_file}. Sẽ tạo mặc định.")
        from generate_music import generate_offline_synth_track
        generate_offline_synth_track(60, music_file)

    try:
        res = render_full_video(
            image_paths=images,
            voice_path=voice_file,
            music_path=music_file,
            sub_path=sub_file if sub_file.exists() else None,
            output_video=out_video,
            font_size=args.font_size,
            sub_position=args.sub_position,
            aspect_ratio=args.aspect_ratio
        )
        print(json.dumps(res, ensure_ascii=False))
    except Exception as e:
        logger.error(f"Lỗi render: {e}", exc_info=True)
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
