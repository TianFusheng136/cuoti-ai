import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.providers.text import TextProviderError
from backend.app.providers.variation import VariationProvider
from backend.app.schemas.learning import VariationDraft
from backend.tests.test_analysis import (
    TestProtector,
    analysis_json,
    setup_confirmed_question,
    setup_provider,
)

VARIANT_TYPES = ("same_point", "new_context", "challenge")


def variation_item(variant_type: str) -> dict[str, object]:
    items = {
        "same_point": {
            "type": "same_point",
            "title": "同知识点巩固",
            "question": "计算 $4+5$。",
            "answer": "$9$",
            "solution": "$4+5=9$。",
            "knowledge_points": ["整数加法"],
            "difficulty": "basic",
        },
        "new_context": {
            "type": "new_context",
            "title": "换场景迁移",
            "question": "盒中有 3 支笔，又放入 6 支，共有多少支？",
            "answer": "9 支",
            "solution": "$3+6=9$。",
            "knowledge_points": ["整数加法", "应用题"],
            "difficulty": "basic",
        },
        "challenge": {
            "type": "challenge",
            "title": "提高难度",
            "question": "计算 $12+19$。",
            "answer": "$31$",
            "solution": "$12+19=31$。",
            "knowledge_points": ["整数加法", "进位加法"],
            "difficulty": "medium",
        },
    }
    return dict(items[variant_type])


def single_variation_json(variant_type: str) -> dict[str, object]:
    draft = variation_item(variant_type)
    draft.pop("answer")
    draft.pop("solution")
    return {"draft": draft}


def independent_solution_json(
    variant_type: str,
    solvable: bool = True,
    issue: str = "题目条件不足",
) -> dict[str, object]:
    return {
        "type": variant_type,
        "solvable": solvable,
        "answer_determined": solvable,
        "answer": "9" if variant_type != "challenge" else "31",
        "reasoning": "独立计算得到该结果。",
        "issues": [] if solvable else [issue],
    }


def resolved_answer_json(variant_type: str) -> dict[str, object]:
    return {
        "answer": "9" if variant_type != "challenge" else "31",
        "solution": "独立计算并检验，得到最终答案。",
    }


def verification_json(
    variant_type: str,
    valid: bool = True,
    issue: str = "答案与题目不一致",
) -> dict[str, object]:
    return {
        "type": variant_type,
        "valid": valid,
        "recomputed_answer": "9" if variant_type != "challenge" else "31",
        "issues": [] if valid else [issue],
    }


def request_text(request: httpx.Request) -> tuple[str, str]:
    payload = json.loads(request.content)
    if "messages" in payload:
        return payload["messages"][0]["content"], payload["messages"][1]["content"]
    return (
        payload["systemInstruction"]["parts"][0]["text"],
        payload["contents"][0]["parts"][0]["text"],
    )


def requested_type(text: str) -> str:
    for variant_type in VARIANT_TYPES:
        if f"指定类型：{variant_type}" in text or f'"type": "{variant_type}"' in text:
            return variant_type
    raise AssertionError(f"请求中没有变式类型：{text[:200]}")


def model_response(request: httpx.Request, body: dict[str, object]) -> httpx.Response:
    content = json.dumps(body, ensure_ascii=False)
    payload = json.loads(request.content)
    if "messages" in payload:
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    return httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": content}]}}]},
    )


def standard_handler(
    requests: list[httpx.Request],
    request: httpx.Request,
) -> httpx.Response:
    requests.append(request)
    if len(requests) == 1:
        return model_response(request, analysis_json())
    system, user = request_text(request)
    variant_type = requested_type(user)
    if system.startswith("你是盲解老师"):
        body = independent_solution_json(variant_type)
    elif system.startswith("你是面向学生的答案编辑老师"):
        body = resolved_answer_json(variant_type)
    elif "最终审题老师" in system:
        body = verification_json(variant_type)
    else:
        body = single_variation_json(variant_type)
    return model_response(request, body)


