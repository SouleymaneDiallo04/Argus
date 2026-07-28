import { render, screen } from "@testing-library/react";
import { Logo } from "./Logo";
import { MetricTile } from "./MetricTile";
import { AlertRow } from "./AlertRow";
import type { Alert } from "@/lib/types";

test("Logo rend un SVG avec un rôle/label accessible", () => {
  render(<Logo />);
  expect(screen.getByLabelText(/argus/i)).toBeInTheDocument();
});

test("MetricTile affiche libellé et valeur", () => {
  render(<MetricTile label="Critiques actives" value="3" tone="crit" />);
  expect(screen.getByText("Critiques actives")).toBeInTheDocument();
  expect(screen.getByText("3")).toBeInTheDocument();
});

test("AlertRow affiche sévérité, zone, ID et EPI manquants", () => {
  const a: Alert = {
    id: "1",
    severity: "crit",
    time: "00:12",
    zone: "Fonderie·Coulée",
    personId: "#37",
    missing: ["casque", "shoes"],
    status: "active",
  };
  render(
    <table>
      <tbody>
        <AlertRow alert={a} />
      </tbody>
    </table>
  );
  expect(screen.getByText("CRITIQUE")).toBeInTheDocument();
  expect(screen.getByText("Fonderie·Coulée")).toBeInTheDocument();
  expect(screen.getByText("#37")).toBeInTheDocument();
  expect(screen.getByText("casque")).toBeInTheDocument();
  expect(screen.getByText("Active")).toBeInTheDocument();
});
