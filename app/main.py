import os
from collections.abc import AsyncIterator
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.agent_tools import build_dashboard_tool_executor
from app.ai_analysis import (
    AiAnalysisError,
    AiAnalysisGateway,
    AiAnalysisRequest,
    AiAnalysisResponse,
    AiAnalysisService,
    OpenAIAnalysisGateway,
    OpenAISettings,
    analysis_cache_ttl_seconds,
    load_project_environment,
)
from app.equipment_analysis import build_equipment_context, build_equipment_tool_executor
from app.chat import (
    DashboardChatGateway,
    DashboardChatRequest,
    DashboardChatResponse,
    DashboardChatService,
    OpenAIDashboardChatGateway,
    parse_tool_request,
)
from app.data_loader import (
    dataset_summaries,
    load_datasets,
    load_fft_record,
    load_history,
)
from app.reporting.ai import OpenAIReportGateway, ReportAiGateway, ReportAiService
from app.reporting.context import build_report_context
from app.reporting.contracts import DiagnosticPptRequest, ReportRequest, decode_png_data_url
from app.reporting.email_ai import EMAIL_DRAFT_REPORT_KIND, generate_email_draft
from app.reporting.email_draft import EmailDraftResponse, present_email_draft
from app.reporting.ppt_ai import PPT_REPORT_KIND, generate_ppt_diagnosis
from app.reporting.ppt_report import diagnostic_ppt_filename_stem
from app.reporting.ppt_pipeline import PptPipeline
from app.reporting.ppt_validation import OpenAIPptGateway, render_ppt
from app.services.analysis import (
    bearing_fft_tool,
    fft_tool,
    range_snapshot,
    select_fft_analysis_record,
    trend_analysis_result,
    trend_tool,
)
from app.services.history import select_dashboard_related_history


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR.parent / "data"
EQUIPMENT_STATUS_DEMO_DIR = BASE_DIR.parent / "equipment-status-demo"


