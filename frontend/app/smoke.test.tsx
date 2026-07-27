import { render, screen } from "@testing-library/react";
import Page from "./page";

test("la page racine rend le nom de la console", () => {
  render(<Page />);
  expect(screen.getByText(/Argus Ops Console/i)).toBeInTheDocument();
});
