import type { FrameResponse } from "@/lib/types";

type Handlers = {
  onMessage: (r: FrameResponse) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (e: unknown) => void;
};
type WSFactory = (url: string) => WebSocket;

export class StreamClient {
  private ws: WebSocket | null = null;

  constructor(
    private url: string,
    private handlers: Handlers,
    private factory: WSFactory = (u) => new WebSocket(u)
  ) {}

  connect() {
    const ws = this.factory(this.url);
    this.ws = ws;
    ws.onopen = () => this.handlers.onOpen?.();
    ws.onclose = () => this.handlers.onClose?.();
    ws.onerror = (e) => this.handlers.onError?.(e);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data as string);
        if (data && typeof data === "object" && "detections" in data) {
          this.handlers.onMessage(data as FrameResponse);
        }
      } catch {
        /* trame non-JSON : ignorée */
      }
    };
  }

  send(frame: string, timestamp: number) {
    if (this.ws && this.ws.readyState === 1 /* OPEN */) {
      this.ws.send(JSON.stringify({ frame, timestamp }));
    }
  }

  close() {
    this.ws?.close();
    this.ws = null;
  }
}
