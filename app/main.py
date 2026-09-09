from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, time
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
from app.envelope import analyze_envelope
from app.data_loader import (
    dataset_summaries,
    dataset_until,
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


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR.parent / "data"
EQUIPMENT_STATUS_DEMO_DIR = BASE_DIR.parent / "equipment-status-demo"


def create_app(
    data_dir: Path = DATA_DIR,
    ai_gateway: AiAnalysisGateway | None = None,
    report_gateway: ReportAiGateway | None = None,
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

    @application.get("/api/dashboard")
    async def default_dashboard_data(request: Request) -> dict:
        available_datasets = datasets_from(request)
        if not available_datasets:
            raise HTTPException(status_code=404, detail="사용 가능한 CSV 데이터가 없습니다.")
        first_dataset_id = dataset_summaries(available_datasets)[0]["id"]
        return public_dashboard(available_datasets[first_dataset_id])

    def snapshot(dataset: dict, until: date | None) -> dict:
        if until is None:
            return dataset
        result = dataset_until(dataset, datetime.combine(until, time.max))
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
    async def dashboard_data(dataset_id: str, request: Request, until: date | None = None) -> dict:
        available_datasets = datasets_from(request)
        if dataset_id not in available_datasets:
            raise HTTPException(status_code=404, detail="설비 데이터를 찾을 수 없습니다.")
        return public_dashboard(snapshot(available_datasets[dataset_id], until))

    @application.get("/api/dashboard/{dataset_id}/fft/{record_id}")
    async def fft_record(dataset_id: str, record_id: int, request: Request, until: date | None = None) -> dict:
        available_datasets = datasets_from(request)
        dataset = available_datasets.get(dataset_id)
        if dataset is None or dataset.get("fft") is None:
            raise HTTPException(status_code=404, detail="FFT 데이터를 찾을 수 없습니다.")
        try:
            filtered = snapshot(dataset, until)
            if filtered.get("fft") is None:
                raise KeyError(record_id)
            return load_fft_record(filtered["fft"], record_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="FFT 레코드를 찾을 수 없습니다.") from error
        except (OSError, ValueError, SyntaxError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.get("/api/dashboard/{dataset_id}/fft/{record_id}/envelope")
    async def envelope_analysis(
        dataset_id: str, record_id: int, request: Request,
        low_hz: float = 1000, high_hz: float = 2200, until: date | None = None,
    ) -> dict:
        record = await fft_record(dataset_id, record_id, request, until)
        try:
            return analyze_envelope(record, low_hz, high_hz)
        except ValueError as error:
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
