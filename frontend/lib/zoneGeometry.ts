import type { ApiZone } from "./zonesApi";

export function toFramePolygon(points: [number, number][], scaleX: number, scaleY: number): [number, number][] {
  return points.map(([x, y]) => [Math.round(x * scaleX), Math.round(y * scaleY)]);
}

export function buildZoneModel(name: string, framePolygon: [number, number][], ppe: string[]): ApiZone {
  return { name, polygon: framePolygon, required_ppe: ppe };
}
