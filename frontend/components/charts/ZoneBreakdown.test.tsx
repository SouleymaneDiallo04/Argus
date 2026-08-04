import { render, screen } from "@testing-library/react";
import { ZoneBreakdown } from "./ZoneBreakdown";

const z = (zone: string, rate: number | null) => ({ zone, rate, person_frames: 1, compliant_frames: 0 });

test("ZoneBreakdown rend une ligne par zone avec le pourcentage", () => {
  render(<ZoneBreakdown data={[z("Fonderie", 0.8), z("Bureau", 1)]} />);
  expect(screen.getByText("Fonderie")).toBeInTheDocument();
  expect(screen.getByText("80%")).toBeInTheDocument();
  expect(screen.getByText("100%")).toBeInTheDocument();
});
