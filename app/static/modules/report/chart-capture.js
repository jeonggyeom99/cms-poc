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

async function captureReferenceFft(plotly, fft, selectedFaultType) {
  if (!fft) return plotly.toImage(renderedChart("fft-chart", "FFT"), imageOptions);
  const target = document.createElement("div");
  target.style.cssText = "position:fixed;left:-10000px;top:0;width:920px;height:720px;visibility:hidden";
  document.body.append(target);
  const figure = buildFftFigure(fft, selectedFaultType);
  try {
    await plotly.newPlot(target, figure.traces, figure.layout, { staticPlot: true, displayModeBar: false });
    return await plotly.toImage(target, imageOptions);
  } finally {
    plotly.purge(target);
    target.remove();
  }
}

export async function captureDashboardCharts({ fft = null, selectedFaultType = null } = {}) {
  const plotly = getPlotly();
  if (!plotly?.toImage) throw new Error("그래프 캡처 기능을 사용할 수 없습니다.");

  const trendChart = renderedChart("trend-chart", "Trend");
  const [trendImageDataUrl, fftImageDataUrl] = await Promise.all([
    plotly.toImage(trendChart, imageOptions),
    captureReferenceFft(plotly, fft, selectedFaultType),
  ]);
  return { trendImageDataUrl, fftImageDataUrl };
}
