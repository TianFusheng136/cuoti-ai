from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LOCAL_ORIGIN_PORTS = {3002, 5173, 8000}


def is_allowed_local_origin(origin: str) -> bool:
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
        and port in LOCAL_ORIGIN_PORTS
        and not parsed.username
        and not parsed.password
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


class LocalOriginMiddleware:
    """Reject browser cross-origin writes while keeping local CLI clients usable."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        origin_bytes = headers.get(b"origin")
        method = str(scope.get("method") or "GET").upper()
        if method in MUTATING_METHODS and origin_bytes is not None:
            try:
                origin = origin_bytes.decode("ascii")
            except UnicodeDecodeError:
                origin = ""
            if not is_allowed_local_origin(origin):
                response = JSONResponse(
                    {"detail": "已拒绝非本地页面发起的数据修改请求。"}, status_code=403
                )
                await response(scope, receive, send)
                return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-frame-options", b"DENY"),
                        (
                            b"content-security-policy",
                            b"default-src 'self'; base-uri 'none'; object-src 'none'; "
                            b"frame-ancestors 'none'; form-action 'self'; "
                            b"script-src 'self'; style-src 'self' 'unsafe-inline'; "
                            b"font-src 'self' data:; img-src 'self' data: blob:; "
                            b"connect-src 'self'",
                        ),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    ]
                )
                message["headers"] = response_headers
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
