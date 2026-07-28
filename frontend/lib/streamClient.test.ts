import { StreamClient } from "./streamClient";

class FakeWS {
  readyState = 1; // OPEN
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  constructor(public url: string) {}
  send(s: string) {
    this.sent.push(s);
  }
  close() {
    this.readyState = 3;
    this.onclose?.();
  }
  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}

test("send sérialise frame+timestamp quand la socket est ouverte", () => {
  let fake!: FakeWS;
  const c = new StreamClient("ws://x", { onMessage: () => {} }, (u) => (fake = new FakeWS(u)) as unknown as WebSocket);
  c.connect();
  c.send("BASE64", 1.5);
  expect(JSON.parse(fake.sent[0])).toEqual({ frame: "BASE64", timestamp: 1.5 });
});

test("onMessage reçoit un FrameResponse et ignore les {error}", () => {
  let fake!: FakeWS;
  const received: unknown[] = [];
  const c = new StreamClient(
    "ws://x",
    { onMessage: (r) => received.push(r) },
    (u) => (fake = new FakeWS(u)) as unknown as WebSocket
  );
  c.connect();
  fake.emit({ error: "frame illisible" });
  fake.emit({ detections: [], results: [], events: [] });
  expect(received).toHaveLength(1);
  expect(received[0]).toEqual({ detections: [], results: [], events: [] });
});
