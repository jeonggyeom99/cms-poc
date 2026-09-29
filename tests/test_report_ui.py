from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_report_actions_and_email_dialog_are_wired() -> None:
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    controller = (ROOT / "app/static/modules/dashboard/controller.js").read_text(
        encoding="utf-8"
    )
    email_draft = (ROOT / "app/static/modules/report/email-draft.js").read_text(
        encoding="utf-8"
    )

    for element_id in (
        "diagnostic-ppt-export",
        "report-action-status",
        "email-draft-open",
        "email-draft-dialog",
        "email-draft-preview",
        "email-draft-close",
        "email-draft-copy",
        "email-draft-status",
    ):
        assert f'id="{element_id}"' in html

    assert "bindPptExport(buildReportRequest)" in controller
    assert "bindEmailDraft(buildReportRequest)" in controller
    assert "resetReportActionsFor(fft)" in controller
    assert '"text/html"' in email_draft
    assert '"text/plain"' in email_draft
    assert "navigator.clipboard.write" in email_draft
    assert "captureDashboardCharts" in email_draft


def test_equipment_ai_diagnosis_is_pinned_until_manual_reanalysis() -> None:
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    controller = (ROOT / "app/static/modules/dashboard/controller.js").read_text(
        encoding="utf-8"
    )
    capture = (ROOT / "app/static/modules/report/chart-capture.js").read_text(
        encoding="utf-8"
    )

    equipment = html[
        html.index('<section class="equipment-overview"'):
        html.index('<section class="chart-grid"')
    ]
    assert 'class="equipment-ai-diagnosis"' in equipment
    assert 'id="ai-analysis-reference"' in equipment
    assert 'id="ai-analysis-details"' not in equipment
    assert 'class="card ai-analysis-card"' in html
    assert 'id="ai-analysis-details-title"' in html

    selection = controller[
        controller.index("async function selectFftRecord"):
        controller.index("export async function loadDashboard")
    ]
    bearing_click = controller[
        controller.index('document.getElementById("fft-analysis-details")'):
        controller.index('document.getElementById("fft-record-browser")')
    ]
    assert "resetAiAnalysis" not in selection
    assert "setAiDiagnosisReference" not in selection
    assert "resetAiAnalysis" not in bearing_click
    assert "setAiDiagnosisReference" not in bearing_click
    assert "bindAiAnalysis((force) => runAiAnalysis(force, true))" in controller
    assert "setAiDiagnosisReference(getSelectedFftRecord(), getSelectedBearingFaultType())" in controller
    assert "fftRecord: reference.record" in controller
    assert "captureReferenceFft" in capture


def test_ai_analysis_hides_rule_based_findings_until_ai_result_arrives() -> None:
    analysis = (ROOT / "app/static/modules/analysis/ai.js").read_text(
        encoding="utf-8"
    )

    reset = analysis[
        analysis.index("export function resetAiAnalysis"):
        analysis.index("export function setAiAnalysisLoading")
    ]
    loading = analysis[
        analysis.index("export function setAiAnalysisLoading"):
        analysis.index("export function renderAiAnalysis")
    ]

    assert '"AI 분석 결과를 기다리고 있습니다."' in reset
    assert '"AI 분석 대기"' in reset
    assert "renderBaseline(details, baseline)" not in reset
    assert '"AI 분석 결과를 분석하고 있습니다. 잠시만 기다려 주세요."' in loading
    assert '"AI 분석 중"' in loading
    assert "renderBaseline(details, baseline" not in loading


def test_ai_analysis_shows_generated_diagnosis_in_overview() -> None:
    analysis = (ROOT / "app/static/modules/analysis/ai.js").read_text(
        encoding="utf-8"
    )
    ready = analysis[
        analysis.index("export function renderAiAnalysis("):
        analysis.index("export function renderAiAnalysisError(")
    ]
    error = analysis[
        analysis.index("export function renderAiAnalysisError("):
        analysis.index("export function bindAiAnalysis(")
    ]

    assert "description.textContent = analysis.headline;" in ready
    assert "conciseSummary" not in analysis
    assert 'result.textContent = "AI 진단 실패";' in error
    assert 'description.textContent = "AI 진단을 불러오지 못했습니다. 다시 시도해 주세요.";' in error


def test_fft_charts_use_one_and_a_half_times_the_maximum_amplitude_for_y_axis() -> None:
    chart = (ROOT / "app/static/modules/fft/chart.js").read_text(encoding="utf-8")

    assert "layout.yaxis.range = [0, maximumAmplitude * 1.5];" in chart
    assert "buildFftDiagnosisFigure" in chart


def test_main_fft_chart_marks_velocity_harmonics() -> None:
    chart = (ROOT / "app/static/modules/fft/chart.js").read_text(encoding="utf-8")

    assert 'else if (fft.frequencyUnit === "Hz")' in chart
    assert "const harmonics = diagnosis?.harmonics?.filter(" in chart
    assert 'text: `${harmonic.order}X`' in chart


def test_time_wave_graph_is_wired_with_sample_index_axis_and_expansion() -> None:
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    controller = (ROOT / "app/static/modules/dashboard/controller.js").read_text(
        encoding="utf-8"
    )
    chart = (ROOT / "app/static/modules/timewave/chart.js").read_text(encoding="utf-8")

    assert 'id="timewave-chart"' in html
    assert 'data-expand-graph="timewave"' in html
    assert 'text: fs ? "시간 (s)" : "표본 번호"' in chart
    assert "renderTimeWaveChart(selectedFft);" in controller
    assert 'getExpandedGraph() === "timewave"' in controller


def test_fft_history_excludes_acceleration_all_and_renames_acceleration_env() -> None:
    records = (ROOT / "app/static/modules/fft/records.js").read_text(encoding="utf-8")
    formatting = (ROOT / "app/static/modules/core/format.js").read_text(encoding="utf-8")

    assert 'record.measureMode?.code !== "0"' in records
    assert '"가속도ENV": "가속도"' in formatting


def test_trend_and_fft_cards_have_equal_widths() -> None:
    styles = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")

    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in styles


def test_chart_tips_are_hidden_without_disabling_chart_navigation() -> None:
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    constants = (ROOT / "app/static/modules/core/constants.js").read_text(
        encoding="utf-8"
    )

    assert "드래그하여 확대 · 더블 클릭하여 초기화" not in html
    assert "showTips: false" in constants
    assert "scrollZoom: true" in constants
    assert 'doubleClick: "reset"' in constants
