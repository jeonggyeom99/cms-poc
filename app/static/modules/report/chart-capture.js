import { getPlotly } from "../core/plot.js?v=report-capture-v1";
import { buildFftFigure } from "../fft/chart.js?v=korean-ui-v2";

const imageOptions = {
  format: "png",
  width: 920,
  height: 720,
  scale: 1,
};

function renderedChart(chartId, label) {
  const chart = document.getElementById(chartId);
  if (!chart || chart.classList.contains("plot-empty") || !Array.isArray(chart.data) || !chart.data.length) {
    throw new Error(`${label} 그래프가 준비되지 않았습니다.`);
  }
  return chart;
}

function presentationFigure(figure) {
  const layout = {
    ...figure.layout,
    font: { ...figure.layout.font, size: 28 },
    margin: { l: 100, r: 100, t: 75, b: 100 },
    legend: { ...figure.layout.legend, x: 0, y: 1.05, xanchor: "left", yanchor: "bottom", font: { size: 26 } },
    annotations: (figure.layout.annotations ?? []).map((item) => ({
      ...item, font: { ...item.font, size: 26 },
    })),
  };
  for (const [key, axis] of Object.entries(figure.layout)) {
    if (!/^[xy]axis\d*$/.test(key)) continue;
    const title = typeof axis.title === "string" ? { text: axis.title } : axis.title;
    layout[key] = {
      ...axis, automargin: true, tickfont: { ...axis.tickfont, size: 26 },
      title: { ...title, font: { ...title?.font, size: 28 } },
    };
  }
  return {
    traces: figure.traces.map((trace) => ({
      ...trace, textfont: { ...trace.textfont, size: 26 },
    })),
    layout,
  };
}

async function captureFigure(plotly, figure, options, presentation) {
  const target = document.createElement("div");
  target.style.cssText = `position:fixed;left:-10000px;top:0;width:${options.width}px;height:${options.height}px;visibility:hidden`;
  document.body.append(target);
  if (presentation) figure = presentationFigure(figure);
  try {
    await plotly.newPlot(target, figure.traces, figure.layout, { staticPlot: true, displayModeBar: false });
    return await plotly.toImage(target, options);
  } finally {
    plotly.purge(target);
    target.remove();
  }
}

async function captureReferenceFft(plotly, fft, selectedFaultType, options, presentation) {
  if (fft) return captureFigure(plotly, buildFftFigure(fft, selectedFaultType), options, presentation);
  const chart = renderedChart("fft-chart", "FFT");
  return presentation
    ? captureFigure(plotly, { traces: chart.data, layout: chart.layout }, options, true)
    : plotly.toImage(chart, options);
}

export async function captureDashboardCharts({ fft = null, selectedFaultType = null, presentation = false } = {}) {
  const plotly = getPlotly();
  if (!plotly?.toImage) throw new Error("그래프 캡처 기능을 사용할 수 없습니다.");

  const trendChart = renderedChart("trend-chart", "Trend");
  const options = presentation ? { ...imageOptions, width: 1120, height: 480 } : imageOptions;
  const [trendImageDataUrl, fftImageDataUrl] = await Promise.all([
    presentation
      ? captureFigure(plotly, { traces: trendChart.data, layout: trendChart.layout }, options, true)
      : plotly.toImage(trendChart, options),
    captureReferenceFft(plotly, fft, selectedFaultType, options, presentation),
  ]);
  return { trendImageDataUrl, fftImageDataUrl };
}
