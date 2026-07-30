import { render, screen, fireEvent } from "@testing-library/react";
import { Workspace } from "./Workspace";

beforeAll(() => {
  // @ts-expect-error shim WS
  globalThis.WebSocket = class {
    readyState = 0;
    onopen = null;
    onclose = null;
    onerror = null;
    onmessage = null;
    send() {}
    close() {}
  };
  // fetch mock : GET /zones vide
  globalThis.fetch = (async () => ({ ok: true, status: 200, json: async () => ({ zones: [] }) })) as typeof fetch;
});

test("Workspace affiche la barre de filtres et ouvre l'éditeur de zones", () => {
  render(<Workspace />);
  expect(screen.getByLabelText(/rechercher/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /éditer les zones/i }));
  expect(screen.getByText(/Nouvelle zone/i)).toBeInTheDocument();
});
