import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import update

from backend.app.api.v1.operations import single_model_operation
from backend.app.db.models import QuestionConfirmation
from backend.app.main import create_app


class TestProtector:
    def protect(self, plaintext: bytes) -> bytes:
        return b"encrypted:" + plaintext[::-1]

    def unprotect(self, ciphertext: bytes) -> bytes:
        return ciphertext.removeprefix(b"encrypted:")[::-1]


def analysis_json(completeness: str = "complete", final_answer: str = "5") -> dict[str, object]:
    complete = completeness == "complete"
    return {
        "subject": "小学数学",
        "grade": "三年级",
        "normalized_question": "计算 $2+3$ 的值。",
        "question_completeness": completeness,
        "knowledge_points": ["整数加法"],
        "difficulty": "basic",
        "final_answer": final_answer if complete else "",
        "solution_overview": "将两个加数相加。" if complete else "",
        "solution_steps": (
            [
                {
                    "step": 1,
                    "content": "$2+3=5$。",
                    "reason": "按照整数加法规则计算。",
                    "knowledge_used": "整数加法",
                }
            ]
            if complete
            else []
        ),
        "possible_mistakes": ["可能把加法误看成乘法"],
        "memory_tip": "看清运算符号再计算。" if complete else "",
        "next_time_checklist": ["看运算符", "按顺序计算", "检查结果"] if complete else [],
        "confidence": "high" if complete else "low",
        "missing_information": [] if complete else ["题目中的第二个加数"],
    }


def setup_provider(client: TestClient, provider_type: str = "openai_compatible") -> str:
    return client.post(
        "/api/v1/providers",
        json={
            "capability": "text",
            "provider_type": provider_type,
            "display_name": "文本分析模型",
            "base_url": (
                "https://generativelanguage.googleapis.com/v1beta"
                if provider_type == "gemini"
                else "https://text.example.test/v1"
            ),
            "api_key": "text-secret",
            "model_name": "text-model",
            "timeout_seconds": 30,
        },
    ).json()["id"]


def setup_confirmed_question(client: TestClient, original: str = "原始错误文字") -> str:
    question_id = client.post(
        "/api/v1/questions", json={"input_type": "text", "source_text": original}
    ).json()["id"]
    response = client.post(
        f"/api/v1/questions/{question_id}/confirm",
        json={
            "confirmed_text": "计算 2 + 3 的值。",
            "subject": "小学数学",
            "grade": "三年级",
            "acknowledge_complete": True,
        },
    )
    assert response.status_code == 200
    return question_id


def test_analysis_is_blocked_before_confirmation(tmp_path: Path) -> None:
    called = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        setup_provider(client)
        question_id = client.post(
            "/api/v1/questions", json={"input_type": "text", "source_text": "2+3"}
        ).json()["id"]
        response = client.post(f"/api/v1/questions/{question_id}/analyze", json={})

    assert response.status_code == 409
    assert "确认" in response.json()["detail"]
    assert called is False


def test_openai_analysis_uses_only_confirmed_snapshot_and_schema(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(analysis_json(), ensure_ascii=False)}}
                ]
            },
        )

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client, "不要使用这段原始错误文字")
        setup_provider(client)
        response = client.post(f"/api/v1/questions/{question_id}/analyze", json={})
        fetched = client.get(f"/api/v1/questions/{question_id}/analysis")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["final_answer"] == "5"
    assert response.json()["verification"]["status"] == "verified"
    assert fetched.json() == response.json()
    body = json.loads(requests[0].content)
    prompt = body["messages"][1]["content"]
    assert "计算 2 + 3 的值" in prompt
    assert "不要使用这段原始错误文字" not in prompt
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True


def test_openai_compatible_repairs_successful_but_incompatible_json(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = (
            {"information_status": "complete", "answer": "5"}
            if len(requests) == 1
            else analysis_json()
        )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(body, ensure_ascii=False)}}]},
        )

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        response = client.post(f"/api/v1/questions/{question_id}/analyze", json={})

    assert response.status_code == 200
    assert response.json()["final_answer"] == "5"
    assert len(requests) == 2
    repair = json.loads(requests[1].content)
    assert repair["response_format"] == {"type": "json_object"}
    assert "不得改名" in repair["messages"][1]["content"]
    assert "JSON Schema" in repair["messages"][1]["content"]


