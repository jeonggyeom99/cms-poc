from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.data_loader import dataset_summaries, load_datasets, load_fft_record


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

    def public_dashboard(dataset: dict) -> dict:
        fft = dataset.get("fft")
        if fft is None:
            return dataset
        return {
            **dataset,
            "fft": {key: value for key, value in fft.items() if not key.startswith("_")},
        }

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
        return public_dashboard(available_datasets[first_dataset_id])

    @application.get("/api/dashboard/{dataset_id}")
    async def dashboard_data(dataset_id: str, request: Request) -> dict:
        available_datasets = datasets_from(request)
        if dataset_id not in available_datasets:
            raise HTTPException(status_code=404, detail="설비 데이터를 찾을 수 없습니다.")
        return public_dashboard(available_datasets[dataset_id])

    @application.get("/api/dashboard/{dataset_id}/fft/{record_id}")
    async def fft_record(dataset_id: str, record_id: int, request: Request) -> dict:
        available_datasets = datasets_from(request)
        dataset = available_datasets.get(dataset_id)
        if dataset is None or dataset.get("fft") is None:
            raise HTTPException(status_code=404, detail="FFT 데이터를 찾을 수 없습니다.")
        try:
            return load_fft_record(dataset["fft"], record_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="FFT 레코드를 찾을 수 없습니다.") from error
        except (OSError, ValueError, SyntaxError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return application


app = create_app()
