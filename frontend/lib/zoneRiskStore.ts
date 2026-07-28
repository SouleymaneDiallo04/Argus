import type { ZoneRisk } from "./priority";

const KEY = "argus.zoneRisk";
type Store = Record<string, ZoneRisk>;

function read(): Store {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Store;
  } catch {
    return {};
  }
}

export function getZoneRisk(name: string): ZoneRisk | undefined {
  return read()[name];
}

export function setZoneRisk(name: string, risk: ZoneRisk): void {
  const s = read();
  s[name] = risk;
  localStorage.setItem(KEY, JSON.stringify(s));
}
