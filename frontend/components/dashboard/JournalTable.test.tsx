import { render, screen } from "@testing-library/react";
import { JournalTable } from "./JournalTable";
import type { ApiEvent } from "@/lib/eventsApi";

const ev = (over: Partial<ApiEvent>): ApiEvent => ({
  id: 1, ts: "2026-08-04T12:00:00+00:00", stream_ts: 0, camera: "cam-1",
  zone: "Fonderie", track_id: 37, missing: ["helmet"], snapshot: "a.jpg", ...over,
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
