import { render, screen, fireEvent } from "@testing-library/react";
import { FilterBar } from "./FilterBar";

test("FilterBar remonte la recherche et le filtre EPI", () => {
  let last: Record<string, unknown> = {};
  render(<FilterBar filters={{}} onChange={(f) => (last = f)} />);
  fireEvent.change(screen.getByLabelText(/rechercher/i), { target: { value: "#37" } });
  expect(last).toMatchObject({ query: "#37" });
  fireEvent.change(screen.getByLabelText(/epi/i), { target: { value: "helmet" } });
  expect(last).toMatchObject({ ppe: "helmet" });
});
