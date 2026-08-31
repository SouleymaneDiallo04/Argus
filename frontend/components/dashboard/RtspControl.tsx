"use client";

import { useCallback, useEffect, useState } from "react";
import { startRtsp, stopRtsp, rtspStatus, type RtspStatus } from "@/lib/sourcesApi";

const POLL_MS = 5000;

export function RtspControl({
  loadStatus = rtspStatus, doStart = startRtsp, doStop = stopRtsp,
}: {
  loadStatus?: typeof rtspStatus; doStart?: typeof startRtsp; doStop?: typeof stopRtsp;
}) {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<RtspStatus>({ running: false });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setStatus(await loadStatus()); } catch { /* garde le dernier statut */ }
  }, [loadStatus]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const id = setInterval(() => { if (!document.hidden) load(); }, POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  async function start() {
    if (!url.trim()) return;
    setBusy(true);
    try { setStatus(await doStart(url.trim())); } catch { /* ignore */ } finally { setBusy(false); }
  }
  async function stop() {
    setBusy(true);
    try { await doStop(); } catch { /* ignore */ } finally { setBusy(false); await load(); }
  }

  const btn = "rounded-lg px-3 py-1.5 text-[12px] font-bold";
  return (
    <div className="flex items-center gap-2.5 rounded-[10px] border border-line bg-s1 px-3 py-2">
      <span className="text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">Source RTSP</span>
      <input aria-label="URL RTSP" value={url} placeholder="rtsp://caméra/flux"
             onChange={(e) => setUrl(e.target.value)}
             className="min-w-0 flex-1 rounded-lg border border-line bg-s2 px-3 py-1.5 text-[13px] text-ink placeholder:text-ink3" />
      {status.running ? (
        <button onClick={stop} disabled={busy} className={`${btn} border border-line2 text-ink hover:bg-s2`}>Arrêter</button>
      ) : (
        <button onClick={start} disabled={busy} className={`${btn} bg-brand text-white disabled:opacity-40`}>Démarrer</button>
      )}
      <span className="flex items-center gap-1.5 text-[12px] text-ink2">
        <span className={`h-1.5 w-1.5 rounded-full ${status.running ? "bg-ok" : "bg-slate"}`} />
        {status.running
          ? `En cours · ${status.frames ?? 0} frames`
          : "Arrêté"}
      </span>
      {status.error ? <span className="text-[12px] text-crit">{status.error}</span> : null}
    </div>
  );
}
