from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.data_loader import dataset_summaries, load_datasets


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR.parent / "data"


def create_app(data_dir: Path = DATA_DIR) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.datasets = load_datasets(data_dir)
        yield

    application = FastAPI(
        title="CMS AI PoC",
        description="CSV 기반 CMS 설비 Trend 및 FFT Dashboard API",
        version="0.2.0",
        lifespan=lifespan,
    )
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    def datasets_from(request: Request) -> dict:
        return request.app.state.datasets

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @application.get("/api/datasets")
    async def datasets(request: Request) -> dict:
        return {"items": dataset_summaries(datasets_from(request))}

    @application.get("/api/dashboard")
    async def default_dashboard_data(request: Request) -> dict:
        available_datasets = datasets_from(request)
        if not available_datasets:
            raise HTTPException(status_code=404, detail="사용 가능한 CSV 데이터가 없습니다.")
        first_dataset_id = dataset_summaries(available_datasets)[0]["id"]
        return available_datasets[first_dataset_id]

    @application.get("/api/dashboard/{dataset_id}")
    async def dashboard_data(dataset_id: str, request: Request) -> dict:
        available_datasets = datasets_from(request)
        if dataset_id not in available_datasets:
            raise HTTPException(status_code=404, detail="설비 데이터를 찾을 수 없습니다.")
        return available_datasets[dataset_id]

    return application


app = create_app()
