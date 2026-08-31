import { render, screen, fireEvent } from "@testing-library/react";
import { JournalTable } from "./JournalTable";
import type { ApiEvent } from "@/lib/eventsApi";

const ev = (over: Partial<ApiEvent>): ApiEvent => ({
  id: 1, ts: "2026-08-04T12:00:00+00:00", stream_ts: 0, camera: "cam-1",
  zone: "Fonderie", track_id: 37, missing: ["helmet"], snapshot: "a.jpg",
  status: "active", ...over,
});

test("JournalTable rend une ligne par event avec vignette et sévérité", () => {
  render(<JournalTable events={[ev({})]} />);
  expect(screen.getByText("Fonderie")).toBeInTheDocument();
  expect(screen.getByText("#37")).toBeInTheDocument();
  const img = screen.getByRole("img", { name: /preuve/i });
  expect(img).toHaveAttribute("src", expect.stringContaining("/events/1/snapshot"));
});

test("JournalTable montre un tiret quand pas de snapshot", () => {
  render(<JournalTable events={[ev({ id: 2, snapshot: null })]} />);
  expect(screen.queryByRole("img", { name: /preuve/i })).toBeNull();
});

test("JournalTable montre le statut et remonte les actions", () => {
  const calls: [number, string][] = [];
  render(<JournalTable events={[ev({ status: "active" })]}
                       onSetStatus={(id, s) => calls.push([id, s])} />);
  expect(screen.getByText("Active")).toBeInTheDocument();       // StatusBadge
  fireEvent.click(screen.getByText("Acquitter"));
  fireEvent.click(screen.getByText("Résoudre"));
  expect(calls).toEqual([[1, "ack"], [1, "resolved"]]);
});
