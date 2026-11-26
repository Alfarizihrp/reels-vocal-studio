import { useEffect, useState } from "react";
import {
  Scissors,
  Music,
  Link as LinkIcon,
  Upload,
  Download,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Mic,
  Disc,
} from "lucide-react";

function JobStatusCard({ job }) {
  if (!job) return null;

  const isDone = job.status === "completed";
  const isFailed = job.status === "failed";

  return (
    <div className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {isDone ? (
            <CheckCircle2 className="h-5 w-5 text-emerald-400" />
          ) : isFailed ? (
            <AlertCircle className="h-5 w-5 text-rose-400" />
          ) : (
            <Loader2 className="h-5 w-5 animate-spin text-violet-400" />
          )}
          <span className="font-medium text-slate-100">{job.title}</span>
        </div>
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {job.progress}%
        </span>
      </div>

      <p className="mt-2 text-sm text-slate-300">{job.message}</p>

      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full transition-all duration-300 ${
            isFailed ? "bg-rose-500" : isDone ? "bg-emerald-500" : "bg-violet-500"
          }`}
          style={{ width: `${job.progress}%` }}
        />
      </div>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("reels");
  const [health, setHealth] = useState(null);
  const [apiBase, setApiBase] = useState(() => {
    const saved = localStorage.getItem("rvs_api_base");
    if (saved !== null) return saved;
    return import.meta.env.VITE_API_BASE_URL || "";
  });

  const apiUrl = (path) => {
    const base = apiBase.trim().replace(/\/+$/, "");
    return base ? `${base}${path}` : path;
  };

  // Reels state
  const [reelsInputType, setReelsInputType] = useState("link");
  const [reelsUrl, setReelsUrl] = useState("");
  const [reelsFile, setReelsFile] = useState(null);
  const [numClips, setNumClips] = useState(3);
  const [minSec, setMinSec] = useState(20);
  const [maxSec, setMaxSec] = useState(55);
  const [cropMode, setCropMode] = useState("center_crop");
  const [whisperModel, setWhisperModel] = useState("base");
  const [burnSubtitles, setBurnSubtitles] = useState(true);
  const [geminiKey, setGeminiKey] = useState("");
  const [reelsJob, setReelsJob] = useState(null);
  const [reelsSubmitting, setReelsSubmitting] = useState(false);

  // Vocal remover state
  const [vocalInputType, setVocalInputType] = useState("link");
  const [vocalUrl, setVocalUrl] = useState("");
  const [vocalFile, setVocalFile] = useState(null);
  const [outputFormat, setOutputFormat] = useState("mp3");
  const [vocalJob, setVocalJob] = useState(null);
  const [vocalSubmitting, setVocalSubmitting] = useState(false);

  useEffect(() => {
    setHealth(null);
    fetch(apiUrl("/api/health"))
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: "offline" }));
  }, [apiBase]);

  // Poll active jobs
  useEffect(() => {
    const activeIds = [];
    if (reelsJob && ["queued", "processing"].includes(reelsJob.status)) {
      activeIds.push(["reels", reelsJob.id]);
    }
    if (vocalJob && ["queued", "processing"].includes(vocalJob.status)) {
      activeIds.push(["vocal", vocalJob.id]);
    }
    if (activeIds.length === 0) return;

    const timer = setInterval(async () => {
      for (const [kind, id] of activeIds) {
        try {
          const res = await fetch(apiUrl(`/api/jobs/${id}`));
          if (res.ok) {
            const data = await res.json();
            if (kind === "reels") setReelsJob(data);
            else setVocalJob(data);
          }
        } catch {
          // ignore transient network errors
        }
      }
    }, 1500);

    return () => clearInterval(timer);
  }, [reelsJob, vocalJob]);

  async function submitReels(e) {
    e.preventDefault();
    if (reelsInputType === "link" && !reelsUrl.trim()) return;
    if (reelsInputType === "file" && !reelsFile) return;

    setReelsSubmitting(true);
    try {
      const fd = new FormData();
      if (reelsInputType === "link") fd.append("url", reelsUrl.trim());
      else fd.append("file", reelsFile);
      fd.append("num_clips", String(numClips));
      fd.append("min_sec", String(minSec));
      fd.append("max_sec", String(maxSec));
      fd.append("crop_mode", cropMode);
      fd.append("whisper_model", whisperModel);
      fd.append("burn_subtitles", String(burnSubtitles));
      if (geminiKey.trim()) fd.append("gemini_api_key", geminiKey.trim());

      const res = await fetch(apiUrl("/api/reels/process"), { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal memulai proses");
      setReelsJob({
        id: data.job_id,
        title: reelsInputType === "link" ? reelsUrl : reelsFile.name,
        status: "queued",
        progress: 5,
        message: "Masuk antrean...",
      });
    } catch (err) {
      alert(err.message);
    } finally {
      setReelsSubmitting(false);
    }
  }

  async function submitVocal(e) {
    e.preventDefault();
    if (vocalInputType === "link" && !vocalUrl.trim()) return;
    if (vocalInputType === "file" && !vocalFile) return;

    setVocalSubmitting(true);
    try {
      const fd = new FormData();
      if (vocalInputType === "link") fd.append("url", vocalUrl.trim());
      else fd.append("file", vocalFile);
      fd.append("output_format", outputFormat);

      const res = await fetch(apiUrl("/api/vocal-remover/process"), { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal memulai proses");
      setVocalJob({
        id: data.job_id,
        title: vocalInputType === "link" ? vocalUrl : vocalFile.name,
        status: "queued",
        progress: 5,
        message: "Masuk antrean...",
      });
    } catch (err) {
      alert(err.message);
    } finally {
      setVocalSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800/80 bg-slate-900/50 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 shadow-lg shadow-violet-500/20">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">Reels & Vocal Studio</h1>
              <p className="text-xs text-slate-400">Local CPU Mode • Personal Content Toolkit</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <input
              type="url"
              value={apiBase}
              onChange={(e) => {
                setApiBase(e.target.value);
                localStorage.setItem("rvs_api_base", e.target.value);
              }}
              placeholder="Backend URL (kosongkan jika lokal)"
              className="w-60 rounded-full border border-slate-800 bg-slate-950 px-3.5 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-violet-500 focus:outline-none"
            />
            <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs">
            <span
              className={`h-2 w-2 rounded-full ${
                health?.status === "ok" ? "bg-emerald-400" : "bg-rose-400"
              }`}
            />
            <span className="text-slate-300">
              {health?.status === "ok"
                ? `Backend Ready (${health.ffmpeg_ready ? "FFmpeg OK" : "No FFmpeg"})`
                : "Backend Offline"}
            </span>
          </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {/* Menu Tabs */}
        <div className="grid grid-cols-2 gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-1.5">
          <button
            onClick={() => setTab("reels")}
            className={`flex items-center justify-center gap-2.5 rounded-xl py-3 text-sm font-semibold transition ${
              tab === "reels"
                ? "bg-violet-600 text-white shadow-lg shadow-violet-600/25"
                : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
            }`}
          >
            <Scissors className="h-4 w-4" />
            Potong Video Reels
          </button>

          <button
            onClick={() => setTab("vocal")}
            className={`flex items-center justify-center gap-2.5 rounded-xl py-3 text-sm font-semibold transition ${
              tab === "vocal"
                ? "bg-emerald-600 text-white shadow-lg shadow-emerald-600/25"
                : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
            }`}
          >
            <Music className="h-4 w-4" />
            Hapus Musik / Pisah Vokal
          </button>
        </div>

        {/* TAB 1: REELS CLIPPER */}
        {tab === "reels" && (
          <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
            <h2 className="text-lg font-semibold">Auto-Clipper Video Reels (9:16)</h2>
            <p className="mt-1 text-sm text-slate-400">
              Masukkan link YouTube/TikTok/IG atau upload video lokal. Sistem akan mentranskrip dan memilih momen terbaik otomatis.
            </p>

            <form onSubmit={submitReels} className="mt-5 space-y-5">
              {/* Input Source Toggle */}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setReelsInputType("link")}
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-medium border ${
                    reelsInputType === "link"
                      ? "border-violet-500 bg-violet-500/15 text-violet-300"
                      : "border-slate-800 bg-slate-900 text-slate-400"
                  }`}
                >
                  <LinkIcon className="h-3.5 w-3.5" /> Paste Link Video
                </button>
                <button
                  type="button"
                  onClick={() => setReelsInputType("file")}
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-medium border ${
                    reelsInputType === "file"
                      ? "border-violet-500 bg-violet-500/15 text-violet-300"
                      : "border-slate-800 bg-slate-900 text-slate-400"
                  }`}
                >
                  <Upload className="h-3.5 w-3.5" /> Upload File Video
                </button>
              </div>

              {reelsInputType === "link" ? (
                <input
                  type="url"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={reelsUrl}
                  onChange={(e) => setReelsUrl(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:border-violet-500 focus:outline-none"
                  required
                />
              ) : (
                <input
                  type="file"
                  accept="video/*"
                  onChange={(e) => setReelsFile(e.target.files?.[0] || null)}
                  className="w-full rounded-xl border border-dashed border-slate-700 bg-slate-950 px-4 py-4 text-sm text-slate-300 file:mr-4 file:rounded-lg file:border-0 file:bg-violet-600 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-white hover:file:bg-violet-500"
                  required
                />
              )}

              {/* Settings Grid */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400">Jumlah Klip</label>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={numClips}
                    onChange={(e) => setNumClips(Number(e.target.value))}
                    className="mt-1.5 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400">Durasi (detik)</label>
                  <div className="mt-1.5 flex items-center gap-2">
                    <input
                      type="number"
                      min={10}
                      max={60}
                      value={minSec}
                      onChange={(e) => setMinSec(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    />
                    <span className="text-slate-500">-</span>
                    <input
                      type="number"
                      min={15}
                      max={120}
                      value={maxSec}
                      onChange={(e) => setMaxSec(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400">Format 9:16</label>
                  <select
                    value={cropMode}
                    onChange={(e) => setCropMode(e.target.value)}
                    className="mt-1.5 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                  >
                    <option value="center_crop">Center Crop (Penuh)</option>
                    <option value="fit_blur">Fit + Blur Background</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400">Model Whisper (CPU)</label>
                  <select
                    value={whisperModel}
                    onChange={(e) => setWhisperModel(e.target.value)}
                    className="mt-1.5 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                  >
                    <option value="tiny">Tiny (Paling Cepat)</option>
                    <option value="base">Base (Seimbang)</option>
                    <option value="small">Small (Lebih Akurat)</option>
                  </select>
                </div>
              </div>

              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={burnSubtitles}
                    onChange={(e) => setBurnSubtitles(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-700 accent-violet-600"
                  />
                  Tambahkan Subtitle Otomatis ke Video
                </label>

                <input
                  type="password"
                  placeholder="Gemini API Key (opsional, untuk AI pilih klip lebih pintar)"
                  value={geminiKey}
                  onChange={(e) => setGeminiKey(e.target.value)}
                  className="w-full sm:w-80 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200 placeholder-slate-500"
                />
              </div>

              <button
                type="submit"
                disabled={reelsSubmitting}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-violet-600 py-3 text-sm font-semibold text-white transition hover:bg-violet-500 disabled:opacity-50"
              >
                {reelsSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Scissors className="h-4 w-4" />}
                Generate Potongan Reels
              </button>
            </form>

            <JobStatusCard job={reelsJob} />

            {reelsJob?.status === "completed" && reelsJob.result?.clips && (
              <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-3">
                {reelsJob.result.clips.map((clip) => (
                  <div
                    key={clip.index}
                    className="flex flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-950"
                  >
                    <video
                      src={apiUrl(clip.url)}
                      controls
                      className="aspect-[9/16] w-full bg-black object-contain"
                    />
                    <div className="flex flex-1 flex-col justify-between p-4">
                      <div>
                        <div className="flex items-center justify-between text-xs text-violet-400 font-semibold">
                          <span>Klip #{clip.index}</span>
                          <span>{clip.duration}s</span>
                        </div>
                        <h3 className="mt-1 text-sm font-semibold text-slate-100 line-clamp-2">
                          {clip.title}
                        </h3>
                        <p className="mt-1 text-xs text-slate-400">{clip.reason}</p>
                      </div>
                      <a
                        href={apiUrl(clip.url)}
                        download={clip.filename}
                        className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-slate-800 py-2 text-xs font-semibold text-slate-100 hover:bg-slate-700"
                      >
                        <Download className="h-3.5 w-3.5" /> Download MP4
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* TAB 2: VOCAL / MUSIC REMOVER */}
        {tab === "vocal" && (
          <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
            <h2 className="text-lg font-semibold">Penghapus Musik & Pemisah Vokal</h2>
            <p className="mt-1 text-sm text-slate-400">
              Pisahkan suara vokal bersih (tanpa musik) dan trek instrumental (karaoke) dari lagu atau link video.
            </p>

            <form onSubmit={submitVocal} className="mt-5 space-y-5">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setVocalInputType("link")}
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-medium border ${
                    vocalInputType === "link"
                      ? "border-emerald-500 bg-emerald-500/15 text-emerald-300"
                      : "border-slate-800 bg-slate-900 text-slate-400"
                  }`}
                >
                  <LinkIcon className="h-3.5 w-3.5" /> Paste Link Lagu/Video
                </button>
                <button
                  type="button"
                  onClick={() => setVocalInputType("file")}
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-medium border ${
                    vocalInputType === "file"
                      ? "border-emerald-500 bg-emerald-500/15 text-emerald-300"
                      : "border-slate-800 bg-slate-900 text-slate-400"
                  }`}
                >
                  <Upload className="h-3.5 w-3.5" /> Upload File Audio/Video
                </button>
              </div>

              {vocalInputType === "link" ? (
                <input
                  type="url"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={vocalUrl}
                  onChange={(e) => setVocalUrl(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
                  required
                />
              ) : (
                <input
                  type="file"
                  accept="audio/*,video/*"
                  onChange={(e) => setVocalFile(e.target.files?.[0] || null)}
                  className="w-full rounded-xl border border-dashed border-slate-700 bg-slate-950 px-4 py-4 text-sm text-slate-300 file:mr-4 file:rounded-lg file:border-0 file:bg-emerald-600 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-white hover:file:bg-emerald-500"
                  required
                />
              )}

              <div className="w-full sm:w-56">
                <label className="block text-xs font-medium text-slate-400">Format Output Audio</label>
                <select
                  value={outputFormat}
                  onChange={(e) => setOutputFormat(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                >
                  <option value="mp3">MP3 (Ringan)</option>
                  <option value="wav">WAV (Lossless)</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={vocalSubmitting}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 py-3 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:opacity-50"
              >
                {vocalSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Music className="h-4 w-4" />}
                Pisahkan Vokal & Musik
              </button>
            </form>

            <JobStatusCard job={vocalJob} />

            {vocalJob?.status === "completed" && vocalJob.result && (
              <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
                {vocalJob.result.vocals_url && (
                  <div className="rounded-2xl border border-slate-800 bg-slate-950 p-5">
                    <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
                      <Mic className="h-4 w-4" /> Vokal Saja (Musik Dihapus)
                    </div>
                    <audio src={apiUrl(vocalJob.result.vocals_url)} controls className="mt-3 w-full" />
                    <a
                      href={apiUrl(vocalJob.result.vocals_url)}
                      download
                      className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-emerald-600/20 py-2 text-xs font-semibold text-emerald-300 hover:bg-emerald-600/30"
                    >
                      <Download className="h-3.5 w-3.5" /> Download Vokal
                    </a>
                  </div>
                )}

                {vocalJob.result.instrumental_url && (
                  <div className="rounded-2xl border border-slate-800 bg-slate-950 p-5">
                    <div className="flex items-center gap-2 text-sky-400 font-semibold text-sm">
                      <Disc className="h-4 w-4" /> Musik / Instrumental Saja
                    </div>
                    <audio src={apiUrl(vocalJob.result.instrumental_url)} controls className="mt-3 w-full" />
                    <a
                      href={apiUrl(vocalJob.result.instrumental_url)}
                      download
                      className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-sky-600/20 py-2 text-xs font-semibold text-sky-300 hover:bg-sky-600/30"
                    >
                      <Download className="h-3.5 w-3.5" /> Download Instrumental
                    </a>
                  </div>
                )}
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
