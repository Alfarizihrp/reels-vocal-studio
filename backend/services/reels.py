import json
import re
from pathlib import Path
from faster_whisper import WhisperModel
from config import MODEL_DIR, get_gemini_api_key
from services.media import extract_audio_wav, probe_duration, render_reel_clip

_whisper_cache: dict[str, WhisperModel] = {}


def _get_whisper(model_size: str = "base") -> WhisperModel:
    if model_size not in _whisper_cache:
        _whisper_cache[model_size] = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root=str(MODEL_DIR / "whisper"),
        )
    return _whisper_cache[model_size]


def transcribe_audio(wav_path: Path, model_size: str = "base") -> list[dict]:
    model = _get_whisper(model_size)
    segments, _ = model.transcribe(str(wav_path), vad_filter=True)
    result = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            result.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": text,
            })
    return result


def _select_clips_with_gemini(
    segments: list[dict],
    num_clips: int,
    min_sec: int,
    max_sec: int,
    api_key: str,
) -> list[dict] | None:
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        transcript_lines = [
            f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}"
            for s in segments
        ]
        transcript_text = "\n".join(transcript_lines[:400])

        prompt = (
            f"Pilih {num_clips} potongan paling menarik/viral untuk video pendek Reels/TikTok "
            f"dari transkrip berikut. Durasi tiap potongan harus antara {min_sec} sampai {max_sec} detik, "
            "dan tidak boleh saling tumpang tindih.\n\n"
            "Balas HANYA dalam format JSON array valid tanpa markdown, dengan struktur:\n"
            '[{"start": 12.5, "end": 48.0, "title": "Judul singkat menarik", "reason": "Alasan singkat"}]\n\n'
            f"Transkrip:\n{transcript_text}"
        )

        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = (resp.text or "").strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        parsed = json.loads(raw)
        if isinstance(parsed, list) and parsed:
            valid = []
            for item in parsed[:num_clips]:
                s = float(item["start"])
                e = float(item["end"])
                if e > s + 5:
                    valid.append({
                        "start": s,
                        "end": e,
                        "title": str(item.get("title", "Highlight Clip"))[:80],
                        "reason": str(item.get("reason", "Dipilih oleh AI Gemini"))[:160],
                    })
            return valid or None
    except Exception:
        return None
    return None


def _select_clips_heuristic(
    segments: list[dict],
    total_duration: float,
    num_clips: int,
    min_sec: int,
    max_sec: int,
) -> list[dict]:
    """Local CPU fallback: group segments into windows and score by hook density & speech rate."""
    if not segments:
        # No speech detected: split evenly
        clip_len = min(max_sec, max(min_sec, total_duration / max(1, num_clips)))
        clips = []
        cursor = 0.0
        for i in range(num_clips):
            if cursor + 5 >= total_duration:
                break
            end = min(total_duration, cursor + clip_len)
            clips.append({
                "start": round(cursor, 2),
                "end": round(end, 2),
                "title": f"Highlight #{i + 1}",
                "reason": "Pemotongan otomatis berdasarkan durasi",
            })
            cursor = end
        return clips

    hook_words = {
        "kenapa", "mengapa", "rahasia", "cara", "tips", "jangan", "harus", "ternyata",
        "fakta", "penting", "kesalahan", "why", "how", "secret", "mistake", "never", "best",
    }

    candidates = []
    n = len(segments)
    for i in range(n):
        start = segments[i]["start"]
        end = segments[i]["end"]
        texts = [segments[i]["text"]]
        j = i + 1
        while j < n and (segments[j]["end"] - start) <= max_sec:
            end = segments[j]["end"]
            texts.append(segments[j]["text"])
            if (end - start) >= min_sec:
                dur = end - start
                joined = " ".join(texts)
                words = joined.lower().split()
                wps = len(words) / max(1.0, dur)
                hook_hits = sum(1 for w in words if w.strip(".,!?") in hook_words)
                q_bonus = 1.5 if "?" in joined else 0.0
                score = wps + hook_hits * 0.8 + q_bonus
                candidates.append({
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "score": score,
                    "title": (texts[0][:55] + "...") if len(texts[0]) > 55 else texts[0],
                    "reason": f"Kepadatan bicara {wps:.1f} kata/detik & potensi hook tinggi",
                })
            j += 1

    # Fallback if video is shorter than min_sec
    if not candidates:
        end = min(total_duration, max(segments[-1]["end"], min_sec))
        return [{
            "start": round(segments[0]["start"], 2),
            "end": round(end, 2),
            "title": segments[0]["text"][:60],
            "reason": "Klip utama video",
        }]

    candidates.sort(key=lambda x: x["score"], reverse=True)
    chosen = []
    for cand in candidates:
        overlap = any(
            not (cand["end"] <= c["start"] or cand["start"] >= c["end"])
            for c in chosen
        )
        if not overlap:
            chosen.append(cand)
            if len(chosen) >= num_clips:
                break

    chosen.sort(key=lambda x: x["start"])
    return chosen