def create_app(
    data_dir: Path = DATA_DIR,
    ai_gateway: AiAnalysisGateway | None = None,
    report_gateway: ReportAiGateway | None = None,
    chat_gateway: DashboardChatGateway | None = None,
    ppt_gateway: ReportAiGateway | None = None,
    ppt_renderer: Callable[[bytes], Awaitable[bytes]] = render_ppt,
    ai_cache_dir: Path | None = None,
) -> FastAPI:
    load_project_environment(BASE_DIR.parent)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.datasets = load_datasets(data_dir)
        try:
            application.state.history = load_history(data_dir)
        except (FileNotFoundError, OSError, ValueError):
            application.state.history = {"items": []}
        settings = OpenAISettings.from_environment()
        application.state.ai_analysis_service = AiAnalysisService(
            ai_gateway or OpenAIAnalysisGateway(settings),
            settings.model,
            cache_dir=(
                ai_cache_dir if ai_cache_dir is not None
                else data_dir.parent / ".cache" / "ai-analysis"
            ),
            ttl_seconds=analysis_cache_ttl_seconds(
                os.environ.get("AI_ANALYSIS_CACHE_TTL_SECONDS")
            ),
        )
        application.state.report_ai_service = ReportAiService(
            report_gateway or OpenAIReportGateway(settings), settings.model
        )
        application.state.ppt_pipeline = PptPipeline(
            ReportAiService(ppt_gateway or OpenAIPptGateway(settings), settings.model),
            ppt_renderer,
        )
        application.state.dashboard_chat_service = DashboardChatService(
            chat_gateway or OpenAIDashboardChatGateway(settings), settings.model
        )
        yield

    application = FastAPI(
        title="CMS AI PoC",
        description="CSV 기반 CMS 설비 Trend 및 FFT Dashboard API",
        version="0.2.0",
        lifespan=lifespan,
    )
    application.mount(
        "/static/equipment-status-demo",
        StaticFiles(directory=EQUIPMENT_STATUS_DEMO_DIR),
        name="equipment-status-demo",
    )
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(
            content=(STATIC_DIR / "favicon.ico").read_bytes(),
            media_type="image/x-icon",
        )

    def datasets_from(request: Request) -> dict:
        return request.app.state.datasets

    def history_from(request: Request) -> list[dict]:
        return request.app.state.history.get("items", [])

    def ai_service_from(request: Request) -> AiAnalysisService:
        return request.app.state.ai_analysis_service

    def report_service_from(request: Request) -> ReportAiService:
        return request.app.state.report_ai_service

    def chat_service_from(request: Request) -> DashboardChatService:
        return request.app.state.dashboard_chat_service

    def raise_ai_error(error: AiAnalysisError) -> None:
        status_code = {
            "missing_api_key": 503,
            "timeout": 504,
            "rate_limited": 429,
            "provider_unavailable": 503,
            "invalid_response": 502,
        }.get(error.code, 502)
        raise HTTPException(
            status_code=status_code,
            detail={"code": error.code, "message": error.message},
        ) from error

    def public_dashboard(dataset: dict) -> dict:
        fft = dataset.get("fft")
        public = {key: value for key, value in dataset.items() if not key.startswith("_")}
        if fft is not None:
            public["fft"] = {key: value for key, value in fft.items() if not key.startswith("_")}
        if public.get("trend") is not None:
            public["trend"] = {**public["trend"], "analysisResult": trend_analysis_result(dataset)}
        return public

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def equipment_status() -> str:
        # Keep the primary entry point on the CMS shell used by the dashboard.
        return await equipment_status2()

    @application.get("/main", response_class=HTMLResponse, include_in_schema=False)
    async def main_dashboard() -> str:
        return (STATIC_DIR / "main.html").read_text(encoding="utf-8")

    @application.get("/main_ct", response_class=HTMLResponse, include_in_schema=False)
    @application.get("/main_sv", response_class=HTMLResponse, include_in_schema=False)
    async def workspace_dashboard(request: Request) -> str:
        page = (STATIC_DIR / "main-workspace.html").read_text(encoding="utf-8").replace("ws1", "ws4")
        if request.url.path == "/main_ct":
            page = page.replace('<div class="sidebar-label">WORKSPACE</div><nav><a data-page="overview" href="#overview">Overview</a><a data-page="risk" href="#risk">Risk map</a><a data-page="worklist" href="#worklist">Worklist</a><a data-page="history" href="/history">Diagnosis history</a></nav><div class="sidebar-bottom"><span class="status-pulse"></span><span>Data refreshed<br><b id="sidebar-time">-</b></span></div>', '<div class="sidebar-label">CMS 운영</div><nav><a data-page="overview" href="/dashboard_ui6">▦ <span>대시보드</span></a><a data-page="risk" href="/equipment-status2">◈ <span>설비 알람 현황</span></a><a data-page="history" href="/history2">◌ <span>진단 이력</span></a><a data-page="control" href="/main_ct">⌁ <span>중앙 관제</span></a></nav><div class="sidebar-label manage-label">관리</div><nav><a href="/main_ct">⚙ <span>설정</span></a><a href="#">? <span>도움말</span></a></nav><div class="sidebar-bottom"><span class="status-pulse"></span><span>CMS 운영팀</span></div>', 1)
            page = page.replace('href="/" class="header-link"', 'href="/equipment-status2" class="header-link"').replace('href="/history"', 'href="/history2"').replace('/dashboard?dataset=', '/dashboard2?dataset=')
            page = page.replace('</head>', '<style>.workspace{grid-template-columns:76px minmax(0,1fr);background:#f7f8fb}.workspace-sidebar{width:76px;padding:28px 18px;background:#16263f;overflow:hidden;white-space:nowrap;transition:width .2s}.workspace:has(.workspace-sidebar:hover){grid-template-columns:244px minmax(0,1fr)}.workspace-sidebar:hover{width:244px}.workspace-logo{height:40px;gap:11px;margin:0 0 42px}.workspace-logo i{width:40px;height:40px;border-radius:11px;background:linear-gradient(145deg,#5ce3c0,#2f6fed);box-shadow:none;position:relative}.workspace-logo i:after{content:"P";position:absolute;inset:0;display:grid;place-items:center;color:#10223a;font-size:24px;font-style:normal;font-weight:900}.workspace-logo span,.workspace-sidebar .sidebar-label,.workspace-sidebar nav a:not(:first-child),.workspace-sidebar nav a:first-child{font-size:0}.workspace-sidebar:hover .workspace-logo span,.workspace-sidebar:hover .sidebar-label,.workspace-sidebar:hover nav a{font-size:12px}.workspace-sidebar nav a{width:52px;padding:12px 10px;margin:3px 0;color:#aebcd0;border-radius:10px}.workspace-sidebar:hover nav a{width:auto}.workspace-sidebar nav a:hover,.workspace-sidebar nav a:first-child{color:#fff;background:#254a77;box-shadow:inset 3px 0 #4ed9bb}.workspace-sidebar .sidebar-label{margin:0 0 12px;padding:0 10px;color:#70809a}.workspace-sidebar .sidebar-bottom{border-top-color:#ffffff14}.workspace-main{min-width:0;padding:30px 38px 50px;background:#f7f8fb}.workspace-header{margin-bottom:24px}.workspace-header h1{font-size:28px}</style></head>', 1)
        if request.url.path == "/main_ct":
            page = page.replace('</head>', '<style>.workspace-main{color:#172033}.workspace-header .eyebrow,.workspace-header #role-label{color:#2f6fed!important;font-size:11px!important;letter-spacing:.14em}.workspace-header h1{font-size:28px!important;letter-spacing:-.05em}.header-actions select,.header-link{border:1px solid #e8ebf1;background:#fff;border-radius:9px}.hero-grid{background:linear-gradient(120deg,#1e4d89,#2678bd);border-radius:16px;box-shadow:0 12px 30px rgba(29,43,70,.07)}.hero-rings .ring{background:rgba(255,255,255,.12)!important;color:#fff!important;backdrop-filter:blur(2px)}.hero-rings .ring small{color:#d9ebf7!important}.summary-line{border:1px solid #e8ebf1;border-radius:14px;box-shadow:0 12px 30px rgba(29,43,70,.07);background:#fff}.workspace-panel{border:1px solid #e8ebf1;border-radius:14px;box-shadow:0 12px 30px rgba(29,43,70,.07);background:#fff}.panel-title h3{font-size:15px}.risk-cell{border-left-width:4px;border-radius:8px}.work-row{border-bottom-color:#f0f2f6}.history-panel{grid-column:2;grid-row:2}.workspace-sidebar .workspace-logo span{display:none!important}.workspace-sidebar:hover .workspace-logo span{display:block!important}.workspace-sidebar nav a{font-size:20px!important}.workspace-sidebar nav a span{display:none!important;font-size:12px!important}.workspace-sidebar:hover nav a{font-size:12px!important}.workspace-sidebar:hover nav a span{display:inline!important}.workspace-sidebar nav a:first-child{color:#aebcd0;background:transparent;box-shadow:none}.workspace-sidebar nav:nth-of-type(1) a:nth-child(4){color:#fff;background:#254a77;box-shadow:inset 3px 0 #4ed9bb}.workspace-sidebar nav:nth-of-type(2) a{color:#aebcd0;background:transparent;box-shadow:none}</style></head>', 1)
        return page

    @application.get("/dashboard_ui3", response_class=HTMLResponse, include_in_schema=False)
    @application.get("/dashboard_ui4", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_ui_lab() -> str:
        return (STATIC_DIR / "design-lab.html").read_text(encoding="utf-8").replace("design1", "design15")

    @application.get("/dashboard_ui2", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_ui2() -> str:
        page = (STATIC_DIR / "kpi-dashboard-concept.html").read_text(encoding="utf-8")
        page = page.replace('<button class="btn">Last 30 days⌄</button><button class="btn primary">＋ Export report</button>', '<a class="btn" href="/dashboard_ui1">KPI 1</a><a class="btn primary" href="/dashboard_ui2">KPI 2</a>')
        return page.replace('</body>', '<script type="module" src="/static/modules/main/dashboard-chart-panels.js?v=20261004"></script></body>')

    @application.get("/dashboard_ui1", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_ui1() -> str:
        page = (STATIC_DIR / "dashboard-ui1-kpi.html").read_text(encoding="utf-8")
        page = page.replace('<a href="/dashboard_ui1">KPI</a>', '<a href="/dashboard_ui1">KPI 1</a><a href="/dashboard_ui2">KPI 2</a>')
        return page.replace('</body>', '<script type="module" src="/static/modules/main/dashboard-chart-panels.js?v=20261004"></script></body>')

    @application.get("/dashboard_ui1_canvas", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_ui1_canvas() -> str:
        return (STATIC_DIR / "dashboard-ui1-canvas.html").read_text(encoding="utf-8").replace("canvas1", "canvas6")

    @application.get("/dashboard_ui5", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_ui5() -> str:
        return (STATIC_DIR / "dashboard-ui5.html").read_text(encoding="utf-8").replace("ui5-1", "ui5-2")

    @application.get("/dashboard_ui6", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_ui6() -> str:
        page = (STATIC_DIR / "kpi-dashboard-concept.html").read_text(encoding="utf-8")
        page = page.replace("<body>", '<body class="dashboard-ui6">').replace("/static/modules/main/kpi-concept.js?v=20261003", "/static/modules/main/kpi-concept.js?v=20261007").replace("Pulseboard", "CMS Operations").replace("Pulse KPI Dashboard — Concept", "CMS Operations Dashboard").replace('href="/history"', 'href="/history2"').replace('<a href="#"><span>◌</span><span>Operations</span></a>', '<a href="/history2"><span>◌</span><span>진단 이력</span></a>')
        page = page.replace('</head>', '<style>.dashboard-ui6 .shell{grid-template-columns:76px 1fr;transition:grid-template-columns .2s}.dashboard-ui6 .side{width:76px;padding:28px 18px;overflow:hidden;white-space:nowrap;transition:width .2s;z-index:2}.dashboard-ui6 .shell:has(.side:hover){grid-template-columns:244px 1fr}.dashboard-ui6 .shell:has(.side:hover) .side{width:244px}.dashboard-ui6 .brand{margin:0 0 42px}.dashboard-ui6 .brand-mark{width:40px;height:40px;border-radius:11px;flex:none}.dashboard-ui6 .brand span,.dashboard-ui6 .nav-label,.dashboard-ui6 .nav a span:last-child,.dashboard-ui6 .side-bottom{display:none}.dashboard-ui6 .shell:has(.side:hover) .brand span,.dashboard-ui6 .shell:has(.side:hover) .nav-label,.dashboard-ui6 .shell:has(.side:hover) .nav a span:last-child,.dashboard-ui6 .shell:has(.side:hover) .side-bottom{display:block}.dashboard-ui6 .nav a{justify-content:flex-start;width:52px;padding:12px 10px;gap:12px}.dashboard-ui6 .shell:has(.side:hover) .nav a{width:auto}.dashboard-ui6 .nav-label{text-transform:none;padding:0 10px}.dashboard-ui6 .side-bottom{margin-top:auto;color:#aebcd0;font-size:11px;border-top:1px solid rgba(255,255,255,.08);padding-top:18px}.dashboard-ui6 .top p{display:none!important}.dashboard-ui6 .actions{display:none!important}</style></head>', 1)
        return page.replace('</body>', '<script type="module" src="/static/modules/main/dashboard-chart-panels.js?v=20261004"></script></body>')

    @application.get("/equipment-status2", response_class=HTMLResponse, include_in_schema=False)
    async def equipment_status2() -> str:
        page = (STATIC_DIR / "equipment-status2.html").read_text(encoding="utf-8")
        page = page.replace('</head>', '<link rel="stylesheet" href="/static/equipment-status.css?v=tree-status-v4"></head>', 1)
        page = page.replace('</head>', '<script src="/static/equipment-status-demo/equipment-status-excel-data.js"></script><script src="/static/equipment-status-demo/equipment-status-tree-data.js"></script></head>', 1)
        page = page.replace('<div class="nav-label">WORKSPACE</div><nav class="nav"><a href="/dashboard_ui6">▦<span>대시보드</span></a><a class="active" href="/equipment-status2">◈<span>설비 현황</span></a><a href="/history">◌<span>진단 이력</span></a></nav><div class="nav-label" style="margin-top:32px">MANAGE</div><nav class="nav"><a href="/main_ct">⚙<span>중앙 관제</span></a></nav>', '<div class="nav-label">CMS 운영</div><nav class="nav"><a href="/dashboard_ui6"><span>▦</span><span>대시보드</span></a><a class="active" href="/equipment-status2"><span>◈</span><span>설비 알람 현황</span></a><a href="/history2"><span>◌</span><span>진단 이력</span></a><a href="/main_ct"><span>⌁</span><span>중앙 관제</span></a></nav><div class="nav-label" style="margin-top:34px">관리</div><nav class="nav"><a href="/main_ct"><span>⚙</span><span>설정</span></a><a href="#"><span>?</span><span>도움말</span></a></nav>', 1)
        page = page.replace('</style>', '.shell{--es-normal:#2ba969;--es-attention:#e59b2f;--es-critical:#df4f61;--es-unknown:#9aa8b5;--es-border:#e2e8ee;--es-text:#172033;--es-accent:#2f6fed}body{overflow-x:hidden}.shell,main,.equipment-status2-panel,.equipment-status2-chart-grid{min-width:0;max-width:100%}main{padding-top:30px!important}.equipment-status2-panel,.equipment-status-search,.equipment-status-panel{background:#fff!important}.top{margin-bottom:4px!important}.top p{display:none!important}.top .action{display:none!important}.equipment-status-search{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:4px!important}.equipment-status-search label:has(#equipment-status-name){grid-column:1 / span 3;min-width:0}.equipment-status-search label:has(#equipment-status-name) input{display:block;width:100%!important;min-width:0}.equipment-status-search button{grid-column:4;align-self:end;width:100%;}.equipment-status2-panel{background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important;margin:0!important;overflow:hidden}.equipment-status2-panel>.equipment-status2-head{display:none}.equipment-status2-chart-grid{margin-bottom:0!important}.equipment-status2-chart-grid article{background:#fff!important;border:1px solid #e2e8ee!important;border-radius:14px!important;box-shadow:0 12px 30px rgba(29,43,70,.07)!important;min-width:0;overflow:hidden}.equipment-status-panel{border:1px solid #e2e8ee!important;border-radius:14px!important;padding:22px!important;margin-top:2px!important;box-shadow:0 12px 30px rgba(29,43,70,.07)!important}.equipment-status-page{background:#f7f8fb!important}.equipment-status-panel__body{grid-template-columns:300px minmax(0,1fr);gap:28px}.equipment-status-tree{height:620px;max-height:620px;padding:16px 14px;border:1px solid #e2e8ee;border-radius:12px;background:#fff}.equipment-status-tree summary,.equipment-status-tree button{font-size:13px;color:#68778b;padding:8px 6px;border-radius:6px}.equipment-status-tree__children{margin-left:10px;padding-left:13px;border-left:1px solid #dce5eb}.equipment-status-list{gap:0;min-width:0}.equipment-status-equipment{border-bottom:1px solid #e8edf1!important;background:transparent!important}.equipment-status-equipment__summary{padding:18px 16px;border-radius:10px;background:#f5fafb!important;display:flex;align-items:center;gap:12px;min-width:0}.equipment-status-equipment__summary:hover,.equipment-status-equipment[open]>summary{background:#edf7f7!important}.equipment-status-dot{width:13px;height:13px;box-shadow:0 0 0 5px rgba(43,169,105,.12)}.equipment-status-item__details{min-width:0}.equipment-status-item__details strong{font-size:16px;color:#26364a}.equipment-status-item__details small{display:block;margin-top:5px;color:#8090a1;white-space:normal}.equipment-status-label{margin-left:auto;font-weight:800}.equipment-status-sensors{margin:0 0 8px 43px;padding:6px 0 4px 18px;border-left:1px solid #dce5eb}.equipment-status-sensor{display:flex;align-items:center;gap:9px;padding:8px 0;color:#718196;text-decoration:none}.equipment-status-sensor__dot{width:7px;height:7px;border-radius:50%;background:var(--es-normal);flex:none}.equipment-status-sensor__state{margin-left:auto}@media(max-width:900px){.equipment-status-search{grid-template-columns:1fr 1fr}.equipment-status-search label:has(#equipment-status-name){grid-column:1 / -1}.equipment-status-search button{grid-column:1 / -1}.equipment-status-panel__body{grid-template-columns:1fr}.equipment-status-tree{height:auto;max-height:300px}}</style>', 1)
        page = page.replace('<div class="eyebrow">CMS EQUIPMENT CONTROL</div>', '<div class="eyebrow">2026년 10월 5일 월요일</div>', 1)
        page = page.replace('</style>', '.top{align-items:start}.top .eyebrow{color:#2f6fed!important;font-size:11px!important;letter-spacing:.14em!important}.top h1{font-size:28px!important;font-weight:800!important;margin-top:7px!important}</style>', 1)
        page = page.replace('</style>', 'html,body,main{background:#f7f8fb!important}</style>', 1)
        page = page.replace('</head>', '<style>html,body,.shell,main,.equipment-status-content{background:#f7f8fb!important}main{width:100%!important;max-width:1600px!important;margin:0 auto!important;padding-left:38px!important;padding-right:38px!important}.equipment-status-content{width:100%!important}</style></head>', 1)
        page = page.replace('<label>설비상태<select', '<label>설비유형<select id="equipment-status-type"><option value="all">전체</option></select></label><label>설비상태<select', 1)
        page = page.replace('<section class="equipment-status-panel">', '<p id="equipment-status-notice" hidden></p><section class="equipment-status-panel">', 1)
        page = page.replace('href="/history"', 'href="/history2"')
        return page

    @application.get("/main_ct1", response_class=HTMLResponse, include_in_schema=False)
    @application.get("/main_ct2", response_class=HTMLResponse, include_in_schema=False)
    @application.get("/main_ct3", response_class=HTMLResponse, include_in_schema=False)
    async def central_dashboard(request: Request) -> str:
        variant = request.url.path.rsplit("/", 1)[-1]
        page = (STATIC_DIR / "main-control.html").read_text(encoding="utf-8")
        return page.replace("CMS 중앙 관제", f"CMS {variant.upper()}").replace("전사 설비 리스크 관제", f"{variant.upper()} 중앙부서 대시보드").replace("ctsv1", "ctsv4").replace("ctjs1", "ctjs4")

    @application.get("/main_sv1", response_class=HTMLResponse, include_in_schema=False)
    @application.get("/main_sv2", response_class=HTMLResponse, include_in_schema=False)
    @application.get("/main_sv3", response_class=HTMLResponse, include_in_schema=False)
    async def site_dashboard(request: Request) -> str:
        variant = request.url.path.rsplit("/", 1)[-1]
        page = (STATIC_DIR / "main-control.html").read_text(encoding="utf-8")
        return page.replace("CMS 중앙 관제", f"CMS {variant.upper()}").replace("전사 설비 리스크 관제", f"{variant.upper()} 현장 대시보드").replace("ctsv1", "ctsv4").replace("ctjs1", "ctjs4")

    @application.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @application.get("/dashboard2", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard2() -> str:
        page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        shell = '<aside class="dashboard2-side"><div class="dashboard2-brand"><div class="dashboard2-mark">P</div><span>CMS Operations</span></div><div class="dashboard2-label">CMS 운영</div><nav><a href="/dashboard_ui6"><span>▦</span><b>대시보드</b></a><a href="/equipment-status2"><span>◈</span><b>설비 알람 현황</b></a><a href="/history2"><span>◌</span><b>진단 이력</b></a><a href="/main_ct"><span>⌁</span><b>중앙 관제</b></a></nav><div class="dashboard2-label manage">관리</div><nav><a href="/main_ct"><span>⚙</span><b>설정</b></a><a href="#"><span>?</span><b>도움말</b></a></nav><small class="dashboard2-footer">CMS 운영팀</small></aside>'
        page = page.replace("<body>", '<body class="dashboard2">', 1)
        page = page.replace("/static/app.js?v=equipment-ai-v3", "/static/app.js?v=dashboard2-scroll-fix", 1)
        page = page.replace('<a class="dashboard-home-link" href="/"', '<a class="dashboard-home-link" href="/equipment-status2"', 1)
        page = page.replace("<div class=\"app-shell\">", shell + '<div class="app-shell">', 1)
        page = page.replace("</head>", '<link rel="stylesheet" href="/static/dashboard2-shell.css?v=20261006"><script>history.scrollRestoration="manual";const dashboard2Top=()=>window.scrollTo({top:0,left:0,behavior:"auto"});dashboard2Top();window.addEventListener("DOMContentLoaded",dashboard2Top);window.addEventListener("load",dashboard2Top);window.addEventListener("pageshow",dashboard2Top);setTimeout(dashboard2Top,50);setTimeout(dashboard2Top,300);</script></head>', 1)
        return page.replace("</body>", '<script>const dashboard2TopAfterChange=()=>setTimeout(()=>window.scrollTo({top:0,left:0,behavior:"auto"}),0);document.addEventListener("change",event=>{if(event.target.id==="dataset-select")dashboard2TopAfterChange()});setTimeout(()=>window.scrollTo({top:0,left:0,behavior:"auto"}),1000);</script></body>', 1)

    @application.get("/history", response_class=HTMLResponse, include_in_schema=False)
    async def history() -> str:
        return (STATIC_DIR / "history.html").read_text(encoding="utf-8")

    @application.get("/history2", response_class=HTMLResponse, include_in_schema=False)
    async def history2() -> str:
        page = (STATIC_DIR / "history.html").read_text(encoding="utf-8")
        page = page.replace('<title>과거 이력 | 설비 진단</title>', '<title>진단 이력 | CMS Operations</title>').replace('<span class="history-kicker">설비 진단 이력</span>', '<span class="history-kicker">2026년 10월 5일 월요일</span>').replace('<p>설비별 진단 근거와 조치 결과를 조회합니다.</p>', '')
        sidebar = '<aside class="history2-side"><div class="history2-brand"><div class="history2-mark">P</div><span>CMS Operations</span></div><div class="history2-label">CMS 운영</div><nav><a href="/dashboard_ui6"><span>▦</span><b>대시보드</b></a><a href="/equipment-status2"><span>◈</span><b>설비 알람 현황</b></a><a class="active" href="/history2"><span>◌</span><b>진단 이력</b></a><a href="/main_ct"><span>⌁</span><b>중앙 관제</b></a></nav><div class="history2-label manage">관리</div><nav><a href="/main_ct"><span>⚙</span><b>설정</b></a><a href="#"><span>?</span><b>도움말</b></a></nav><small class="history2-footer">CMS 운영팀</small></aside>'
        css = '<style>.history2-side{position:fixed;inset:0 auto 0 0;width:76px;padding:28px 18px;background:#16263f;color:#c4cede;overflow:hidden;white-space:nowrap;z-index:5;transition:.2s}.history2-side:hover{width:244px}.history2-brand{display:flex;align-items:center;gap:11px;margin-bottom:42px;font-size:17px;font-weight:800}.history2-mark{width:40px;height:40px;flex:none;display:grid;place-items:center;border-radius:11px;background:linear-gradient(145deg,#5ce3c0,#2f6fed);color:#10223a;font-size:24px}.history2-brand span,.history2-label,.history2-side nav b,.history2-footer{display:none}.history2-side:hover .history2-brand span,.history2-side:hover .history2-label,.history2-side:hover nav b,.history2-side:hover .history2-footer{display:block}.history2-label{padding:0 10px;margin-bottom:12px;color:#70809a;font-size:10px}.history2-label.manage{margin-top:34px}.history2-side nav a{display:flex;align-items:center;gap:12px;width:52px;padding:12px 10px;margin:3px 0;border-radius:10px;color:#aebcd0;text-decoration:none}.history2-side nav b{font:inherit;font-weight:400}.history2-side nav a.active{color:#fff;background:#254a77;box-shadow:inset 3px 0 #4ed9bb}.history2-side:hover nav a{width:auto}.history2-footer{position:absolute;bottom:28px;color:#aebcd0;font-size:11px}.history-page{margin-left:76px;min-height:100vh;background:#f7f8fb}.history-topbar{display:none!important}.history-content{max-width:1600px;margin:auto;padding-top:30px!important}@media(max-width:800px){.history-page{margin-left:0}.history2-side{display:none}}</style>'
        css = css.replace('<style>', '<style>html,body,.history-page{background:#f7f8fb!important}.history-heading{align-items:start}.history-kicker{color:#2f6fed!important;font-size:11px!important;font-weight:800!important;letter-spacing:.14em!important}.history-heading h1{font-size:28px!important;font-weight:800!important;margin-top:7px!important}.history-heading p{display:none!important}.history2-side{font-size:12px!important}.history2-side nav b{font-size:12px!important}.history2-side .history2-label{font-size:9px!important}.history2-side .history2-brand{font-size:15px!important}.history-page{transition:margin-left .2s}.history2-side:hover ~ .history-page{margin-left:244px}.history-content{width:auto!important;max-width:1600px!important;margin:0!important;padding:30px 38px 48px!important}')
        page = page.replace('</head>', css + '</head>', 1).replace('<div class="history-page">', sidebar + '<div class="history-page">', 1)
        return page

    @application.get("/api/datasets")
    async def datasets(request: Request) -> dict:
        return {"items": dataset_summaries(datasets_from(request))}

    @application.get("/api/history")
    async def history_data() -> dict:
        try:
            return load_history(data_dir)
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404, detail="CMS 이력 CSV를 찾을 수 없습니다."
            ) from error
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.get("/api/dashboard/{dataset_id}/related-history")
    async def related_history(
        dataset_id: str, record_id: int, request: Request,
        selected_fault_type: str | None = None, until: date | None = None,
    ) -> dict:
        dataset = datasets_from(request).get(dataset_id)
        if dataset is None or dataset.get("fft") is None:
            raise HTTPException(status_code=404, detail="FFT 데이터를 찾을 수 없습니다.")
        try:
            filtered = snapshot(dataset, until)
            if filtered.get("fft") is None:
                raise KeyError(record_id)
            record = select_fft_analysis_record(filtered["fft"], record_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="FFT 레코드를 찾을 수 없습니다.") from error
        return select_dashboard_related_history(record, history_from(request), selected_fault_type, until)

    @application.get("/api/dashboard")
    async def default_dashboard_data(request: Request) -> dict:
        available_datasets = datasets_from(request)
        if not available_datasets:
            raise HTTPException(status_code=404, detail="사용 가능한 CSV 데이터가 없습니다.")
        first_dataset_id = dataset_summaries(available_datasets)[0]["id"]
        return public_dashboard(available_datasets[first_dataset_id])

    def snapshot(dataset: dict, until: date | None, start: date | None = None) -> dict:
        if until is None and start is None:
            return dataset
        result = range_snapshot(dataset, start, until)
        if result is None:
            raise HTTPException(status_code=404, detail="기준일 이전에 Trend와 FFT 데이터가 없습니다.")
        return result

    def report_context_for(
        dataset_id: str,
        report_request: ReportRequest,
        request: Request,
        report_kind: str,
    ) -> dict:
        dataset = datasets_from(request).get(dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail="설비 데이터를 찾을 수 없습니다.")
        try:
            filtered = snapshot(dataset, report_request.until)
            filtered_fft = filtered.get("fft")
            if filtered_fft is None:
                raise KeyError(report_request.record_id)
            selected_fft = load_fft_record(filtered_fft, report_request.record_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="FFT 레코드를 찾을 수 없습니다.") from error
        except (OSError, ValueError, SyntaxError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        return build_report_context(
            report_kind,
            dataset_id,
            filtered,
            {**filtered_fft, **selected_fft},
            history_from(request),
            report_request.selected_fault_type,
            report_request.until,
        )

    @application.get("/api/dashboard/{dataset_id}")
    async def dashboard_data(dataset_id: str, request: Request, until: date | None = None, start: date | None = None) -> dict:
        available_datasets = datasets_from(request)
        if dataset_id not in available_datasets:
            raise HTTPException(status_code=404, detail="설비 데이터를 찾을 수 없습니다.")
        return public_dashboard(snapshot(available_datasets[dataset_id], until, start))

    @application.get("/api/dashboard/{dataset_id}/fft/{record_id}")
    async def fft_record(dataset_id: str, record_id: int, request: Request, until: date | None = None, start: date | None = None) -> dict:
        available_datasets = datasets_from(request)
        dataset = available_datasets.get(dataset_id)
        if dataset is None or dataset.get("fft") is None:
            raise HTTPException(status_code=404, detail="FFT 데이터를 찾을 수 없습니다.")
        try:
            filtered = snapshot(dataset, until, start)
            if filtered.get("fft") is None:
                raise KeyError(record_id)
            return select_fft_analysis_record(filtered["fft"], record_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="FFT 레코드를 찾을 수 없습니다.") from error
        except (OSError, ValueError, SyntaxError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.post(
        "/api/dashboard/{dataset_id}/ai-analysis",
        response_model=AiAnalysisResponse,
    )
    async def ai_analysis(
        dataset_id: str,
        analysis_request: AiAnalysisRequest,
        request: Request,
    ) -> AiAnalysisResponse:
        dataset = datasets_from(request).get(dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail="설비 데이터를 찾을 수 없습니다.")
        try:
            filtered = snapshot(dataset, analysis_request.until)
            # Legacy record IDs are accepted but never determine equipment analysis scope.
            if analysis_request.record_id is not None:
                load_fft_record(filtered.get("fft") or {}, analysis_request.record_id)
            context = build_equipment_context(dataset_id, filtered, history_from(request), analysis_request.until)
            execute_analysis_tool = build_equipment_tool_executor(
                dataset_id, filtered, history_from(request), analysis_request.until, context
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="FFT 레코드를 찾을 수 없습니다.") from error
        except (OSError, ValueError, SyntaxError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        try:
            return await ai_service_from(request).analyze(
                context, analysis_request.force, execute_analysis_tool, dataset_id=dataset_id
            )
        except AiAnalysisError as error:
            raise_ai_error(error)

    @application.post(
        "/api/dashboard/{dataset_id}/chat",
        response_model=DashboardChatResponse,
    )
    async def dashboard_chat(
        dataset_id: str,
        chat_request: DashboardChatRequest,
        request: Request,
    ) -> DashboardChatResponse:
        available_datasets = datasets_from(request)
        dataset = available_datasets.get(dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail="설비 데이터를 찾을 수 없습니다.")
        chat_service = chat_service_from(request)
        if chat_service.uses_model_tools:
            reference_end = chat_request.until
            if reference_end is None:
                latest = dataset.get("equipment", {}).get("lastMeasuredAt")
                reference_end = date.fromisoformat(str(latest).split(" ")[0]) if latest else None
            executor = build_dashboard_tool_executor(
                available_datasets,
                dataset_id,
                chat_request.record_id,
                history_from(request),
                chat_request.selected_fault_type,
                reference_end,
            )
            try:
                return await chat_service.respond_with_tools(
                    {
                        "selectedEquipment": dataset.get("equipment", {}).get("id"),
                        "selectedRecordId": chat_request.record_id,
                        "until": chat_request.until.isoformat() if chat_request.until else None,
                    },
                    chat_request.history,
                    chat_request.message,
                    executor,
                )
            except AiAnalysisError as error:
                raise_ai_error(error)

        reference_end = chat_request.until
        if reference_end is None:
            latest = dataset.get("equipment", {}).get("lastMeasuredAt")
            reference_end = date.fromisoformat(str(latest).split(" ")[0]) if latest else None
        invocation = parse_tool_request(chat_request.message, chat_request.record_id, reference_end)
        requested_code = invocation.pop("equipment_code")
        if requested_code:
            matches = [
                (candidate_id, candidate) for candidate_id, candidate in available_datasets.items()
                if candidate.get("equipment", {}).get("id") == requested_code
            ]
            if matches:
                dataset_id, dataset = next(((candidate_id, candidate) for candidate_id, candidate in matches if candidate_id == dataset_id), matches[0])
            else:
                return await chat_service_from(request).respond_with_tool(
                    invocation["tool_name"], invocation, {"status": "unavailable", "reason": "dataset_not_found"},
                    chat_request.history, chat_request.message,
                )
        if invocation["end"] is None:
            invocation["end"] = chat_request.until
        tool_name = invocation["tool_name"]
        if tool_name == "trend":
            result = trend_tool(dataset, invocation["start"], invocation["end"])
        elif tool_name == "bearing_fft":
            result = bearing_fft_tool(dataset, invocation["record_id"], invocation["start"], invocation["end"], fallback_to_default=not invocation["record_explicit"])
        elif tool_name == "fft":
            result = fft_tool(dataset, invocation["record_id"], invocation["start"], invocation["end"], fallback_to_default=not invocation["record_explicit"])
        else:
            trend = trend_tool(dataset, invocation["start"], invocation["end"])
            fft = fft_tool(dataset, invocation["record_id"], invocation["start"], invocation["end"])
            result = {"status": "ready" if trend.get("status") == "ready" or fft.get("status") == "ready" else "unavailable", "trend": trend, "fft": fft}
        arguments = {key: (value.isoformat() if isinstance(value, date) else value) for key, value in invocation.items()}
        return await chat_service_from(request).respond_with_tool(
            tool_name, arguments, result, chat_request.history, chat_request.message
        )

    @application.post(
        "/api/dashboard/{dataset_id}/email-draft",
        response_model=EmailDraftResponse,
    )
    async def email_draft(
        dataset_id: str,
        report_request: ReportRequest,
        request: Request,
    ) -> EmailDraftResponse:
        context = report_context_for(
            dataset_id, report_request, request, EMAIL_DRAFT_REPORT_KIND
        )
        try:
            draft = await generate_email_draft(
                report_service_from(request), context, report_request.force
            )
        except AiAnalysisError as error:
            raise_ai_error(error)
        return present_email_draft(draft, report_service_from(request).model)

    @application.post("/api/dashboard/{dataset_id}/diagnostic-ppt")
    async def diagnostic_ppt(
        dataset_id: str,
        report_request: DiagnosticPptRequest,
        request: Request,
    ) -> Response:
        context = report_context_for(
            dataset_id, report_request, request, PPT_REPORT_KIND
        )
        try:
            diagnosis = await generate_ppt_diagnosis(
                report_service_from(request), context, report_request.force
            )
        except AiAnalysisError as error:
            raise_ai_error(error)

        try:
            result = await request.app.state.ppt_pipeline.build(
                context,
                diagnosis,
                decode_png_data_url(report_request.trend_image_data_url),
                decode_png_data_url(report_request.fft_image_data_url),
                force=report_request.force,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        filename = f"{diagnostic_ppt_filename_stem(context)}.pptx"
        return Response(
            content=result.presentation,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-PPT-Validation": result.validation.header(),
            },
        )

    return application


app = create_app()
