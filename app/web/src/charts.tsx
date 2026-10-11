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

// Chart tokens (mirror styles.css; validated in docs/DECISIONS.md D-027).
export const C = {
  ink1: "#0b0b0b", ink2: "#52514e", ink3: "#6f6d68", grid: "#e1e0d9", axis: "#c3c2b7", surface: "#fcfcfb",
  outage: "#eb6834", low: "#2a78d6", high: "#1baf7a", nodata: "#98a2b3",
  // single-hue orange sequential ramp for outage minutes per day (OKLCH, lightness strictly decreasing)
  ramp: ["#ffede5", "#ffd2c0", "#ffb295", "#f78d66", "#e96a38", "#9b411d"],
};

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
