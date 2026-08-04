import { render, screen } from "@testing-library/react";
import { NavRail } from "./NavRail";

test("NavRail lie les routes et surligne l'item actif", () => {
  render(<NavRail active="analytique" />);
  const analytique = screen.getByTitle("Analytique");
  expect(analytique).toHaveAttribute("href", "/dashboard");
  expect(analytique).toHaveAttribute("aria-current", "page");
  expect(screen.getByTitle("Live")).toHaveAttribute("href", "/");
});