def _format_srt_time(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    hrs, rem = divmod(ms, 3_600_000)
    mins, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def _write_clip_srt(segments: list[dict], start: float, end: float, srt_path: Path) -> bool:
    lines = []
    idx = 1
    for seg in segments:
        if seg["end"] <= start or seg["start"] >= end:
            continue
        rel_start = max(0.0, seg["start"] - start)
        rel_end = min(end - start, seg["end"] - start)
        if rel_end <= rel_start:
            continue
        lines.append(f"{idx}\n{_format_srt_time(rel_start)} --> {_format_srt_time(rel_end)}\n{seg['text']}\n")
        idx += 1
    if not lines:
        return False
    srt_path.write_text("\n".join(lines), encoding="utf-8")
    return True


def process_reels_job(
    *,
    video_path: Path,
    out_dir: Path,
    num_clips: int = 3,
    min_sec: int = 20,
    max_sec: int = 55,
    crop_mode: str = "center_crop",
    whisper_model: str = "base",
    burn_subtitles: bool = True,
    gemini_api_key: str | None = None,
    progress_cb=None,
) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    total_duration = probe_duration(video_path)

    if progress_cb:
        progress_cb(30, "Mengekstrak audio untuk transkripsi...")
    wav_path = out_dir / "audio_16k.wav"
    extract_audio_wav(video_path, wav_path)

    if progress_cb:
        progress_cb(45, f"Mentranskrip audio (Whisper {whisper_model} CPU)...")
    segments = transcribe_audio(wav_path, model_size=whisper_model)

    if progress_cb:
        progress_cb(65, "Memilih momen terbaik untuk Reels...")
    key = get_gemini_api_key(gemini_api_key)
    selected = None
    if key and segments:
        selected = _select_clips_with_gemini(segments, num_clips, min_sec, max_sec, key)
    if not selected:
        selected = _select_clips_heuristic(segments, total_duration, num_clips, min_sec, max_sec)

    results = []
    total_clips = len(selected)
    for idx, clip in enumerate(selected, start=1):
        if progress_cb:
            pct = 70 + int((idx - 1) / max(1, total_clips) * 25)
            progress_cb(pct, f"Merender klip {idx}/{total_clips} (9:16)...")

        srt_path = out_dir / f"clip_{idx}.srt"
        has_srt = burn_subtitles and _write_clip_srt(segments, clip["start"], clip["end"], srt_path)
        mp4_path = out_dir / f"reel_{idx}.mp4"

        render_reel_clip(
            video_path=video_path,
            start_sec=clip["start"],
            end_sec=clip["end"],
            output_path=mp4_path,
            crop_mode=crop_mode,
            srt_path=srt_path if has_srt else None,
        )

        results.append({
            "index": idx,
            "title": clip["title"],
            "reason": clip["reason"],
            "start": clip["start"],
            "end": clip["end"],
            "duration": round(clip["end"] - clip["start"], 1),
            "filename": mp4_path.name,
        })

    return results
