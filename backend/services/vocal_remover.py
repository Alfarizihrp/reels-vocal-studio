from pathlib import Path
from audio_separator.separator import Separator
from config import MODEL_DIR
from services.media import convert_audio_format

DEFAULT_SEPARATION_MODEL = "UVR-MDX-NET-Inst_HQ_3.onnx"


def process_vocal_removal_job(
    *,
    audio_path: Path,
    out_dir: Path,
    output_format: str = "mp3",
    progress_cb=None,
) -> dict:
    """Separate vocals and instrumental from an audio/video file on CPU."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sep_dir = out_dir / "raw_stems"
    sep_dir.mkdir(parents=True, exist_ok=True)

    if progress_cb:
        progress_cb(35, "Memuat model pemisah vokal & musik (CPU)...")

    separator = Separator(
        output_dir=str(sep_dir),
        model_file_dir=str(MODEL_DIR / "audio_separator"),
        output_format="WAV",
    )
    separator.load_model(model_filename=DEFAULT_SEPARATION_MODEL)

    if progress_cb:
        progress_cb(55, "Memisahkan vokal dan instrumen musik...")

    output_files = separator.separate(str(audio_path))
    if not output_files:
        raise RuntimeError("Pemisahan audio tidak menghasilkan file output.")

    vocals_src = None
    inst_src = None
    for f in output_files:
        p = Path(f)
        if not p.is_absolute():
            p = sep_dir / p
        name_lower = p.name.lower()
        if "vocal" in name_lower:
            vocals_src = p
        elif "instrumental" in name_lower or "no_vocals" in name_lower:
            inst_src = p

    if progress_cb:
        progress_cb(88, f"Mengonversi hasil ke format {output_format.upper()}...")

    ext = "wav" if output_format == "wav" else "mp3"
    result = {}

    if vocals_src and vocals_src.exists():
        vocals_out = out_dir / f"vocals_only.{ext}"
        convert_audio_format(vocals_src, vocals_out, ext)
        result["vocals"] = vocals_out.name

    if inst_src and inst_src.exists():
        inst_out = out_dir / f"instrumental_only.{ext}"
        convert_audio_format(inst_src, inst_out, ext)
        result["instrumental"] = inst_out.name

    if not result:
        raise RuntimeError("Gagal mengenali stem vokal/instrumen dari output model.")

    return result
