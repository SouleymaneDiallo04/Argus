"use client";

import { useEffect, useRef, useState } from "react";
import { detectionsToBoxes } from "@/lib/overlay";
import type { FrameResponse } from "@/lib/types";

export function VideoStage({
  response,
  onFrame,
}: {
  response: FrameResponse | null;
  onFrame: (video: HTMLVideoElement, canvas: HTMLCanvasElement) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const sampleCanvas = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const [source, setSource] = useState<"none" | "webcam" | "file">("none");

  // échantillonnage périodique (~7 i/s) tant qu'une source joue
  useEffect(() => {
    if (source === "none") return;
    const id = setInterval(() => {
      const v = videoRef.current,
        c = sampleCanvas.current;
      if (v && c && v.readyState >= 2) onFrame(v, c);
    }, 140);
    return () => clearInterval(id);
  }, [source, onFrame]);

  // dessin des overlays à chaque réponse
  useEffect(() => {
    const v = videoRef.current,
      o = overlayRef.current;
    if (!v || !o || !response) return;
    o.width = v.clientWidth;
    o.height = v.clientHeight;
    const ctx = o.getContext("2d");
    if (!ctx || !v.videoWidth) return;
    ctx.clearRect(0, 0, o.width, o.height);
    const boxes = detectionsToBoxes(
      response.detections,
      response.results,
      o.width / v.videoWidth,
      o.height / v.videoHeight
    );
    ctx.lineWidth = 2;
    ctx.font = "12px ui-monospace, monospace";
    for (const b of boxes) {
      ctx.strokeStyle = b.color;
      ctx.strokeRect(b.x, b.y, b.w, b.h);
      ctx.fillStyle = b.color;
      ctx.fillRect(b.x, b.y - 15, ctx.measureText(b.label).width + 10, 15);
      ctx.fillStyle = "#04140c";
      ctx.fillText(b.label, b.x + 5, b.y - 4);
    }
  }, [response]);

  async function useWebcam() {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setSource("webcam");
    }
  }
  function useFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file && videoRef.current) {
      videoRef.current.srcObject = null;
      videoRef.current.src = URL.createObjectURL(file);
      videoRef.current.play();
      setSource("file");
    }
  }

  return (
    <div className="relative flex-1 overflow-hidden rounded-[10px] border border-line2 bg-[#06080d]">
      <video ref={videoRef} className="h-full w-full object-contain" muted playsInline />
      <canvas ref={overlayRef} className="pointer-events-none absolute inset-0 h-full w-full" />
      <canvas ref={sampleCanvas} className="hidden" />
      {source === "none" ? (
        <div className="absolute inset-0 grid place-items-center gap-3">
          <div className="flex gap-2.5">
            <button onClick={useWebcam} className="rounded-lg bg-brand px-4 py-2 text-[13px] font-bold text-white">
              Webcam
            </button>
            <label className="cursor-pointer rounded-lg border border-line2 px-4 py-2 text-[13px] font-bold text-ink hover:bg-s2">
              Charger une vidéo
              <input type="file" accept="video/*" className="hidden" onChange={useFile} />
            </label>
          </div>
        </div>
      ) : null}
    </div>
  );
}
