import { render, screen } from "@testing-library/react";
import { SeverityTag } from "./SeverityTag";
import { StatusBadge } from "./StatusBadge";
import { PpeChip } from "./PpeChip";

test("SeverityTag affiche le libellé FR et porte la couleur de rôle", () => {
  render(<SeverityTag severity="crit" />);
  const el = screen.getByText("CRITIQUE");
  expect(el).toBeInTheDocument();
  expect(el.className).toMatch(/crit/);
});

test("StatusBadge affiche les 3 états", () => {
  const { rerender } = render(<StatusBadge status="active" />);
  expect(screen.getByText("Active")).toBeInTheDocument();
  rerender(<StatusBadge status="ack" />);
  expect(screen.getByText("Acquittée")).toBeInTheDocument();
  rerender(<StatusBadge status="resolved" />);
  expect(screen.getByText("Résolue")).toBeInTheDocument();
});

test("PpeChip affiche l'EPI", () => {
  render(<PpeChip label="casque" />);
  expect(screen.getByText("casque")).toBeInTheDocument();
});
