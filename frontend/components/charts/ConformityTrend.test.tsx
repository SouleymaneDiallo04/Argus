import { render, screen } from "@testing-library/react";
import { ConformityTrend } from "./ConformityTrend";

const b = (bucket: string, rate: number | null) => ({ bucket, rate, person_frames: 1, compliant_frames: 0 });

test("ConformityTrend rend une polyline par segment continu", () => {
  const { container } = render(
    <ConformityTrend data={[b("14:30", 0.5), b("14:31", null), b("14:32", 1), b("14:33", 1)]} />);
  expect(container.querySelectorAll("polyline")).toHaveLength(2);
});

test("ConformityTrend affiche un vide sans données", () => {
  render(<ConformityTrend data={[]} />);
  expect(screen.getByText(/aucune donnée/i)).toBeInTheDocument();
});
