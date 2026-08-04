import { Shell } from "@/components/console/Shell";
import { Dashboard } from "@/components/dashboard/Dashboard";

export default function DashboardPage() {
  return (
    <Shell active="analytique">
      <Dashboard />
    </Shell>
  );
}
