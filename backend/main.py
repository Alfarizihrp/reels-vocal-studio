import shutil
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import OUTPUT_DIR, WORK_DIR, init_ffmpeg
from jobs import create_job, executor, get_job, list_jobs, update_job
from services.media import download_media
from services.reels import process_reels_job
from services.vocal_remover import process_vocal_removal_job

FFMPEG_READY = init_ffmpeg()

app = FastAPI(title="Reels & Vocal Studio API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "ffmpeg_ready": FFMPEG_READY,
        "mode": "cpu",
    }


@app.get("/api/jobs")
def api_list_jobs():
    return {"jobs": list_jobs()}


@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    return job


def _run_reels_task(
    job_id: str,
    url: str | None,
    uploaded_path: Path | None,
    num_clips: int,
    min_sec: int,
    max_sec: int,
    crop_mode: str,
    whisper_model: str,
    burn_subtitles: bool,
    gemini_api_key: str | None,
):
    work_dir = WORK_DIR / job_id
    out_dir = OUTPUT_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        update_job(job_id, status="processing", progress=10, message="Menyiapkan video sumber...")
        if uploaded_path:
            video_path = uploaded_path
        elif url:
            update_job(job_id, progress=15, message="Mengunduh video dari link...")
            video_path, title = download_media(url, work_dir, audio_only=False)
            update_job(job_id, title=title)
        else:
            raise ValueError("Harap masukkan link video atau upload file.")

        clips = process_reels_job(
            video_path=video_path,
            out_dir=out_dir,
            num_clips=num_clips,
            min_sec=min_sec,
            max_sec=max_sec,
            crop_mode=crop_mode,
            whisper_model=whisper_model,
            burn_subtitles=burn_subtitles,
            gemini_api_key=gemini_api_key,
            progress_cb=lambda p, m: update_job(job_id, progress=p, message=m),
        )

        for c in clips:
            c["url"] = f"/outputs/{job_id}/{c['filename']}"

        update_job(
            job_id,
            status="completed",
            progress=100,
            message=f"Selesai! {len(clips)} klip Reels berhasil dibuat.",
            result={"clips": clips},
        )
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc), message=f"Gagal: {exc}")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _run_vocal_task(
    job_id: str,
    url: str | None,
    uploaded_path: Path | None,
    output_format: str,
):
    work_dir = WORK_DIR / job_id
    out_dir = OUTPUT_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        update_job(job_id, status="processing", progress=10, message="Menyiapkan audio sumber...")
        if uploaded_path:
            audio_path = uploaded_path
        elif url:
            update_job(job_id, progress=20, message="Mengunduh audio dari link...")
            audio_path, title = download_media(url, work_dir, audio_only=True)
            update_job(job_id, title=title)
        else:
            raise ValueError("Harap masukkan link atau upload file audio/video.")

        stems = process_vocal_removal_job(
            audio_path=audio_path,
            out_dir=out_dir,
            output_format=output_format,
            progress_cb=lambda p, m: update_job(job_id, progress=p, message=m),
        )

        formatted = {}
        if "vocals" in stems:
            formatted["vocals_url"] = f"/outputs/{job_id}/{stems['vocals']}"
        if "instrumental" in stems:
            formatted["instrumental_url"] = f"/outputs/{job_id}/{stems['instrumental']}"

        update_job(
            job_id,
            status="completed",
            progress=100,
            message="Selesai! Vokal dan musik berhasil dipisahkan.",
            result=formatted,
        )
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc), message=f"Gagal: {exc}")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.post("/api/reels/process")
async def api_process_reels(
    url: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    num_clips: int = Form(default=3),
    min_sec: int = Form(default=20),
    max_sec: int = Form(default=55),
    crop_mode: str = Form(default="center_crop"),
    whisper_model: str = Form(default="base"),
    burn_subtitles: bool = Form(default=True),
    gemini_api_key: str | None = Form(default=None),
):
    if not url and not file:
        raise HTTPException(status_code=400, detail="Masukkan link video atau upload file.")

    title = file.filename if file else (url or "Reels Job")
    job_id = create_job("reels", title)
    uploaded_path = None

    if file and file.filename:
        work_dir = WORK_DIR / job_id
        work_dir.mkdir(parents=True, exist_ok=True)
        uploaded_path = work_dir / file.filename
        with uploaded_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

    executor.submit(
        _run_reels_task,
        job_id,
        url.strip() if url else None,
        uploaded_path,
        max(1, min(10, num_clips)),
        max(10, min_sec),
        max(15, max_sec),
        crop_mode,
        whisper_model,
        burn_subtitles,
        gemini_api_key,
    )
    return {"job_id": job_id}


@app.post("/api/vocal-remover/process")
async def api_process_vocal_remover(
    url: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    output_format: str = Form(default="mp3"),
):
    if not url and not file:
        raise HTTPException(status_code=400, detail="Masukkan link lagu atau upload file audio.")

    title = file.filename if file else (url or "Vocal Remover Job")
    job_id = create_job("vocal_remover", title)
    uploaded_path = None

    if file and file.filename:
        work_dir = WORK_DIR / job_id
        work_dir.mkdir(parents=True, exist_ok=True)
        uploaded_path = work_dir / file.filename
        with uploaded_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

    executor.submit(
        _run_vocal_task,
        job_id,
        url.strip() if url else None,
        uploaded_path,
        output_format if output_format in ("mp3", "wav") else "mp3",
    )
    return {"job_id": job_id}
