import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { HeatmapChart, LineChart } from "echarts/charts";
import {
  CalendarComponent, DataZoomComponent, GridComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([HeatmapChart, LineChart, CalendarComponent, DataZoomComponent, GridComponent, MarkAreaComponent,
  MarkLineComponent, TooltipComponent, VisualMapComponent, CanvasRenderer]);

/** A colour token from styles.css, read when a chart is drawn, so chart text, grid and axes follow the light or dark
 *  theme. The state colours and the outage ramp below are fixed: they are the validated palette (D-027). */
function token(name: string, fallback: string): string {
  try {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
  } catch {
    return fallback;
  }
}

export const C = {
  get ink1() { return token("--ink-1", "#0b0b0b"); },
  get ink2() { return token("--ink-2", "#52514e"); },
  get ink3() { return token("--ink-3", "#6f6d68"); },
  get grid() { return token("--grid", "#e1e0d9"); },
  get axis() { return token("--axis", "#c3c2b7"); },
  get surface() { return token("--surface-1", "#fcfcfb"); },
  // text on heat-map cells, which are light orange or hatched paper in both themes; white on the darkest ramp step
  cellInk: "#0b0b0b", cellInkDark: "#ffffff", cellInk2: "#3f3e3a",
  outage: "#eb6834", low: "#2a78d6", high: "#1baf7a", nodata: "#98a2b3",
  // single-hue orange sequential ramp for outage minutes per day (OKLCH, lightness strictly decreasing)
  ramp: ["#ffede5", "#ffd2c0", "#ffb295", "#f78d66", "#e96a38", "#9b411d"],
};

/** Text for chart tooltips, which ECharts renders as HTML: every value placed in a tooltip goes through this, so a
 *  name from an uploaded file could never become markup. */
export function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

/** Diagonal hatch used for "no reading" (texture channel, 45 degrees). */
export function hatch(color = "#98a2b3", bg = "#eef0f3"): any {
  const c = document.createElement("canvas");
  c.width = 8; c.height = 8;
  const g = c.getContext("2d")!;
  g.fillStyle = bg; g.fillRect(0, 0, 8, 8);
  g.strokeStyle = color; g.lineWidth = 1.5;
  g.beginPath(); g.moveTo(-1, 9); g.lineTo(9, -1); g.moveTo(-1, 1); g.lineTo(1, -1); g.moveTo(7, 9); g.lineTo(9, 7); g.stroke();
  return { image: c, repeat: "repeat" };
}

type Props = {
  option: any;
  height: number;
  ariaLabel: string;
  onClick?: (p: any) => void;
  testId?: string;
};

/** Minimal ECharts wrapper: init, resize with the container, dispose on unmount. */
export function EChart({ option, height, ariaLabel, onClick, testId }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    chart.current = echarts.init(ref.current, undefined, { renderer: "canvas" });
    const ro = new ResizeObserver(() => chart.current?.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); chart.current?.dispose(); chart.current = null; };
  }, []);
  useEffect(() => { chart.current?.setOption(option, true); }, [option]);
  useEffect(() => {
    const c = chart.current;
    if (!c || !onClick) return;
    c.on("click", onClick);
    return () => { c.off("click", onClick); };
  }, [onClick]);
  return <div ref={ref} style={{ height, width: "100%" }} role="img" aria-label={ariaLabel} data-testid={testId} />;
}
