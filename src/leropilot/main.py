import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from leropilot.config import get_config
from leropilot.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan events."""
    config = get_config()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="LeRoPilot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/hello")
async def hello() -> dict[str, str]:
    """Return a simple hello message with version info."""
    return {"message": "Hello from LeRoPilot!", "version": "0.1.0"}


def get_static_dir() -> Path:
    """获取静态文件目录，兼容开发环境和 PyInstaller 打包后的环境"""
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后的环境
        base_path = Path(sys._MEIPASS)
    else:
        # 开发环境
        base_path = Path(__file__).parent

    return base_path / "leropilot" / "static"


def serve_static() -> None:
    static_dir = get_static_dir()
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    else:
        logger.warning("Static directory not found", path=str(static_dir))


def run_server() -> None:
    import threading
    import webbrowser

    config = get_config()
    serve_static()

    # 延迟打开浏览器，等待服务器启动
    def open_browser() -> None:
        import time

        time.sleep(1.5)
        webbrowser.open(f"http://127.0.0.1:{config.port}")

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=config.port)


if __name__ == "__main__":
    run_server()
