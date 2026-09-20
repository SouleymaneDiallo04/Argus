import { vi } from "vitest";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import { render, screen, waitFor } from "@testing-library/react";
import { Shell } from "./Shell";
import { AuthProvider } from "@/components/auth/AuthProvider";

test("Shell redirige vers /login si non connecté", async () => {
  render(<AuthProvider loadMe={async () => { throw new Error("401"); }}>
    <Shell active="live"><div>contenu</div></Shell></AuthProvider>);
  await waitFor(() => expect(push).toHaveBeenCalledWith("/login"));
});

test("Shell rend le contenu si connecté", async () => {
  render(<AuthProvider loadMe={async () => ({ username: "a", role: "admin" })}>
    <Shell active="live"><div>contenu</div></Shell></AuthProvider>);
  expect(await screen.findByText("contenu")).toBeInTheDocument();
});
