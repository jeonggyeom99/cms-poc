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