from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.ai_analysis import (
    AiAnalysisError,
    AiAnalysisGateway,
    AiAnalysisRequest,
    AiAnalysisResponse,
    AiAnalysisService,
    OpenAIAnalysisGateway,
    OpenAISettings,
    build_ai_context,
    load_project_environment,
)
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
from app.reporting.ppt_report import build_diagnostic_ppt, diagnostic_ppt_filename_stem
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
            ai_gateway or OpenAIAnalysisGateway(settings), settings.model
        )
        application.state.report_ai_service = ReportAiService(
            report_gateway or OpenAIReportGateway(settings), settings.model
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
        return (STATIC_DIR / "equipment-status.html").read_text(encoding="utf-8")

    @application.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @application.get("/history", response_class=HTMLResponse, include_in_schema=False)
    async def history() -> str:
        return (STATIC_DIR / "history.html").read_text(encoding="utf-8")

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
            filtered_fft = filtered.get("fft")
            if filtered_fft is None:
                raise KeyError(analysis_request.record_id)
            selected_fft = load_fft_record(filtered_fft, analysis_request.record_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="FFT 레코드를 찾을 수 없습니다.") from error
        except (OSError, ValueError, SyntaxError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        fft_for_analysis = {**filtered_fft, **selected_fft}
        context = build_ai_context(
            dataset_id,
            filtered,
            fft_for_analysis,
            history_from(request),
            analysis_request.selected_fault_type,
            analysis_request.until,
        )
        try:
            return await ai_service_from(request).analyze(context, analysis_request.force)
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
            presentation = build_diagnostic_ppt(
                context,
                diagnosis,
                decode_png_data_url(report_request.trend_image_data_url),
                decode_png_data_url(report_request.fft_image_data_url),
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        filename = f"{diagnostic_ppt_filename_stem(context)}.pptx"
        return Response(
            content=presentation,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return application


app = create_app()
