from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from backend.app.main import create_app


class TestProtector:
    def protect(self, plaintext: bytes) -> bytes:
        return b"encrypted:" + plaintext[::-1]

    def unprotect(self, ciphertext: bytes) -> bytes:
        assert ciphertext.startswith(b"encrypted:")
        return ciphertext.removeprefix(b"encrypted:")[::-1]


def provider_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "capability": "text",
        "provider_type": "openai_compatible",
        "display_name": "我的文本模型",
        "base_url": "https://models.example.test/v1",
        "api_key": "local-test-api-key-not-a-secret",
        "model_name": "example-chat-model",
        "timeout_seconds": 30,
    }
    payload.update(overrides)
    return payload


def test_provider_key_is_encrypted_and_never_returned(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path, secret_protector=TestProtector())

    with TestClient(app) as client:
        created = client.post("/api/v1/providers", json=provider_payload())
        listed = client.get("/api/v1/providers")

    assert created.status_code == 201
    assert created.json()["has_api_key"] is True
    assert created.json()["api_key_masked"] == "••••••••"
    assert "api_key" not in created.json()
    assert "secret_ref" not in created.json()
    assert listed.json()[0] == created.json()

    secret_files = list((tmp_path / "config" / "secrets").glob("*.bin"))
    assert len(secret_files) == 1
    secret_content = secret_files[0].read_bytes()
    assert b"local-test-api-key-not-a-secret" not in secret_content
    assert secret_content.startswith(b"encrypted:")


def test_openai_compatible_connection_uses_models_endpoint_and_bearer_key(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": "example-chat-model"}]})

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )

    with TestClient(app) as client:
        provider_id = client.post("/api/v1/providers", json=provider_payload()).json()["id"]
        response = client.post(f"/api/v1/providers/{provider_id}/test")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["message"] == "连接成功，已找到配置的模型。"
    assert str(requests[0].url) == "https://models.example.test/v1/models"
    assert requests[0].headers["authorization"] == "Bearer local-test-api-key-not-a-secret"


def test_gemini_connection_uses_documented_model_resource(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"name": "models/gemini-test"})

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )

    with TestClient(app) as client:
        provider_id = client.post(
            "/api/v1/providers",
            json=provider_payload(
                capability="vision",
                provider_type="gemini",
                base_url="https://generativelanguage.googleapis.com/v1beta/",
                model_name="gemini-test",
            ),
        ).json()["id"]
        response = client.post(f"/api/v1/providers/{provider_id}/test")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert str(requests[0].url) == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-test"
    )
    assert requests[0].headers["x-goog-api-key"] == "local-test-api-key-not-a-secret"


def test_update_preserves_key_and_delete_removes_encrypted_file(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path, secret_protector=TestProtector())

    with TestClient(app) as client:
        provider_id = client.post("/api/v1/providers", json=provider_payload()).json()["id"]
        secret_file = next((tmp_path / "config" / "secrets").glob("*.bin"))
        updated = client.put(
            f"/api/v1/providers/{provider_id}",
            json={
                "display_name": "更新后的模型",
                "base_url": "https://new.example.test/v1",
                "model_name": "new-model",
                "timeout_seconds": 45,
            },
        )
        deleted = client.delete(f"/api/v1/providers/{provider_id}")

    assert updated.status_code == 200
    assert updated.json()["display_name"] == "更新后的模型"
    assert updated.json()["has_api_key"] is True
    assert deleted.status_code == 204
    assert not secret_file.exists()


def test_connection_test_reports_authentication_network_and_timeout_errors(
    tmp_path: Path,
) -> None:
    scenarios: list[tuple[str, object, str]] = [
        (
            "authentication",
            httpx.Response(401, json={"error": "invalid key"}),
            "认证失败",
        ),
        ("network", httpx.ConnectError("offline"), "无法连接模型服务"),
        ("timeout", httpx.ReadTimeout("slow"), "连接超时"),
    ]

    for name, outcome, expected in scenarios:

        def handler(request: httpx.Request, result: object = outcome) -> httpx.Response:
            if isinstance(result, Exception):
                raise result
            assert isinstance(result, httpx.Response)
            return result

        app = create_app(
            data_dir=tmp_path / name,
            secret_protector=TestProtector(),
            provider_transport=httpx.MockTransport(handler),
        )
        with TestClient(app) as client:
            provider_id = client.post("/api/v1/providers", json=provider_payload()).json()["id"]
            response = client.post(f"/api/v1/providers/{provider_id}/test")

        assert response.status_code == 200
        assert response.json()["success"] is False
        assert expected in response.json()["message"]


def test_provider_rejects_non_http_base_url(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path, secret_protector=TestProtector())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/providers", json=provider_payload(base_url="file:///local/secret")
        )

    assert response.status_code == 422
