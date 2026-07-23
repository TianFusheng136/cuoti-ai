from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_health_endpoint_reports_local_app(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "AI 错题复盘工作台",
        "api_version": "v1",
    }
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_startup_initializes_local_database(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)

    with TestClient(app):
        pass

    assert (tmp_path / "app.db").is_file()
    assert (tmp_path / "uploads").is_dir()
    assert (tmp_path / "exports").is_dir()
    assert (tmp_path / "logs").is_dir()


def test_untrusted_host_is_rejected(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)

    with TestClient(app) as client:
        response = client.get("/api/v1/health", headers={"host": "attacker.example"})

    assert response.status_code == 400


def test_cross_origin_mutation_is_rejected(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/questions",
            headers={"origin": "https://attacker.example"},
            json={"input_type": "text", "source_text": "不应写入"},
        )
        questions = client.get("/api/v1/questions")

    assert response.status_code == 403
    assert questions.json()["total"] == 0


def test_local_development_origin_is_allowed(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/questions",
            headers={"origin": "http://127.0.0.1:5173"},
            json={"input_type": "text", "source_text": "允许写入"},
        )

    assert response.status_code == 201


def test_release_mode_disables_api_documentation(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path, expose_api_docs=False)

    with TestClient(app) as client:
        docs = client.get("/api/docs")
        schema = client.get("/api/openapi.json")

    assert docs.status_code == 404
    assert schema.status_code == 404


def test_built_frontend_is_served_by_fastapi(tmp_path: Path) -> None:
    frontend_dist = tmp_path / "dist"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text(
        "<html><body>本地工作台</body></html>", encoding="utf-8"
    )
    app = create_app(data_dir=tmp_path / "data", frontend_dist=frontend_dist)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "本地工作台" in response.text
