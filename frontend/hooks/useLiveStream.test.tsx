import { renderHook, act } from "@testing-library/react";
import { useLiveStream } from "./useLiveStream";

// jsdom n'a pas WebSocket : on fournit un faux global inerte.
beforeAll(() => {
  // @ts-expect-error test shim
  globalThis.WebSocket = class {
    readyState = 0;
    onopen: (() => void) | null = null;
    onclose: (() => void) | null = null;
    onerror: (() => void) | null = null;
    onmessage: (() => void) | null = null;
    send() {}
    close() {}
  };
});

test("useLiveStream démarre en 'connecting' et expose une API", () => {
  const { result } = renderHook(() => useLiveStream());
  expect(result.current.status).toBe("connecting");
  expect(typeof result.current.sendFrame).toBe("function");
  act(() => result.current.stop());
});
