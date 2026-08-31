import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RtspControl } from "./RtspControl";
import type { RtspStatus } from "@/lib/sourcesApi";

test("RtspControl affiche le champ et démarre le flux", async () => {
  let started = "";
  const doStart = async (url: string) => { started = url; return { running: true, url } as RtspStatus; };
  render(<RtspControl loadStatus={async () => ({ running: false })}
                      doStart={doStart} doStop={async () => {}} />);
  const input = await screen.findByLabelText(/url rtsp/i);
  fireEvent.change(input, { target: { value: "rtsp://cam" } });
  fireEvent.click(screen.getByRole("button", { name: /démarrer/i }));
  await waitFor(() => expect(started).toBe("rtsp://cam"));
});

test("RtspControl affiche 'En cours' et le bouton Arrêter quand actif", async () => {
  render(<RtspControl loadStatus={async () => ({ running: true, url: "rtsp://cam", frames: 12 })}
                      doStart={async () => ({ running: true })} doStop={async () => {}} />);
  expect(await screen.findByText(/en cours/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /arrêter/i })).toBeInTheDocument();
});