def test_openai_compatible_falls_back_to_json_object_when_schema_mode_is_rejected(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(400, json={"error": "unsupported response format"})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(analysis_json(), ensure_ascii=False)}}
                ]
            },
        )

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        response = client.post(f"/api/v1/questions/{question_id}/analyze", json={})

    assert response.status_code == 200
    assert len(requests) == 2
    fallback = json.loads(requests[1].content)
    assert fallback["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in fallback["messages"][1]["content"]


def test_gemini_analysis_uses_structured_json_schema(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": json.dumps(analysis_json(), ensure_ascii=False)}]
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
        question_id = setup_confirmed_question(client)
        provider_id = setup_provider(client, "gemini")
        response = client.post(
            f"/api/v1/questions/{question_id}/analyze",
            json={"provider_id": provider_id},
        )

    assert response.status_code == 200
    assert str(requests[0].url).endswith("/models/text-model:generateContent")
    request_body = json.loads(requests[0].content)
    generation_config = request_body["generationConfig"]
    assert generation_config["responseMimeType"] == "application/json"
    assert generation_config["responseJsonSchema"]["additionalProperties"] is False
    assert requests[0].headers["x-goog-api-key"] == "text-secret"


def test_information_shortage_never_returns_answer_or_steps(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(analysis_json("partial"), ensure_ascii=False)
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
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        response = client.post(f"/api/v1/questions/{question_id}/analyze", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "needs_more_information"
    assert response.json()["final_answer"] == ""
    assert response.json()["solution_steps"] == []
    assert response.json()["missing_information"]


def test_confirmation_hash_mismatch_blocks_analysis(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path, secret_protector=TestProtector())
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        with app.state.session_factory() as session:
            session.execute(
                update(QuestionConfirmation)
                .where(QuestionConfirmation.question_id == question_id)
                .values(confirmed_text="被修改但未重新确认的文字")
            )
            session.commit()
        response = client.post(f"/api/v1/questions/{question_id}/analyze", json={})

    assert response.status_code == 409
    assert "重新确认" in response.json()["detail"]


def test_analysis_reports_network_timeout_empty_and_unparseable_responses(
    tmp_path: Path,
) -> None:
    scenarios: list[tuple[str, object, str]] = [
        (
            "network",
            httpx.ConnectError("offline"),
            "无法连接文本模型服务",
        ),
        (
            "timeout",
            httpx.ReadTimeout("slow"),
            "超时",
        ),
        (
            "empty",
            httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
            "没有可用分析",
        ),
        (
            "unparseable",
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": "not-json"}}]},
            ),
            "结构无效",
        ),
    ]

    for name, outcome, expected in scenarios:
        case_dir = tmp_path / name

        def handler(request: httpx.Request, result: object = outcome) -> httpx.Response:
            if isinstance(result, Exception):
                raise result
            assert isinstance(result, httpx.Response)
            return result

        app = create_app(
            data_dir=case_dir,
            secret_protector=TestProtector(),
            provider_transport=httpx.MockTransport(handler),
        )
        with TestClient(app) as client:
            question_id = setup_confirmed_question(client)
            setup_provider(client)
            response = client.post(f"/api/v1/questions/{question_id}/analyze", json={})

        assert response.status_code == 502
        assert expected in response.json()["detail"]


def test_duplicate_model_operation_is_rejected_while_first_is_running() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    app = SimpleNamespace(state=SimpleNamespace(active_model_operations=set()))
    request = Request({"type": "http", "app": app})

    @single_model_operation("analysis")
    async def operation(*, question_id: str, request: Request) -> str:
        started.set()
        await release.wait()
        return question_id

    async def scenario() -> tuple[str, HTTPException]:
        first = asyncio.create_task(operation(question_id="question-1", request=request))
        await started.wait()
        try:
            await operation(question_id="question-1", request=request)
        except HTTPException as exc:
            duplicate = exc
        else:
            raise AssertionError("duplicate operation was not rejected")
        release.set()
        return await first, duplicate

    result, duplicate = asyncio.run(scenario())
    assert result == "question-1"
    assert duplicate.status_code == 409
    assert "正在进行" in duplicate.detail


def test_math_verification_marks_conflicting_answer_without_silently_changing_it(
    tmp_path: Path,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                analysis_json(final_answer="6"), ensure_ascii=False
                            )
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
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        response = client.post(f"/api/v1/questions/{question_id}/analyze", json={})

    assert response.json()["final_answer"] == "6"
    assert response.json()["verification"]["status"] == "conflict"
    assert "5" in response.json()["verification"]["message"]
