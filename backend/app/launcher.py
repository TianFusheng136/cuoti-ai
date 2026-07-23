import ctypes
import json
import os
import socket
import sys
import threading
import urllib.request
import webbrowser
from datetime import UTC, datetime
from pathlib import Path

import uvicorn

from backend.app.core.config import PROJECT_ROOT
from backend.app.main import create_app


def installation_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def bundled_frontend() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    return bundle_root / "frontend" / "dist"


def choose_port() -> int:
    port = 3002
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        try:
            candidate.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError("端口 3002 已被占用，请先关闭占用该端口的程序。") from exc
    return port


def running_url(state_file: Path) -> str | None:
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        url = str(state["url"])
        with urllib.request.urlopen(f"{url}/api/v1/health", timeout=2) as response:  # noqa: S310
            body = json.loads(response.read())
        return url if body.get("status") == "ok" else None
    except (OSError, ValueError, KeyError):
        state_file.unlink(missing_ok=True)
        return None


def main() -> None:
    root = installation_root()
    configured_data = os.environ.get("AI_REVIEW_DATA_DIR")
    data_dir = Path(configured_data).resolve() if configured_data else root / "data"
    runtime = data_dir / "runtime"
    logs = data_dir / "logs"
    runtime.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    state_file = runtime / "app.json"

    existing = running_url(state_file)
    if existing:
        if os.environ.get("AI_REVIEW_NO_BROWSER") != "1":
            webbrowser.open(existing)
        return

    port = choose_port()
    url = f"http://127.0.0.1:{port}"
    state = {
        "pid": os.getpid(),
        "url": url,
        "port": port,
        "processStartTimeUtc": datetime.now(UTC).isoformat(),
    }
    state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    app = create_app(
        data_dir=data_dir,
        frontend_dist=bundled_frontend(),
        expose_api_docs=not getattr(sys, "frozen", False),
    )
    if os.environ.get("AI_REVIEW_NO_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="info",
            log_config=None,
            access_log=False,
        )
    finally:
        state_file.unlink(missing_ok=True)


def show_startup_error(message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            None,
            message,
            "AI 错题复盘工作台",
            0x10,
        )
    else:
        print(message, file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # frozen windowed build must show startup failures
        show_startup_error(str(exc) or "程序启动失败。")
        raise SystemExit(1) from exc
