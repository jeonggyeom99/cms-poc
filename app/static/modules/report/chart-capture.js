import { getPlotly } from "../core/plot.js?v=report-capture-v1";

const imageOptions = {
  format: "png",
  width: 1100,
  height: 500,
  scale: 1,
};

function renderedChart(chartId, label) {
  const chart = document.getElementById(chartId);
  if (!chart || chart.classList.contains("plot-empty") || !Array.isArray(chart.data) || !chart.data.length) {
    throw new Error(`${label} 그래프가 준비되지 않았습니다.`);
  }
  return chart;
}

export async function captureDashboardCharts() {
  const plotly = getPlotly();
  if (!plotly?.toImage) throw new Error("그래프 캡처 기능을 사용할 수 없습니다.");

  const trendChart = renderedChart("trend-chart", "Trend");
  const fftChart = renderedChart("fft-chart", "FFT");
  const [trendImageDataUrl, fftImageDataUrl] = await Promise.all([
    plotly.toImage(trendChart, imageOptions),
    plotly.toImage(fftChart, imageOptions),
  ]);
  return { trendImageDataUrl, fftImageDataUrl };
}