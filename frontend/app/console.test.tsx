import { render, screen } from "@testing-library/react";
import Page from "./page";

test("la console affiche le bandeau vital, les filtres et la file d'alertes", () => {
  render(<Page />);
  expect(screen.getByRole("img", { name: /argus/i })).toBeInTheDocument();
  expect(screen.getByText(/Conformité · Site/i)).toBeInTheDocument();
  expect(screen.getByText(/File d'alertes/i)).toBeInTheDocument();
  // au moins une ligne d'alerte mock rendue
  expect(screen.getAllByText(/CRITIQUE|ÉLEVÉ|MOYEN|FAIBLE/).length).toBeGreaterThan(0);
});
