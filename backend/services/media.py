import json
import subprocess
from pathlib import Path
import yt_dlp


def download_media(url: str, dest_dir: Path, audio_only: bool = False) -> tuple[Path, str]:
    """Download video or audio from URL using yt-dlp and return (file_path, title)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(dest_dir / "source.%(ext)s")

    ydl_opts: dict = {
        "outtmpl": out_tmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    if audio_only:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }],
        })
    else:
        ydl_opts.update({
            "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
            "merge_output_format": "mp4",
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title") or "downloaded_media"

    files = list(dest_dir.glob("source.*"))
    if not files:
        raise RuntimeError("Gagal mengunduh media dari link tersebut.")

    # Prefer mp4/wav if multiple files exist
    preferred = [f for f in files if f.suffix.lower() in (".wav", ".mp4", ".mkv", ".webm", ".mp3", ".m4a")]
    chosen = preferred[0] if preferred else files[0]
    return chosen, title


def probe_duration(media_path: Path) -> float:
    """Return duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(media_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    return float(data.get("format", {}).get("duration", 0.0))


def extract_audio_wav(video_path: Path, wav_path: Path) -> Path:
    """Extract 16kHz mono WAV for fast Whisper transcription."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(wav_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return wav_path


def render_reel_clip(
    video_path: Path,
    start_sec: float,
    end_sec: float,
    output_path: Path,
    crop_mode: str = "center_crop",
    srt_path: Path | None = None,
) -> Path:
    """Cut clip and format to 1080x1920 (9:16) vertical Reels video."""
    duration = max(1.0, end_sec - start_sec)

    if crop_mode == "fit_blur":
        vf_base = (
            "split[original][copy];"
            "[copy]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
            "[original]scale=1080:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
    else:
        # center_crop 9:16
        vf_base = "scale=-2:1920,crop=1080:1920:(iw-1080)/2:0"

    if srt_path and srt_path.exists():
        # Escape Windows path for FFmpeg subtitles filter
        escaped_srt = str(srt_path).replace("\\", "/").replace(":", "\\:")
        sub_filter = (
            f"subtitles='{escaped_srt}':force_style="
            "'FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=45'"
        )
        if crop_mode == "fit_blur":
            vf = f"{vf_base}[v];[v]{sub_filter}"
        else:
            vf = f"{vf_base},{sub_filter}"
    else:
        vf = vf_base

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_sec:.2f}",
        "-i", str(video_path),
        "-t", f"{duration:.2f}",
        "-vf", vf if crop_mode != "fit_blur" else vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    if crop_mode == "fit_blur":
        # Use -filter_complex for multi-stream graph
        cmd[cmd.index("-vf")] = "-filter_complex"

    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return output_path


def convert_audio_format(src_path: Path, dst_path: Path, fmt: str = "mp3") -> Path:
    """Convert WAV to MP3 or copy WAV."""
    if fmt == "wav" and src_path.suffix.lower() == ".wav":
        if src_path != dst_path:
            dst_path.write_bytes(src_path.read_bytes())
        return dst_path

    cmd = ["ffmpeg", "-y", "-i", str(src_path)]
    if fmt == "mp3":
        cmd += ["-codec:a", "libmp3lame", "-qscale:a", "2"]
    cmd.append(str(dst_path))
    subprocess.run(cmd, capture_output=True, check=True)
    return dst_path
