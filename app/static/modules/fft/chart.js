import { palette } from "../core/constants.js";
import { baseLayout } from "../core/plot.js?v=plot-zoom-bounds";

function selectedBearingFault(fft, selectedFaultType) {
  const diagnosis = fft.analysis?.diagnosis;
  return diagnosis?.faults?.find((fault) => fault.type === selectedFaultType)
    ?? diagnosis?.faults?.find((fault) => fault.type === diagnosis.defaultFaultType)
    ?? null;
}

export function buildFftFigure(fft, selectedFaultType = null) {
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
    text: fft.frequencyUnit === "Hz" ? "주파수 (Hz)" : "주파수 구간",
    standoff: 8,
    font: { ...layout.font },
  };
  layout.yaxis.title = {
    text: fft.amplitudeUnit ? `${measureModeLabel} (${fft.amplitudeUnit})` : measureModeLabel,
    standoff: 8,
    font: { ...layout.font },
  };
  const maximumAmplitude = Math.max(
    0,
    ...fft.amplitudes.filter((amplitude) => Number.isFinite(Number(amplitude))).map(Number),
  );
  layout.yaxis.range = [0, maximumAmplitude * 1.5];
  layout.yaxis.tick0 = 0;

  const bearingFault = selectedBearingFault(fft, selectedFaultType);
  if (fft.frequencyUnit === "Hz" && bearingFault) {
    const harmonics = bearingFault.harmonics.filter(
      (harmonic) => harmonic.targetFrequency > 0 && harmonic.targetFrequency <= Math.max(...fft.frequencies),
    );
    layout.shapes = harmonics.map((harmonic) => ({
      type: "line", x0: harmonic.targetFrequency, x1: harmonic.targetFrequency, xref: "x",
      y0: 0, y1: 1, yref: "paper",
      line: { color: "rgba(226, 83, 83, 0.52)", width: 1, dash: "dash" },
    }));
    layout.annotations = harmonics.map((harmonic) => ({
      x: harmonic.targetFrequency, xref: "x", y: 1, yref: "paper",
      text: `${bearingFault.type} ${harmonic.order}X`, showarrow: false, yshift: 8,
      font: { ...layout.font, color: palette.danger },
    }));
    const detected = harmonics.filter((harmonic) => harmonic.detected && harmonic.amplitude > 0);
    traces.push({
      x: detected.map((harmonic) => harmonic.detectedFrequency),
      y: detected.map((harmonic) => harmonic.amplitude),
      type: "scatter", mode: "markers+text", name: `${bearingFault.type} Peak`,
      text: detected.map((harmonic) => `${harmonic.order}X`), textposition: "top center",
      textfont: { ...layout.font, color: palette.danger },
      marker: { color: palette.danger, size: 9, line: { color: "#ffffff", width: 1.5 } },
      hovertemplate: `%{text}<br>%{x:.2f} Hz<br><b>%{y:.4f} ${amplitudeSuffix.trim()}</b><extra>${bearingFault.type} 결함 피크</extra>`,
    });
  } else if (fft.frequencyUnit === "Hz") {
    const diagnosis = fft.analysis?.diagnosis;
    const maximumFrequency = Math.max(...fft.frequencies);
    const harmonics = diagnosis?.harmonics?.filter(
      (harmonic) => harmonic.targetFrequency > 0 && harmonic.targetFrequency <= maximumFrequency,
    ) ?? [];
    const detected = harmonics.filter((harmonic) => harmonic.detected && harmonic.amplitude > 0);

    if (harmonics.length) {
      layout.margin = { l: 52, r: 15, t: 46, b: 43 };
      layout.shapes = harmonics.map((harmonic) => ({
        type: "line", x0: harmonic.targetFrequency, x1: harmonic.targetFrequency, xref: "x",
        y0: 0, y1: 1, yref: "paper",
        line: { color: "rgba(226, 83, 83, 0.45)", width: 1, dash: "dash" },
      }));
      layout.annotations = harmonics.map((harmonic) => ({
        x: harmonic.targetFrequency, xref: "x", y: 1, yref: "paper",
        text: `${harmonic.order}X`, showarrow: false, yshift: 8,
        font: { ...layout.font, color: palette.danger },
      }));
      traces.push({
        x: detected.map((harmonic) => harmonic.detectedFrequency),
        y: detected.map((harmonic) => harmonic.amplitude),
        type: "scatter", mode: "markers+text", name: "회전 주파수 피크",
        showlegend: false,
        text: detected.map((harmonic) => `${harmonic.order}X`), textposition: "top center",
        textfont: { ...layout.font, color: palette.danger },
        marker: { color: palette.danger, size: 9, line: { color: "#ffffff", width: 1.5 } },
        hovertemplate: `%{text}<br>%{x:.2f} Hz<br><b>%{y:.4f}${amplitudeSuffix}</b><extra>회전 주파수 피크</extra>`,
      });
    }
  }

  return { traces, layout };
}

export function buildFftDiagnosisFigure(fft, selectedFaultType = null) {
  const bearingFault = selectedBearingFault(fft, selectedFaultType);
  if (bearingFault) return buildFftFigure(fft, bearingFault.type);
  return buildFftFigure(fft);
}
