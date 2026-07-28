import { render, screen } from "@testing-library/react";
import Page from "./page";

beforeAll(() => {
  // jsdom n'a pas WebSocket : shim inerte pour que le Workspace (hook live) ne plante pas au montage.
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

test("la console rend le shell + le sélecteur de source vidéo", () => {
  render(<Page />);
  expect(screen.getByRole("img", { name: /argus/i })).toBeInTheDocument(); // logo (NavRail)
  expect(screen.getByText(/Conformité · Site/i)).toBeInTheDocument(); // bandeau vital
  expect(screen.getByRole("button", { name: /webcam/i })).toBeInTheDocument(); // source vidéo (VideoStage)
});
