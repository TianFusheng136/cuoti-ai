import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.tests.test_analysis import TestProtector, setup_provider


def test_backup_contains_database_and_uploads_but_never_api_keys(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path, secret_protector=TestProtector())
    with TestClient(app) as client:
        setup_provider(client)
        question_id = client.post(
            "/api/v1/questions",
            json={"input_type": "text", "source_text": "备份中的题目"},
        ).json()["id"]
        response = client.get("/api/v1/data/backup")

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        extracted_content = b"".join(archive.read(name) for name in names)
    assert "backup/app.db" in names
    assert manifest["includes_api_keys"] is False
    assert not any(name.startswith("config/") for name in names)
    assert b"text-secret" not in extracted_content
    assert question_id.encode() in extracted_content


def test_restore_is_applied_on_restart_and_model_keys_must_be_reentered(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path, secret_protector=TestProtector())
    with TestClient(app) as client:
        provider_id = setup_provider(client)
        question_id = client.post(
            "/api/v1/questions",
            json={"input_type": "text", "source_text": "需要恢复的题目"},
        ).json()["id"]
        restored_asset = tmp_path / "uploads" / "2026" / "07" / "asset.bin"
        restored_asset.parent.mkdir(parents=True)
        restored_asset.write_bytes(b"local-image-content")
        backup = client.get("/api/v1/data/backup").content
        client.delete(f"/api/v1/questions/{question_id}")
        restored_asset.unlink()
        staged = client.post(
            "/api/v1/data/restore",
            files={"file": ("backup.zip", backup, "application/zip")},
        )
        assert client.get(f"/api/v1/questions/{question_id}").status_code == 404

    assert staged.status_code == 200
    assert staged.json()["requires_restart"] is True

    restored_app = create_app(data_dir=tmp_path, secret_protector=TestProtector())
    with TestClient(restored_app) as client:
        restored = client.get(f"/api/v1/questions/{question_id}")
        provider = client.get(f"/api/v1/providers/{provider_id}")
        rekeyed = client.put(
            f"/api/v1/providers/{provider_id}",
            json={
                "display_name": "恢复后的文本模型",
                "base_url": "https://text.example.test/v1",
                "model_name": "text-model",
                "timeout_seconds": 30,
                "enabled": True,
                "api_key": "new-local-key",
            },
        )

    assert restored.status_code == 200
    assert restored.json()["source_text"] == "需要恢复的题目"
    assert restored_asset.read_bytes() == b"local-image-content"
    assert provider.json()["enabled"] is False
    assert provider.json()["has_api_key"] is False
    assert provider.json()["api_key_masked"] == ""
    assert rekeyed.status_code == 200
    assert rekeyed.json()["enabled"] is True
    assert rekeyed.json()["has_api_key"] is True


def test_restore_rejects_path_traversal_archive(tmp_path: Path) -> None:
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("../outside.txt", "unsafe")
        archive.writestr("manifest.json", "{}")
        archive.writestr("backup/app.db", "not a database")

    app = create_app(data_dir=tmp_path, secret_protector=TestProtector())
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/data/restore",
            files={"file": ("backup.zip", content.getvalue(), "application/zip")},
        )

    assert response.status_code == 400
    assert "不安全路径" in response.json()["detail"]
    assert not (tmp_path.parent / "outside.txt").exists()


def test_notebook_can_be_exported_as_json_and_csv(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path, secret_protector=TestProtector())
    with TestClient(app) as client:
        json_response = client.get("/api/v1/data/export?format=json")
        csv_response = client.get("/api/v1/data/export?format=csv")

    assert json_response.status_code == 200
    assert json_response.json()["format"] == "ai-error-review-notebook-export"
    assert json_response.json()["items"] == []
    csv_text = csv_response.content.decode("utf-8-sig")
    assert "question_id,question,subject" in csv_text
    assert "secret" not in csv_text.casefold()
