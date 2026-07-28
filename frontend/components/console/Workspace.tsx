"use client";

import { useMemo } from "react";
import { useLiveStream } from "@/hooks/useLiveStream";
import { rosterFromResults, alertFromEvent } from "@/lib/live";
import { riskOf } from "@/lib/zoneRisk";
import { VideoStage } from "./VideoStage";
import { Roster } from "./Roster";
import { AlertsPanel } from "./AlertsPanel";
import { MetricTile } from "@/components/ui/MetricTile";
import type { Alert } from "@/lib/types";

export function Workspace() {
  const { response, sendFrame, status } = useLiveStream();

  const roster = useMemo(() => (response ? rosterFromResults(response.results) : []), [response]);
  const alerts: Alert[] = useMemo(
    () => (response ? response.events.map((e) => alertFromEvent(e, riskOf)) : []),
    [response]
  );
  const nonCompliant = roster.filter((r) => !r.compliant).length;

  return (
    <div className="grid min-h-0 grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] gap-3.5 overflow-hidden p-3.5">
      <div className="flex min-h-0 flex-col gap-3.5">
        <VideoStage response={response} onFrame={sendFrame} />
        <div className="grid grid-cols-4 gap-2.5">
          <MetricTile label="Personnes" value={String(roster.length)} />
          <MetricTile label="Non conformes" value={String(nonCompliant)} tone="crit" />
          <MetricTile label="Alertes" value={String(alerts.length)} tone="warn" />
          <MetricTile
            label="Service"
            value={status === "open" ? "OK" : "…"}
            tone={status === "open" ? "ok" : "default"}
          />
        </div>
      </div>
      <div className="grid min-h-0 grid-rows-2 gap-3.5">
        <Roster entries={roster} />
        <AlertsPanel alerts={alerts} />
      </div>
    </div>
  );
}
