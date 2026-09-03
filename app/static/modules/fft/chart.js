import { palette } from "../core/constants.js";
import { baseLayout, renderPlot, setPlotEmpty } from "../core/plot.js?v=plot-zoom-bounds";
import { setExpandButtonEnabled } from "../controls/controls.js";

export function buildFftFigure(fft) {
  const measureModeLabel = fft.metadata?.measureMode?.label ?? "진폭";
  const frequencySuffix = fft.frequencyUnit === "Hz" ? " Hz" : " bin";
  const amplitudeSuffix = fft.amplitudeUnit ? ` ${fft.amplitudeUnit}` : "";
  const traces = [
    {
      x: fft.frequencies,
      y: fft.amplitudes,
      type: "scatter",
      mode: "lines",
      name: measureModeLabel,
      line: { color: palette.teal, width: 1.6 },
      fill: "tozeroy",
      fillcolor: palette.tealFill,
      hovertemplate: `%{x:.2f}${frequencySuffix}<br><b>%{y:.4f}${amplitudeSuffix}</b><extra></extra>`,
    },
  ];

  const layout = baseLayout();
  layout.margin = { l: 52, r: 15, t: 36, b: 43 };
  layout.showlegend = false;
  layout.xaxis.title = {
    text: fft.frequencyUnit === "Hz" ? "Frequency (Hz)" : "FFT bin",
    standoff: 8,
    font: { size: 10 },
  };
  layout.yaxis.title = {
    text: fft.amplitudeUnit ? `${measureModeLabel} (${fft.amplitudeUnit})` : measureModeLabel,
    standoff: 8,
    font: { size: 10 },
  };
  const maximumAmplitude = Math.max(
    0,
    ...fft.amplitudes.filter((amplitude) => Number.isFinite(Number(amplitude))).map(Number),
  );
  layout.yaxis.range = [0, maximumAmplitude > 5 ? 10 : 5];
  layout.yaxis.tick0 = 0;
  layout.yaxis.dtick = maximumAmplitude > 5 ? 1 : 0.5;

  return { traces, layout };
}

export function buildFftDiagnosisFigure(fft) {
  const { traces, layout } = buildFftFigure(fft);
  const diagnosis = fft.analysis?.diagnosis;
  const harmonicPeaks = diagnosis?.harmonics?.filter(
    (harmonic) => harmonic.detected && harmonic.amplitude > 0,
  ) ?? [];
  const maximumFrequency = Math.max(...fft.frequencies);
  const harmonicGuides = diagnosis?.harmonics?.filter(
    (harmonic) => harmonic.targetFrequency > 0 && harmonic.targetFrequency <= maximumFrequency,
  ) ?? [];

  traces.push({
    x: harmonicPeaks.map((harmonic) => harmonic.detectedFrequency),
    y: harmonicPeaks.map((harmonic) => harmonic.amplitude),
    type: "scatter",
    mode: "markers+text",
    name: "회전 주파수 피크",
    showlegend: false,
    text: harmonicPeaks.map((harmonic) => `${harmonic.order}X`),
    textposition: "top center",
    textfont: { color: palette.danger, size: 11, family: "Arial, sans-serif" },
    marker: {
      color: palette.danger,
      size: 9,
      line: { color: "#ffffff", width: 1.5 },
    },
    hovertemplate: "%{text}<br>%{x:.2f} Hz<br><b>%{y:.4f} mm/s</b><extra>회전 주파수 피크</extra>",
  });
  layout.margin = { l: 52, r: 15, t: 46, b: 43 };
  layout.shapes = harmonicGuides.map((harmonic) => ({
    type: "line",
    x0: harmonic.targetFrequency,
    x1: harmonic.targetFrequency,
    xref: "x",
    y0: 0,
    y1: 1,
    yref: "paper",
    line: { color: "rgba(226, 83, 83, 0.45)", width: 1, dash: "dash" },
  }));
  layout.annotations = harmonicGuides.map((harmonic) => ({
    x: harmonic.targetFrequency,
    xref: "x",
    y: 1,
    yref: "paper",
    text: `${harmonic.order}X`,
    showarrow: false,
    yshift: 8,
    font: { color: palette.danger, size: 10 },
  }));

  return { traces, layout };
}

export function renderFftChart(fft, emptyMessage = "이 설비에는 FFT CSV가 없습니다.") {
  if (!fft) {
    setExpandButtonEnabled("fft", false);
    setPlotEmpty("fft-chart", emptyMessage);
    return;
  }

  setExpandButtonEnabled("fft", true);
  renderPlot("fft-chart", buildFftFigure(fft));
}
