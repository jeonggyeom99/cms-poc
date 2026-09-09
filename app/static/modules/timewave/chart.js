import { palette } from "../core/constants.js";
import { baseLayout, renderPlot, setPlotEmpty } from "../core/plot.js?v=plot-zoom-bounds";
import { setExpandButtonEnabled } from "../controls/controls.js";

function finiteSamples(fft) {
  const samples = fft?.timeWaveSamples;
  if (!Array.isArray(samples) || !samples.length) return null;
  const values = samples.map(Number);
  return values.every(Number.isFinite) ? values : null;
}

function waveformRange(samples) {
  const minimum = Math.min(...samples);
  const maximum = Math.max(...samples);
  const span = maximum - minimum;
  const padding = span > 0 ? span * 0.1 : Math.max(Math.abs(maximum) * 0.1, 1);
  return [minimum - padding, maximum + padding];
}

export function buildTimeWaveFigure(fft) {
  const samples = finiteSamples(fft);
  if (!samples) return null;
  const measureModeLabel = fft.metadata?.measureMode?.label ?? "진폭";
  const amplitudeSuffix = fft.amplitudeUnit ? ` ${fft.amplitudeUnit}` : "";
  const layout = baseLayout();
  layout.margin = { l: 58, r: 15, t: 30, b: 43 };
  layout.showlegend = false;
  layout.xaxis.title = { text: "Sample Index", standoff: 8, font: { size: 10 } };
  layout.yaxis.title = {
    text: fft.amplitudeUnit ? `${measureModeLabel} (${fft.amplitudeUnit})` : measureModeLabel,
    standoff: 8,
    font: { size: 10 },
  };
  layout.yaxis.range = waveformRange(samples);
  layout.yaxis.zeroline = true;
  layout.yaxis.zerolinecolor = palette.grid;

  return {
    traces: [{
      x: samples.map((_, index) => index),
      y: samples,
      type: "scatter",
      mode: "lines",
      line: { color: palette.teal, width: 1.25 },
      hovertemplate: "Sample %{x}<br><b>%{y:.4f}" + amplitudeSuffix + "</b><extra></extra>",
    }],
    layout,
  };
}

export function renderTimeWaveChart(
  fft, emptyMessage = "선택한 FFT에 TimeWaveSampling 데이터가 없습니다.",
) {
  const figure = buildTimeWaveFigure(fft);
  if (!figure) {
    setExpandButtonEnabled("timewave", false);
    setPlotEmpty("timewave-chart", emptyMessage);
    return;
  }
  setExpandButtonEnabled("timewave", true);
  renderPlot("timewave-chart", figure);
}
