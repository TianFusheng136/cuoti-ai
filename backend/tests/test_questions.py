from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.app.main import create_app


def make_png() -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (80, 60), "white")
    ImageDraw.Draw(image).rectangle((10, 20, 70, 30), fill="black")
    image.save(output, format="PNG")
    return output.getvalue()


def create_image_question(client: TestClient) -> str:
    response = client.post("/api/v1/questions", json={"input_type": "image"})
    assert response.status_code == 201
    return response.json()["id"]


def test_create_and_get_text_question(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/questions",
            json={"input_type": "text", "source_text": "  解方程：x² - 5x + 6 = 0  "},
        )
        fetched = client.get(f"/api/v1/questions/{created.json()['id']}")

    assert created.status_code == 201
    assert created.json()["source_text"] == "解方程：x² - 5x + 6 = 0"
    assert created.json()["status"] == "draft"
    assert fetched.status_code == 200
    assert fetched.json() == created.json()


def test_text_question_rejects_blank_content(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/questions", json={"input_type": "text", "source_text": "   "}
        )

    assert response.status_code == 422


def test_upload_valid_image_and_delete_question_removes_file(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)

    with TestClient(app) as client:
        question_id = create_image_question(client)
        uploaded = client.post(
            f"/api/v1/questions/{question_id}/image",
            files={"file": ("题目.png", make_png(), "image/png")},
        )
        relative_path = uploaded.json()["relative_path"]
        stored_file = tmp_path / relative_path
        downloaded = client.get(f"/api/v1/questions/{question_id}/image")
        deleted = client.delete(f"/api/v1/questions/{question_id}")

    assert uploaded.status_code == 201
    assert uploaded.json()["mime_type"] == "image/png"
    assert uploaded.json()["width"] == 80
    assert uploaded.json()["height"] == 60
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "image/png"
    assert downloaded.content == make_png()
    assert not stored_file.exists()
    assert deleted.status_code == 204


def test_upload_rejects_disguised_or_unsupported_file(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)

    with TestClient(app) as client:
        question_id = create_image_question(client)
        disguised = client.post(
            f"/api/v1/questions/{question_id}/image",
            files={"file": ("题目.jpg", b"not an image", "image/jpeg")},
        )
        unsupported = client.post(
            f"/api/v1/questions/{question_id}/image",
            files={"file": ("题目.gif", make_png(), "image/gif")},
        )

    assert disguised.status_code == 415
    assert "有效的题目图片" in disguised.json()["detail"]
    assert unsupported.status_code == 415
    assert "JPG、PNG 或 WebP" in unsupported.json()["detail"]


def test_upload_rejects_empty_oversized_blank_and_huge_pixel_images(
    tmp_path: Path,
) -> None:
    app = create_app(data_dir=tmp_path)
    blank = BytesIO()
    Image.new("RGB", (800, 600), "white").save(blank, format="PNG")
    huge = BytesIO()
    huge_image = Image.new("1", (6500, 6500), 1)
    ImageDraw.Draw(huge_image).rectangle((10, 10, 20, 20), fill=0)
    huge_image.save(huge, format="PNG")

    with TestClient(app) as client:
        empty_id = create_image_question(client)
        empty = client.post(
            f"/api/v1/questions/{empty_id}/image",
            files={"file": ("empty.png", b"", "image/png")},
        )
        oversized_id = create_image_question(client)
        oversized = client.post(
            f"/api/v1/questions/{oversized_id}/image",
            files={"file": ("large.png", b"x" * (15 * 1024 * 1024 + 1), "image/png")},
        )
        blank_id = create_image_question(client)
        blank_response = client.post(
            f"/api/v1/questions/{blank_id}/image",
            files={"file": ("blank.png", blank.getvalue(), "image/png")},
        )
        huge_id = create_image_question(client)
        huge_response = client.post(
            f"/api/v1/questions/{huge_id}/image",
            files={"file": ("huge.png", huge.getvalue(), "image/png")},
        )

    assert empty.status_code == 415
    assert "内容为空" in empty.json()["detail"]
    assert oversized.status_code == 415
    assert "15MB" in oversized.json()["detail"]
    assert blank_response.status_code == 415
    assert "接近空白" in blank_response.json()["detail"]
    assert huge_response.status_code == 415
    assert "4000 万像素" in huge_response.json()["detail"]


def test_list_questions_returns_newest_first(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/questions", json={"input_type": "text", "source_text": "第一题"}
        ).json()
        second = client.post(
            "/api/v1/questions", json={"input_type": "text", "source_text": "第二题"}
        ).json()
        response = client.get("/api/v1/questions")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [second["id"], first["id"]]
    assert response.json()["total"] == 2
