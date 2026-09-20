import { render, screen } from "@testing-library/react";
import { Dashboard } from "./Dashboard";
import { AuthProvider } from "@/components/auth/AuthProvider";
import type { Stats } from "@/lib/statsApi";
import type { ApiEvent } from "@/lib/eventsApi";

const stats: Stats = {
  global: { person_frames: 10, compliant_frames: 9, rate: 0.9 },
  by_zone: [{ zone: "Fonderie", person_frames: 10, compliant_frames: 9, rate: 0.9 }],
  over_time: [{ bucket: "14:30", person_frames: 10, compliant_frames: 9, rate: 0.9 }],
  violations: { total: 2, by_zone: { Fonderie: 2 } },
};
const events: ApiEvent[] = [
  { id: 1, ts: "2026-08-04T12:00:00+00:00", stream_ts: 0, camera: "c",
    zone: "Fonderie", track_id: 37, missing: ["helmet"], snapshot: "a.jpg",
    status: "active" },
];

test("Dashboard charge et affiche KPI + sections + journal", async () => {
  render(<Dashboard loadStats={async () => stats} loadEvents={async () => events} />);
  expect(await screen.findByText("#37")).toBeInTheDocument();            // ligne journal (async chargé)
  expect(screen.getByText("Conformité globale")).toBeInTheDocument();    // KPI
  expect(screen.getAllByText("90%").length).toBeGreaterThan(0);          // taux affiché (KPI + zone)
  expect(screen.getByText(/conformité dans le temps/i)).toBeInTheDocument();
  expect(screen.getByText(/conformité par zone/i)).toBeInTheDocument();
  expect(screen.getByText("CSV")).toHaveAttribute("href", expect.stringContaining("/reports/events.csv"));
  expect(screen.getByText("PDF")).toHaveAttribute("href", expect.stringContaining("/reports/summary.pdf"));
});

test("Dashboard masque le contrôle RTSP pour un rôle non-admin", async () => {
  render(<AuthProvider loadMe={async () => ({ username: "op", role: "hse" })}>
    <Dashboard loadStats={async () => stats} loadEvents={async () => events} />
  </AuthProvider>);
  await screen.findByText("#37");
  expect(screen.queryByLabelText(/url rtsp/i)).toBeNull();
});

test("Dashboard montre le contrôle RTSP pour un admin", async () => {
  render(<AuthProvider loadMe={async () => ({ username: "boss", role: "admin" })}>
    <Dashboard loadStats={async () => stats} loadEvents={async () => events} />
  </AuthProvider>);
  expect(await screen.findByLabelText(/url rtsp/i)).toBeInTheDocument();
});
