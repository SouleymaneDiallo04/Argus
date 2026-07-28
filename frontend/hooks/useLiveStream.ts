"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { StreamClient } from "@/lib/streamClient";
import { grabFrame } from "@/lib/sampler";
import type { FrameResponse } from "@/lib/types";

const WS_URL = process.env.NEXT_PUBLIC_ARGUS_WS ?? "ws://localhost:8000/ws/stream";

export type StreamStatus = "connecting" | "open" | "closed";

export function useLiveStream() {
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const [response, setResponse] = useState<FrameResponse | null>(null);
  const clientRef = useRef<StreamClient | null>(null);
  const startRef = useRef<number>(Date.now());

  useEffect(() => {
    const client = new StreamClient(WS_URL, {
      onMessage: setResponse,
      onOpen: () => setStatus("open"),
      onClose: () => setStatus("closed"),
      onError: () => setStatus("closed"),
    });
    clientRef.current = client;
    client.connect();
    return () => client.close();
  }, []);

  const sendFrame = useCallback((video: HTMLVideoElement, canvas: HTMLCanvasElement) => {
    const frame = grabFrame(video, canvas);
    if (frame) clientRef.current?.send(frame, (Date.now() - startRef.current) / 1000);
  }, []);

  const stop = useCallback(() => clientRef.current?.close(), []);

  return { status, response, sendFrame, stop };
}
