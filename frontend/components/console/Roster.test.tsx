import { render, screen } from "@testing-library/react";
import { Roster } from "./Roster";

test("Roster affiche l'ID, le statut et les EPI manquants", () => {
  render(
    <Roster
      entries={[
        { trackId: 8, zone: "z", missing: [], compliant: true },
        { trackId: 37, zone: "z", missing: ["casque", "shoes"], compliant: false },
      ]}
    />
  );
  expect(screen.getByText("#08")).toBeInTheDocument();
  expect(screen.getByText("#37")).toBeInTheDocument();
  expect(screen.getByText("casque")).toBeInTheDocument();
  expect(screen.getAllByText(/conforme|✓/i).length).toBeGreaterThan(0);
});
