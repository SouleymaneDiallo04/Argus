import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "./AuthProvider";

function Probe() {
  const { user, ready, login, logout } = useAuth();
  return (
    <div>
      <span>ready:{String(ready)}</span>
      <span>user:{user?.username ?? "none"}</span>
      <button onClick={() => login("a", "b")}>login</button>
      <button onClick={logout}>logout</button>
    </div>
  );
}

test("AuthProvider charge le user puis logout le vide", async () => {
  render(<AuthProvider loadMe={async () => ({ username: "alice", role: "admin" })}
                       doLogin={async () => ({ access_token: "t", role: "admin" })}>
    <Probe /></AuthProvider>);
  expect(await screen.findByText("user:alice")).toBeInTheDocument();
  fireEvent.click(screen.getByText("logout"));
  await waitFor(() => expect(screen.getByText("user:none")).toBeInTheDocument());
});

test("AuthProvider met user à null si me échoue", async () => {
  render(<AuthProvider loadMe={async () => { throw new Error("401"); }}
                       doLogin={async () => ({ access_token: "t", role: "admin" })}>
    <Probe /></AuthProvider>);
  await waitFor(() => expect(screen.getByText("user:none")).toBeInTheDocument());
  expect(screen.getByText("ready:true")).toBeInTheDocument();
});
