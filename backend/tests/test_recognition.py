import json
from io import BytesIO
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.app.main import create_app
from backend.app.schemas.recognition import RecognitionOutput


class TestProtector:
    def protect(self, plaintext: bytes) -> bytes:
        return b"encrypted:" + plaintext[::-1]

    def unprotect(self, ciphertext: bytes) -> bytes:
        return ciphertext.removeprefix(b"encrypted:")[::-1]


def make_png() -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (900, 600), "white")
    ImageDraw.Draw(image).text((80, 100), "x^2 + 2x = 3", fill="black")
    image.save(output, format="PNG")
    return output.getvalue()


def setup_image_question(client: TestClient) -> str:
    question_id = client.post("/api/v1/questions", json={"input_type": "image"}).json()["id"]
    uploaded = client.post(
        f"/api/v1/questions/{question_id}/image",
        files={"file": ("question.png", make_png(), "image/png")},
    )
    assert uploaded.status_code == 201
    return question_id


def setup_vision_provider(client: TestClient, provider_type: str = "openai_compatible") -> str:
    base_url = (
        "https://generativelanguage.googleapis.com/v1beta"
        if provider_type == "gemini"
        else "https://vision.example.test/v1"
    )
    return client.post(
        "/api/v1/providers",
        json={
            "capability": "vision",
            "provider_type": provider_type,
            "display_name": "视觉模型",
            "base_url": base_url,
            "api_key": "vision-secret",
            "model_name": "vision-model",
            "timeout_seconds": 30,
        },
    ).json()["id"]


def recognition_json(completeness: str = "complete") -> dict[str, object]:
    return {
        "recognized_text": "解方程：$x^2-5x+6=0$。",
        "question_completeness": completeness,
        "confidence": "high" if completeness == "complete" else "low",
        "warnings": [] if completeness == "complete" else ["题目右侧可能被裁切"],
        "missing_information": [] if completeness == "complete" else ["右侧条件"],
        "detected_subject": "初中数学",
        "detected_grade": "八年级",
        "has_formula": True,
        "has_diagram": False,
    }


def test_recognition_normalizes_unescaped_latex_tab_commands() -> None:
    output = RecognitionOutput.model_validate(
        {
            "recognized_text": "求 \\triangle ABC 与 \\theta 的值。".replace("\\t", "\t"),
            "question_completeness": "complete",
            "confidence": "high",
            "warnings": [],
            "missing_information": [],
            "detected_subject": "数学",
            "detected_grade": "九年级",
            "has_formula": True,
            "has_diagram": True,
        }
    )

    assert "\\triangle" in output.recognized_text
    assert "\\theta" in output.recognized_text


def test_openai_vision_recognition_sends_image_and_returns_validated_result(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(recognition_json(), ensure_ascii=False)}}
                ]
            },
        )

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_image_question(client)
        provider_id = setup_vision_provider(client)
        response = client.post(
            f"/api/v1/questions/{question_id}/recognize",
            json={"provider_id": provider_id},
        )

    assert response.status_code == 200
    assert response.json()["recognized_text"].startswith("解方程")
    assert response.json()["prompt_version"] == "recognition-v1"
    assert response.json()["model_name"] == "vision-model"
    request_body = json.loads(requests[0].content)
    image_url = request_body["messages"][1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
    assert "只提取题目" in request_body["messages"][0]["content"]


def test_gemini_vision_recognition_uses_inline_data(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": json.dumps(recognition_json(), ensure_ascii=False)}]
                        }
                    }
                ]
            },
        )

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_image_question(client)
        provider_id = setup_vision_provider(client, "gemini")
        response = client.post(
            f"/api/v1/questions/{question_id}/recognize",
            json={"provider_id": provider_id},
        )

    assert response.status_code == 200
    assert str(requests[0].url).endswith("/models/vision-model:generateContent")
    body = json.loads(requests[0].content)
    inline_data = body["contents"][0]["parts"][1]["inline_data"]
    assert inline_data["mime_type"] == "image/png"
    assert inline_data["data"]
    assert requests[0].headers["x-goog-api-key"] == "vision-secret"


def test_partial_recognition_keeps_warning_and_does_not_confirm_question(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(recognition_json("partial"), ensure_ascii=False)
                        }
                    }
                ]
            },
        )

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_image_question(client)
        setup_vision_provider(client)
        recognized = client.post(f"/api/v1/questions/{question_id}/recognize", json={})
        question = client.get(f"/api/v1/questions/{question_id}")

    assert recognized.json()["question_completeness"] == "partial"
    assert recognized.json()["missing_information"] == ["右侧条件"]
    assert question.json()["status"] == "recognition_review"


def test_confirmation_requires_explicit_acknowledgement_and_saves_snapshot(
    tmp_path: Path,
) -> None:
    app = create_app(data_dir=tmp_path, secret_protector=TestProtector())
    with TestClient(app) as client:
        question_id = client.post(
            "/api/v1/questions",
            json={"input_type": "text", "source_text": "求 2 + 3 的值。"},
        ).json()["id"]
        rejected = client.post(
            f"/api/v1/questions/{question_id}/confirm",
            json={
                "confirmed_text": "求 2 + 3 的值。",
                "acknowledge_complete": False,
            },
        )
        confirmed = client.post(
            f"/api/v1/questions/{question_id}/confirm",
            json={
                "confirmed_text": "求 2 + 3 的值。",
                "subject": "小学数学",
                "grade": "三年级",
                "user_answer": "6",
                "acknowledge_complete": True,
            },
        )
        fetched = client.get(f"/api/v1/questions/{question_id}/confirmation")

    assert rejected.status_code == 422
    assert confirmed.status_code == 200
    assert confirmed.json()["confirmed_text_hash"]
    assert confirmed.json()["confirmed_text"] == "求 2 + 3 的值。"
    assert fetched.json() == confirmed.json()


def test_recognition_without_vision_provider_is_blocked(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path, secret_protector=TestProtector())
    with TestClient(app) as client:
        question_id = setup_image_question(client)
        response = client.post(f"/api/v1/questions/{question_id}/recognize", json={})

    assert response.status_code == 409
    assert "视觉模型" in response.json()["detail"]