def analyzed_client(tmp_path: Path) -> tuple[TestClient, str, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return standard_handler(requests, request)

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    client = TestClient(app)
    client.__enter__()
    question_id = setup_confirmed_question(client)
    setup_provider(client)
    response = client.post(f"/api/v1/questions/{question_id}/analyze", json={})
    assert response.status_code == 200
    return client, question_id, requests


def test_completed_analysis_enters_notebook_and_accepts_real_error_reason(
    tmp_path: Path,
) -> None:
    client, question_id, _ = analyzed_client(tmp_path)
    try:
        updated = client.put(
            f"/api/v1/questions/{question_id}/learning",
            json={
                "actual_error_reason": "calculation",
                "actual_error_note": "进位时忘记加一",
                "starred": True,
            },
        )
        notebook = client.get("/api/v1/notebook?search=整数加法&starred=true")
    finally:
        client.__exit__(None, None, None)

    assert updated.status_code == 200
    assert updated.json()["actual_error_reason"] == "calculation"
    assert notebook.status_code == 200
    assert notebook.json()["facets"]["total"] == 1
    assert notebook.json()["items"][0]["actual_error_note"] == "进位时忘记加一"
    assert notebook.json()["items"][0]["starred"] is True


def test_variations_generate_and_verify_each_type_separately(tmp_path: Path) -> None:
    client, question_id, requests = analyzed_client(tmp_path)
    try:
        response = client.post(f"/api/v1/questions/{question_id}/variations", json={})
        fetched = client.get(f"/api/v1/questions/{question_id}/variations")
    finally:
        client.__exit__(None, None, None)

    assert response.status_code == 200
    assert fetched.json() == response.json()
    assert [item["type"] for item in response.json()["variants"]] == list(VARIANT_TYPES)
    variation_requests = requests[1:]
    assert len(variation_requests) == 12
    generation_requests = [
        request for request in variation_requests if "练习题设计老师" in request_text(request)[0]
    ]
    verification_requests = [
        request for request in variation_requests if "最终审题老师" in request_text(request)[0]
    ]
    assert {requested_type(request_text(item)[1]) for item in generation_requests} == set(
        VARIANT_TYPES
    )
    assert len(verification_requests) == 3
    blind_requests = [
        request
        for request in variation_requests
        if request_text(request)[0].startswith("你是盲解老师")
    ]
    assert len(blind_requests) == 3
    assert (
        sum(
            request_text(item)[0].startswith("你是面向学生的答案编辑老师")
            for item in variation_requests
        )
        == 3
    )
    assert "$9$" not in request_text(blind_requests[0])[1]
    assert "question_only" in request_text(blind_requests[0])[1]
    assert "independent_solution" not in request_text(verification_requests[0])[1]
    assert "recomputed_answer" in request_text(verification_requests[0])[1]
    generation_body = json.loads(generation_requests[0].content)
    assert generation_body["response_format"]["json_schema"]["strict"] is True
    prompt = request_text(generation_requests[0])[1]
    assert "计算 $2+3$ 的值" in prompt
    assert "final_answer" not in prompt
    assert "solution_steps" not in prompt
    assert "solution_overview" in prompt


def test_absolute_context_rejects_nonnegative_real_world_quantity() -> None:
    analysis = {"knowledge_points": ["绝对值方程"], "normalized_question": "|2x-3|=5"}
    invalid = VariationDraft(
        type="new_context",
        title="测量",
        question="物体实际长度3厘米，测量值x的误差为5厘米。",
        knowledge_points=["绝对值方程"],
        difficulty="basic",
    )
    valid = VariationDraft(
        type="new_context",
        title="数轴距离",
        question="数轴上点x到点3的距离为5，求x。",
        knowledge_points=["绝对值方程"],
        difficulty="basic",
    )

    assert VariationProvider.draft_issues(analysis, invalid)
    assert VariationProvider.draft_issues(analysis, valid) == ()


def test_absolute_specialist_uses_distinct_types_without_model_generation(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            body = analysis_json()
            body.update(
                {
                    "subject": "初中数学",
                    "grade": "八年级",
                    "normalized_question": "解方程：|2x-3|=5。",
                    "knowledge_points": ["绝对值方程", "一元一次方程"],
                    "difficulty": "basic",
                    "final_answer": "x=4或x=-1",
                }
            )
            return model_response(request, body)
        raise AssertionError("绝对值安全题型不应继续调用模型生成或验算")

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        assert client.post(f"/api/v1/questions/{question_id}/analyze", json={}).status_code == 200
        generated = client.post(f"/api/v1/questions/{question_id}/variations", json={})

    assert generated.status_code == 200
    assert generated.json()["model_name"] == "deterministic-absolute-v1"
    assert len(requests) == 1
    variants = generated.json()["variants"]
    assert variants[0]["question"].startswith("解方程")
    assert "数轴" in variants[1]["question"]
    assert "a为实数" in variants[2]["question"]


def test_coordinate_specialist_calculates_three_distinct_types(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            body = analysis_json()
            body.update(
                {
                    "subject": "初中数学",
                    "grade": "八年级",
                    "normalized_question": "求线段中点和三角形面积。",
                    "knowledge_points": ["中点坐标公式", "三角形面积", "坐标几何"],
                    "difficulty": "basic",
                    "final_answer": "中点(1,1)，面积12。",
                }
            )
            return model_response(request, body)
        raise AssertionError("坐标安全题型不应继续调用模型生成或验算")

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        assert client.post(f"/api/v1/questions/{question_id}/analyze", json={}).status_code == 200
        generated = client.post(f"/api/v1/questions/{question_id}/variations", json={})

    assert generated.status_code == 200
    assert generated.json()["model_name"] == "deterministic-coordinate-v1"
    assert len(requests) == 1
    variants = generated.json()["variants"]
    assert "中点" in variants[0]["title"]
    assert "地图" in variants[1]["title"]
    assert "轴对称" in variants[2]["title"]


def test_work_power_specialist_avoids_conflicting_force_conditions(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            body = analysis_json()
            body.update(
                {
                    "subject": "初中物理",
                    "grade": "九年级",
                    "normalized_question": "求水平拉力做的功和功率。",
                    "knowledge_points": ["功的计算", "功率的计算"],
                    "difficulty": "basic",
                    "final_answer": "240J，60W。",
                }
            )
            return model_response(request, body)
        raise AssertionError("功率安全题型不应继续调用模型生成或验算")

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        assert client.post(f"/api/v1/questions/{question_id}/analyze", json={}).status_code == 200
        generated = client.post(f"/api/v1/questions/{question_id}/variations", json={})

    assert generated.status_code == 200
    assert generated.json()["model_name"] == "deterministic-work-power-v1"
    assert len(requests) == 1
    variants = generated.json()["variants"]
    assert "水平拉力" in variants[0]["title"]
    assert "起重机" in variants[1]["title"]
    assert "效率" in variants[2]["title"]
    assert all("摩擦力" not in item["question"] for item in variants)


def test_parabola_specialist_rejects_invalid_formula_parameters() -> None:
    VariationProvider.require_parabola_spec_valid(2, 6, 2)
    with pytest.raises(TextProviderError, match="参数无效"):
        VariationProvider.require_parabola_spec_valid(4, 2)
    with pytest.raises(TextProviderError, match="范围参数无效"):
        VariationProvider.require_parabola_spec_valid(2, 6, 3)


def test_parabola_area_uses_formula_specialist_with_deterministic_verification(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            body = analysis_json()
            body.update(
                {
                    "subject": "初中数学",
                    "grade": "九年级",
                    "normalized_question": "求抛物线上动点构成三角形的面积最大值。",
                    "knowledge_points": ["抛物线解析式", "三角形面积", "二次函数最值"],
                    "difficulty": "medium",
                    "final_answer": "最大面积为27/8。",
                }
            )
            return model_response(request, body)
        raise AssertionError("抛物线安全题型不应继续调用不可靠的模型验算")

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        assert client.post(f"/api/v1/questions/{question_id}/analyze", json={}).status_code == 200
        generated = client.post(f"/api/v1/questions/{question_id}/variations", json={})

    assert generated.status_code == 200
    assert generated.json()["model_name"] == "deterministic-parabola-v1"
    assert len(requests) == 1
    variants = generated.json()["variants"]
    assert [item["type"] for item in variants] == list(VARIANT_TYPES)
    assert all("如图" not in item["question"] for item in variants)
    assert all("四边形" not in item["question"] for item in variants)
    assert "y=-x²+" in variants[0]["answer"]
    assert "铅锤法" in variants[0]["knowledge_points"]
    assert "S=" in variants[2]["answer"]


def test_gemini_variations_use_native_single_response_schema(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return standard_handler(requests, request)

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client)
        provider_id = setup_provider(client, "gemini")
        assert (
            client.post(
                f"/api/v1/questions/{question_id}/analyze", json={"provider_id": provider_id}
            ).status_code
            == 200
        )
        response = client.post(
            f"/api/v1/questions/{question_id}/variations",
            json={"provider_id": provider_id},
        )

    assert response.status_code == 200
    generation = next(
        request for request in requests[1:] if "练习题设计老师" in request_text(request)[0]
    )
    payload = json.loads(generation.content)
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    schema = payload["generationConfig"]["responseJsonSchema"]
    assert schema["additionalProperties"] is False
    assert generation.headers["x-goog-api-key"] == "text-secret"
    assert sum("最终审题老师" in request_text(item)[0] for item in requests) == 3
    assert sum(request_text(item)[0].startswith("你是盲解老师") for item in requests) == 3


def test_only_failed_type_is_retried_with_verifier_feedback(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    challenge_checks = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal challenge_checks
        requests.append(request)
        if len(requests) == 1:
            return model_response(request, analysis_json())
        system, user = request_text(request)
        variant_type = requested_type(user)
        if system.startswith("你是盲解老师"):
            return model_response(request, independent_solution_json(variant_type))
        if system.startswith("你是面向学生的答案编辑老师"):
            return model_response(request, resolved_answer_json(variant_type))
        if "最终审题老师" in system:
            if variant_type == "challenge":
                challenge_checks += 1
            valid = variant_type != "challenge" or challenge_checks > 1
            return model_response(
                request,
                verification_json(variant_type, valid, "挑战题答案漏掉第二种情况"),
            )
        return model_response(request, single_variation_json(variant_type))

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        client.post(f"/api/v1/questions/{question_id}/analyze", json={})
        generated = client.post(f"/api/v1/questions/{question_id}/variations", json={})

    assert generated.status_code == 200
    generation_prompts = [
        request_text(item)[1] for item in requests if "练习题设计老师" in request_text(item)[0]
    ]
    assert sum("指定类型：same_point" in item for item in generation_prompts) == 1
    assert sum("指定类型：new_context" in item for item in generation_prompts) == 1
    assert sum("指定类型：challenge" in item for item in generation_prompts) == 2
    assert "挑战题答案漏掉第二种情况" in generation_prompts[-1]


def test_failed_independent_verification_is_rejected_and_not_exposed(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return model_response(request, analysis_json())
        system, user = request_text(request)
        variant_type = requested_type(user)
        if system.startswith("你是盲解老师"):
            return model_response(request, independent_solution_json(variant_type))
        if system.startswith("你是面向学生的答案编辑老师"):
            return model_response(request, resolved_answer_json(variant_type))
        if "最终审题老师" in system:
            valid = variant_type != "challenge"
            return model_response(
                request,
                verification_json(variant_type, valid, "题目条件不足，答案不唯一"),
            )
        return model_response(request, single_variation_json(variant_type))

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        client.post(f"/api/v1/questions/{question_id}/analyze", json={})
        generated = client.post(f"/api/v1/questions/{question_id}/variations", json={})
        fetched = client.get(f"/api/v1/questions/{question_id}/variations")

    assert generated.status_code == 502
    assert "提高难度" in generated.json()["detail"]
    assert "题目条件不足" in generated.json()["detail"]
    assert "定向重试 4 次" in generated.json()["detail"]
    assert fetched.status_code == 404


def test_self_correction_is_repaired_without_regenerating_other_types(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    same_point_generations = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal same_point_generations
        requests.append(request)
        if len(requests) == 1:
            return model_response(request, analysis_json())
        system, user = request_text(request)
        variant_type = requested_type(user)
        if system.startswith("你是盲解老师"):
            return model_response(request, independent_solution_json(variant_type))
        if system.startswith("你是面向学生的答案编辑老师"):
            body = resolved_answer_json(variant_type)
            if variant_type == "same_point" and same_point_generations == 1:
                body["solution"] = "等等，重新计算后修正答案。"
            return model_response(request, body)
        if "最终审题老师" in system:
            return model_response(request, verification_json(variant_type))
        body = single_variation_json(variant_type)
        if variant_type == "same_point":
            same_point_generations += 1
        return model_response(request, body)

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        client.post(f"/api/v1/questions/{question_id}/analyze", json={})
        generated = client.post(f"/api/v1/questions/{question_id}/variations", json={})

    assert generated.status_code == 200
    assert same_point_generations == 2
    prompts = [
        request_text(item)[1] for item in requests if "练习题设计老师" in request_text(item)[0]
    ]
    assert any("自我纠错" in item for item in prompts)


def test_invalid_variation_schema_is_rejected_and_not_exposed(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = analysis_json() if len(requests) == 1 else {"variant": {}}
        return model_response(request, body)

    app = create_app(
        data_dir=tmp_path,
        secret_protector=TestProtector(),
        provider_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        client.post(f"/api/v1/questions/{question_id}/analyze", json={})
        generated = client.post(f"/api/v1/questions/{question_id}/variations", json={})
        fetched = client.get(f"/api/v1/questions/{question_id}/variations")

    assert generated.status_code == 502
    assert "结构无效" in generated.json()["detail"]
    assert fetched.status_code == 404


def test_variations_are_blocked_before_completed_analysis(tmp_path: Path) -> None:
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
        question_id = setup_confirmed_question(client)
        setup_provider(client)
        response = client.post(f"/api/v1/questions/{question_id}/variations", json={})

    assert response.status_code == 409
    assert called is False


def test_review_schedule_moves_to_mastered_after_three_successes(tmp_path: Path) -> None:
    client, question_id, _ = analyzed_client(tmp_path)
    try:
        schedules = [
            client.post(
                f"/api/v1/questions/{question_id}/review", json={"result": "remembered"}
            ).json()
            for _ in range(3)
        ]
        due = client.get("/api/v1/review/due")
        forgotten = client.post(
            f"/api/v1/questions/{question_id}/review", json={"result": "forgotten"}
        )
    finally:
        client.__exit__(None, None, None)

    assert [item["scheduled_days"] for item in schedules] == [1, 3, 7]
    assert schedules[-1]["mastery_status"] == "mastered"
    assert due.json() == []
    assert forgotten.json()["mastery_status"] == "reviewing"
    assert forgotten.json()["review_count"] == 0


def test_legacy_database_is_stamped_and_upgraded_without_losing_questions(
    tmp_path: Path,
) -> None:
    app = create_app(data_dir=tmp_path, secret_protector=TestProtector())
    with TestClient(app) as client:
        question_id = client.post(
            "/api/v1/questions", json={"input_type": "text", "source_text": "保留这道题"}
        ).json()["id"]

    connection = sqlite3.connect(tmp_path / "app.db")
    try:
        connection.execute("DROP TABLE review_events")
        connection.execute("DROP TABLE variation_runs")
        connection.execute("DROP TABLE question_learning")
        connection.execute("DROP TABLE alembic_version")
        connection.commit()
    finally:
        connection.close()

    upgraded_app = create_app(data_dir=tmp_path, secret_protector=TestProtector())
    with TestClient(upgraded_app) as client:
        preserved = client.get(f"/api/v1/questions/{question_id}")

    assert preserved.status_code == 200
    assert preserved.json()["source_text"] == "保留这道题"


def test_fresh_database_is_upgraded_to_latest_revision(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path, secret_protector=TestProtector())
    with TestClient(app):
        pass

    connection = sqlite3.connect(tmp_path / "app.db")
    try:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        connection.close()

    assert revision == "0002"
    assert {"question_learning", "variation_runs", "review_events"} <= tables
