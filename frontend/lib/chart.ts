export function scaleY(rate: number, height: number): number {
  const r = Math.max(0, Math.min(1, rate));
  return height - r * height;
}

export function barWidth(rate: number | null, maxW: number): number {
  if (rate === null) return 0;
  return Math.max(0, Math.min(1, rate)) * maxW;
}

export type TrendPoint = { x: number; y: number };

export function trendSegments(
  rates: (number | null)[], width: number, height: number,
): TrendPoint[][] {
  const n = rates.length;
  const segs: TrendPoint[][] = [];
  let cur: TrendPoint[] = [];
  rates.forEach((r, i) => {
    if (r === null) {
      if (cur.length) { segs.push(cur); cur = []; }
      return;
    }
    const x = n === 1 ? 0 : (i / (n - 1)) * width;
    cur.push({ x, y: scaleY(r, height) });
  });
  if (cur.length) segs.push(cur);
  return segs;
}
