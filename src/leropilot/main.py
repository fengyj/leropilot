import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from leropilot import __version__
from leropilot.core.app_config import get_config
from leropilot.logger import get_logger
from leropilot.middleware import IdempotencyMiddleware
from leropilot.routers import app_config_api as config_router
from leropilot.routers import environments_api as environments_router
from leropilot.routers import repositories_api as repositories_router
from leropilot.routers import tools_api as tools_router
from leropilot.routers import web_sockets_api as terminal_router
from leropilot.utils import get_static_dir

# Configure basic logging early to capture config loading messages
# Note: This runs after imports, so initial config loading logs may not be visible
# For debugging config loading, set LEROPILOT_DEBUG=1 environment variable
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan events."""
    config = get_config()
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="LeRoPilot", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Idempotency middleware (after CORS)
app.add_middleware(IdempotencyMiddleware, ttl_hours=24)


@app.get("/api/hello", operation_id="hello_api_hello_get")
async def hello_get() -> dict[str, str]:
    """Return a simple hello message with version info."""
    return {"message": "Hello from LeRoPilot!", "version": "0.1.0"}


@app.head("/api/hello", operation_id="hello_api_hello_head")
async def hello_head() -> dict[str, str]:
    """Return a simple hello message with version info."""
    return {"message": "Hello from LeRoPilot!", "version": "0.1.0"}


# Register routers
app.include_router(config_router.router)
app.include_router(environments_router.router)
app.include_router(repositories_router.router)
app.include_router(terminal_router.router)
app.include_router(tools_router.router)


def serve_static() -> None:
    static_dir = get_static_dir()
    if static_dir.exists():
        # Mount static files
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        # Serve index.html for root
        @app.get("/")
        async def read_root() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        # Catch-all for SPA routing (serve index.html for any other path)
        @app.get("/{full_path:path}")
        async def catch_all(full_path: str) -> FileResponse:
            # Check if file exists in static dir (e.g. favicon.ico)
            file_path = static_dir / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            # Otherwise serve index.html for client-side routing
            return FileResponse(static_dir / "index.html")
    else:
        logger.warning("Static directory not found", path=str(static_dir))


def run_server(port: int | None = None, open_browser: bool = True) -> None:
    """Run the LeRoPilot server.

    Args:
        port: Optional port number to override config. If provided, will be saved to config.
        open_browser: Whether to automatically open the browser.
    """
    import threading
    import webbrowser

    from leropilot.core.app_config import get_config, save_config

    config = get_config()

    # If port is provided via CLI, update and save config
    if port is not None and port != config.server.port:
        logger.info("Port override detected, updating config", old_port=config.server.port, new_port=port)
        config.server.port = port
        save_config(config)
        logger.info("Config saved with new port", port=port)

    serve_static()

    # Delay browser opening to wait for server startup
    def open_browser_func() -> None:
        import shutil
        import subprocess
        import time

        time.sleep(1.5)
        url = f"http://127.0.0.1:{config.server.port}"

        if config.server.auto_open_browser:
            # Try to open in app mode (Chrome/Edge)
            browsers = ["google-chrome", "microsoft-edge", "chromium-browser", "chromium"]
            if sys.platform == "darwin":
                browsers = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
            elif sys.platform == "win32":
                browsers = ["chrome", "msedge"]

            opened = False
            for browser in browsers:
                if shutil.which(browser):
                    try:
                        logger.info(f"Opening browser in app mode: {browser}")
                        subprocess.Popen([browser, f"--app={url}"])
                        opened = True
                        break
                    except Exception as e:
                        logger.warning(f"Failed to open {browser}: {e}")

            if not opened:
                logger.info("Falling back to default browser")
                webbrowser.open(url)

    if open_browser:
        threading.Thread(target=open_browser_func, daemon=True).start()

    uvicorn.run(app, host=config.server.host, port=config.server.port)


def main() -> None:
    """Main entry point with CLI argument parsing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="LeRoPilot - LeRobot Environment Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  leropilot                    # Start with default/saved port
  leropilot --port 9000        # Start on port 9000 and save it
  leropilot --no-browser       # Start without opening browser (for Electron/WSL)
        """,
    )

    parser.add_argument(
        "--port",
        type=int,
        metavar="PORT",
        help="Port number to run the server on (will be saved to config)",
    )

    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open browser automatically",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"LeRoPilot {__version__}",
    )

    args = parser.parse_args()

    run_server(port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
