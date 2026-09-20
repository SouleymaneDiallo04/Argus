import { render, screen, fireEvent } from "@testing-library/react";
import { Workspace } from "./Workspace";
import { AuthProvider } from "@/components/auth/AuthProvider";

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

test("Workspace affiche la barre de filtres et ouvre l'éditeur de zones", async () => {
  render(<AuthProvider loadMe={async () => ({ username: "admin", role: "admin" })}>
    <Workspace /></AuthProvider>);
  expect(screen.getByLabelText(/rechercher/i)).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: /éditer les zones/i }));
  expect(screen.getByText(/Nouvelle zone/i)).toBeInTheDocument();
});
