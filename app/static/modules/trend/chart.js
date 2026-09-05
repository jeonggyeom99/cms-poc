import { palette, trendMetricStyles } from "../core/constants.js";
import { getDashboardData, getSelectedTrendMetrics } from "../core/state.js?v=acceleration-bearing-fft";
import { baseLayout, renderPlot, setPlotEmpty } from "../core/plot.js?v=plot-zoom-bounds";
import { setExpandButtonEnabled, setPeriodTabsEnabled } from "../controls/controls.js";

export function filteredTrendPoints(period, data = getDashboardData()) {
  const points = data.trend.points;
  if (period === "all") return points;

  const latest = new Date(points.at(-1).timestamp.replace(" ", "T"));
  const start = new Date(latest);
  start.setDate(start.getDate() - Number(period));
  return points.filter((point) => new Date(point.timestamp.replace(" ", "T")) >= start);
}

export function trendAxisTitle(unit) {
  if (unit === "g") return "가속도 (g)";
  return "속도 (mm/s)";
}

export function buildExpandedTrendFigure(
  period = "90",
  data = getDashboardData(),
  selectedMetrics = getSelectedTrendMetrics(),
) {
  const points = filteredTrendPoints(period, data);
  const metrics = data.trend.metrics.filter(
    (metric) => metric.available && selectedMetrics.has(metric.key),
  );
  const units = [...new Set(metrics.map((metric) => metric.unit))];
  const usesDualAxis = units.length > 1;
  const traces = [];

  metrics.forEach((metric) => {
    const style = trendMetricStyles[metric.key] ?? { color: palette.teal, digits: 2 };
    const axis = usesDualAxis && metric.unit !== "g" ? "y2" : "y";
    const x = points.map((point) => point.timestamp);
    const y = points.map((point) => point[metric.pointKey]);
    const latestPoint = [...points].reverse().find((point) => point[metric.pointKey] !== null);

    traces.push({
      x,
      y,
      yaxis: axis,
      type: "scatter",
      mode: "lines",
      name: metric.label,
      legendgroup: metric.key,
      line: { color: style.color, width: 2 },
      hovertemplate: `%{x}<br><b>%{y:.${style.digits}f} ${metric.unit}</b><extra>${metric.label}</extra>`,
    });

    [
      ["주의", metric.warningThreshold, palette.caution, "dash"],
      ["위험", metric.dangerThreshold, palette.danger, "dot"],
    ].forEach(([label, value, color, dash]) => {
      if (value === null || !Number.isFinite(Number(value))) return;
      traces.push({
        x: [x[0], x.at(-1)],
        y: [value, value],
        yaxis: axis,
        type: "scatter",
        mode: "lines",
        name: `${metric.label} ${label}`,
        legendgroup: metric.key,
        showlegend: false,
        line: { color, width: 1.2, dash },
        opacity: 0.8,
        hovertemplate: `${metric.label} ${label} <b>%{y:.${style.digits}f} ${metric.unit}</b><extra></extra>`,
      });
    });

    if (latestPoint) {
      traces.push({
        x: [latestPoint.timestamp],
        y: [latestPoint[metric.pointKey]],
        yaxis: axis,
        type: "scatter",
        mode: "markers",
        name: `${metric.label} 최신값`,
        legendgroup: metric.key,
        showlegend: false,
        marker: { color: style.color, line: { color: "#ffffff", width: 2 }, size: 9 },
        hovertemplate: `최신 <b>%{y:.${style.digits}f} ${metric.unit}</b><extra>${metric.label}</extra>`,
      });
    }
  });

  const layout = baseLayout();
  layout.margin = { l: 62, r: usesDualAxis ? 70 : 24, t: 28, b: 62 };
  layout.legend = {
    ...layout.legend,
    x: 0,
    y: -0.18,
    xanchor: "left",
    yanchor: "top",
  };
  layout.yaxis.title = {
    text: trendAxisTitle(usesDualAxis ? "g" : units[0]),
    standoff: 8,
    font: { size: 10 },
  };
  layout.yaxis.rangemode = "tozero";
  layout.xaxis.hoverformat = "%Y-%m-%d %H:%M";
  if (usesDualAxis) {
    const secondaryUnit = units.find((unit) => unit !== "g");
    layout.yaxis2 = {
      title: { text: trendAxisTitle(secondaryUnit), standoff: 8, font: { size: 10 } },
      overlaying: "y",
      side: "right",
      rangemode: "tozero",
      showgrid: false,
      linecolor: palette.grid,
      tickfont: { color: palette.muted, size: 10 },
      zeroline: false,
      fixedrange: true,
    };
  }

  return { traces, layout };
}

export function buildTrendFigure(period = "90", data = getDashboardData()) {
  const points = filteredTrendPoints(period, data);
  const x = points.map((point) => point.timestamp);
  const y = points.map((point) => point.value);
  const latestPoint = points.at(-1);
  const traces = [
    {
      x,
      y,
      type: "scatter",
      mode: "lines",
      name: "진동 속도 평균",
      line: { color: palette.teal, width: 2 },
      fill: "tozeroy",
      fillcolor: palette.tealFill,
      hovertemplate: "%{x}<br><b>%{y:.3f} mm/s</b><extra></extra>",
    },
  ];

  const thresholdDefinitions = [
    {
      value: data.current.warningThreshold,
      name: "현재 주의 Level",
      color: palette.caution,
      dash: "dash",
    },
    {
      value: data.current.dangerThreshold,
      name: "현재 위험 Level",
      color: palette.danger,
      dash: "dot",
    },
  ];
  thresholdDefinitions.forEach((threshold) => {
    if (threshold.value === null || !Number.isFinite(Number(threshold.value))) return;
    traces.push({
      x: [x[0], x.at(-1)],
      y: [threshold.value, threshold.value],
      type: "scatter",
      mode: "lines",
      name: threshold.name,
      line: { color: threshold.color, width: 1.5, dash: threshold.dash },
      hovertemplate: `${threshold.name} <b>%{y:.2f} mm/s</b><extra></extra>`,
    });
  });
  traces.push({
    x: [latestPoint.timestamp],
    y: [latestPoint.value],
    type: "scatter",
    mode: "markers",
    name: "최신 측정",
    marker: { color: palette.caution, line: { color: "#ffffff", width: 2 }, size: 10 },
    hovertemplate: "최신 <b>%{y:.3f} mm/s</b><extra></extra>",
  });

  const layout = baseLayout();
  layout.margin = { ...layout.margin, t: 28, b: 58 };
  layout.legend = {
    ...layout.legend,
    x: 0,
    y: -0.18,
    xanchor: "left",
    yanchor: "top",
  };
  layout.yaxis.title = { text: "속도 (mm/s)", standoff: 8, font: { size: 10 } };
  layout.yaxis.rangemode = "tozero";
  layout.xaxis.hoverformat = "%Y-%m-%d %H:%M";

  return { traces, layout };
}

export function renderTrend(period = "90", data = getDashboardData()) {
  if (!data?.trend) {
    setPeriodTabsEnabled(false);
    setExpandButtonEnabled("trend", false);
    setPlotEmpty("trend-chart", "이 설비에는 Trend CSV가 없습니다.");
    return;
  }

  setPeriodTabsEnabled(true);
  setExpandButtonEnabled("trend", true);
  renderPlot("trend-chart", buildTrendFigure(period, data));
}
