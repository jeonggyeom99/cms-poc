import { palette, plotConfig } from "./constants.js";

const plotRenderVersions = new WeakMap();

export function getPlotly() {
  return window.Plotly;
}

export function readChartTypography(root = globalThis.document?.documentElement) {
  const fallback = {
    family: 'Pretendard, "Noto Sans KR", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif',
    size: 12,
  };
  if (!root || typeof globalThis.getComputedStyle !== "function") return fallback;
  const style = globalThis.getComputedStyle(root);
  const family = style.getPropertyValue("--cms-font-family").trim();
  const size = Number.parseFloat(style.getPropertyValue("--cms-type-chart"));
  return {
    family: family || fallback.family,
    size: Number.isFinite(size) && size > 0 ? size : fallback.size,
  };
}

export function baseLayout() {
  const typography = readChartTypography();
  return {
    autosize: true,
    margin: { l: 48, r: 18, t: 28, b: 44 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    dragmode: "zoom",
    hoverlabel: {
      bgcolor: "#0d2f3c",
      bordercolor: "#0d2f3c",
      font: { ...typography, color: "#ffffff" },
    },
    font: { ...typography, color: palette.muted },
    xaxis: {
      gridcolor: palette.grid,
      linecolor: palette.grid,
      tickfont: { ...typography, color: palette.muted },
      zeroline: false,
    },
    yaxis: {
      gridcolor: palette.grid,
      linecolor: palette.grid,
      tickfont: { ...typography, color: palette.muted },
      zeroline: false,
      fixedrange: true,
    },
    showlegend: true,
    legend: {
      orientation: "h",
      x: 0,
      y: 1.13,
      font: { ...typography },
    },
  };
}

export function setPlotEmpty(plotId, message, isError = false) {
  const plot = document.getElementById(plotId);
  getPlotly().purge(plot);
  plot.className = `plot ${isError ? "loading-error" : "plot-empty"}`;
  plot.textContent = message;
}

function limitPlotAxesToInitialRange(plot) {
  const updates = {};

  Object.entries(plot._fullLayout ?? {}).forEach(([axisName, axis]) => {
    if (!/^[xy]axis\d*$/.test(axisName) || !Array.isArray(axis?.range)) return;

    const [minimum, maximum] = axis.range;
    if (minimum === null || minimum === undefined || maximum === null || maximum === undefined) return;

    updates[`${axisName}.minallowed`] = minimum;
    updates[`${axisName}.maxallowed`] = maximum;
  });

  if (Object.keys(updates).length) return getPlotly().relayout(plot, updates);
}

export function renderPlot(plotId, { traces, layout }) {
  const plot = document.getElementById(plotId);
  plot.className = plotId === "graph-modal-chart" ? "plot graph-modal-plot" : "plot";
  plot.textContent = "";
  const renderVersion = (plotRenderVersions.get(plot) ?? 0) + 1;
  plotRenderVersions.set(plot, renderVersion);
  void Promise.resolve(getPlotly().react(plot, traces, layout, plotConfig)).then(() => {
    if (plotRenderVersions.get(plot) === renderVersion) {
      return limitPlotAxesToInitialRange(plot);
    }
  });
}
