import { render, screen, fireEvent } from "@testing-library/react";
import { DashboardFilters, type DashFilters } from "./DashboardFilters";

test("DashboardFilters remonte EPI et plage", () => {
  let last: DashFilters = { zone: "", ppe: "", range: "day", status: "" };
  render(<DashboardFilters filters={last} onChange={(f) => (last = f)} />);
  fireEvent.change(screen.getByLabelText(/epi/i), { target: { value: "helmet" } });
  expect(last.ppe).toBe("helmet");
  fireEvent.change(screen.getByLabelText(/période/i), { target: { value: "hour" } });
  expect(last.range).toBe("hour");
});

test("DashboardFilters remonte le statut", () => {
  let last: DashFilters = { zone: "", ppe: "", range: "day", status: "" };
  render(<DashboardFilters filters={last} onChange={(f) => (last = f)} />);
  fireEvent.change(screen.getByLabelText(/statut/i), { target: { value: "ack" } });
  expect(last.status).toBe("ack");
});
