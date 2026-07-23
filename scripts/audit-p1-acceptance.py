"""P1 real-provider acceptance through public APIs only; never reads or prints an API key."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:3002/api/v1"
OUTPUT = ROOT / "docs" / "v1-p1-acceptance.json"
VARIANT_TYPES = ["same_point", "new_context", "challenge"]

ORIGINALS = [
    {
        "name": "抛物线面积最值图片题",
        "question_id": "241df39e-40c9-496f-9851-456ebe5b90d2",
    },
    {
        "name": "绝对值方程 |2x-3|=5",
        "question_id": "5fad8eb1-2f78-4a02-836c-9421059de6ca",
    },
    {
        "name": "6V、12Ω灯泡题",
        "question_id": "2c95f40b-e535-42b7-a199-48fbe07bbf59",
    },
]

BLIND_CASES = [
    {
        "name": "新代数题：二元一次方程组",
        "existing_question_id": "74741d18-276d-4f64-835d-85f4a3de703d",
        "text": "解方程组：2x+y=7，x-y=2。",
        "subject": "初中数学",
        "grade": "七年级",
        "user_answer": "x=2，y=3",
        "user_solution": "把两个方程直接相加后计算错误。",
        "reason": "calculation",
        "note": "消元计算出错",
    },
    {
        "name": "新坐标几何题：三角形面积与中点",
        "existing_question_id": "e802a6a2-2e7e-49f4-9b48-a4ae4819e1ec",
        "text": (
            "在平面直角坐标系xOy中，已知A(-3,1)、B(5,1)、C(1,4)。"
            "（1）求线段AB的中点M的坐标；（2）求△ABC的面积。"
        ),
        "subject": "初中数学",
        "grade": "八年级",
        "user_answer": "M(1,1)，面积为24",
        "user_solution": "底边取AB，高误用了点C到原点的距离。",
        "reason": "method",
        "note": "三角形的高判断错误",
    },
    {
        "name": "新物理题：功和功率",
        "existing_question_id": "5ff50665-53a1-49d4-86f9-e5d0d553c08e",
        "text": ("用30 N的水平拉力使物体沿水平面匀速前进8 m，用时4 s。求拉力做的功和拉力的功率。"),
        "subject": "初中物理",
        "grade": "九年级",
        "user_answer": "功为120 J，功率为30 W",
        "user_solution": "使用W=Fs和P=W/t，但乘法计算错误。",
        "reason": "calculation",
        "note": "功的计算错误",
    },
]


def response_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:1000]
    return str(body.get("detail", body))


def assert_variations(body: dict[str, object]) -> None:
    variants = body.get("variants")
    if not isinstance(variants, list) or len(variants) != 3:
        raise AssertionError("成功响应没有三道变式题")
    if [item.get("type") for item in variants] != VARIANT_TYPES:
        raise AssertionError("三类变式题类型或顺序错误")
    for item in variants:
        for field in ("question", "answer", "solution"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise AssertionError(f"变式题缺少 {field}")


def generate_once(
    client: httpx.Client,
    question_id: str,
    run_number: int,
) -> dict[str, object]:
    started = time.perf_counter()
    try:
        response = client.post(f"{BASE}/questions/{question_id}/variations", json={})
    except httpx.RequestError as exc:
        return {
            "run": run_number,
            "http_status": 0,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "success": False,
            "failure": f"审计客户端请求失败：{type(exc).__name__}: {exc}",
        }
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    record: dict[str, object] = {
        "run": run_number,
        "http_status": response.status_code,
        "elapsed_ms": elapsed_ms,
    }
    if response.status_code == 200:
        body = response.json()
        assert_variations(body)
        record.update(
            {
                "success": True,
                "variation_run_id": body["id"],
                "model": body["model_name"],
                "provider_duration_ms": body["duration_ms"],
                "prompt_version": body["prompt_version"],
                "schema_version": body["schema_version"],
                "variants": body["variants"],
            }
        )
    else:
        record.update({"success": False, "failure": response_detail(response)})
    return record


def create_blind_case(client: httpx.Client, case: dict[str, str]) -> dict[str, object]:
    existing_question_id = case.get("existing_question_id")
    if existing_question_id:
        question_id = existing_question_id
        confirmed = client.get(f"{BASE}/questions/{question_id}/confirmation")
        confirmed.raise_for_status()
        analyzed = client.get(f"{BASE}/questions/{question_id}/analysis")
        analyzed.raise_for_status()
        analysis_elapsed_ms = 0
        created_now = False
    else:
        created = client.post(
            f"{BASE}/questions",
            json={"input_type": "text", "source_text": case["text"]},
        )
        created.raise_for_status()
        question_id = created.json()["id"]
        confirmed = client.post(
            f"{BASE}/questions/{question_id}/confirm",
            json={
                "confirmed_text": case["text"],
                "subject": case["subject"],
                "grade": case["grade"],
                "user_answer": case["user_answer"],
                "user_solution": case["user_solution"],
                "acknowledge_complete": True,
            },
        )
        confirmed.raise_for_status()
        analysis_started = time.perf_counter()
        analyzed = client.post(f"{BASE}/questions/{question_id}/analyze", json={})
        analysis_elapsed_ms = round((time.perf_counter() - analysis_started) * 1000)
        analyzed.raise_for_status()
        created_now = True
    analysis = analyzed.json()

    learned = client.put(
        f"{BASE}/questions/{question_id}/learning",
        json={"actual_error_reason": case["reason"], "actual_error_note": case["note"]},
    )
    learned.raise_for_status()

    variation = generate_once(client, question_id, 1)
    review = client.post(
        f"{BASE}/questions/{question_id}/review",
        json={"result": "remembered"},
    )
    review.raise_for_status()
    notebook = client.get(f"{BASE}/notebook")
    notebook.raise_for_status()
    in_notebook = any(item["question_id"] == question_id for item in notebook.json()["items"])

    return {
        "name": case["name"],
        "question_id": question_id,
        "created_in_this_run": created_now,
        "first_seen_as_blind_case_in": "docs/v1-p1-acceptance-round1.json",
        "confirmed": confirmed.status_code == 200,
        "analysis": {
            "status": analysis["status"],
            "model": analysis["model_name"],
            "elapsed_ms": analysis_elapsed_ms,
            "final_answer": analysis["final_answer"],
            "knowledge_points": analysis["knowledge_points"],
            "solution_steps": analysis["solution_steps"],
        },
        "learning_saved": learned.json()["actual_error_reason"] == case["reason"],
        "in_notebook": in_notebook,
        "variation": variation,
        "review": {
            "mastery_status": review.json()["mastery_status"],
            "scheduled_days": review.json()["scheduled_days"],
        },
    }


def main() -> None:
    evidence: dict[str, object] = {
        "started_at": datetime.now(UTC).isoformat(),
        "base_url": BASE,
        "policy": "public APIs only; no database edits; real configured provider",
        "original_nine_runs": [],
        "blind_cases": [],
    }
    with httpx.Client(timeout=900) as client:
        health = client.get(f"{BASE}/health")
        health.raise_for_status()
        evidence["health"] = health.json()

        original_results: list[dict[str, object]] = []
        for case in ORIGINALS:
            case_result = {**case, "runs": [], "success_count": 0}
            original_results.append(case_result)
            for index in range(1, 4):
                case_result["runs"].append(generate_once(client, case["question_id"], index))
                case_result["success_count"] = sum(
                    bool(item["success"]) for item in case_result["runs"]
                )
                evidence["original_nine_runs"] = original_results
                OUTPUT.write_text(
                    json.dumps(evidence, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        evidence["original_nine_runs"] = original_results

        blind_results: list[dict[str, object]] = []
        for case in BLIND_CASES:
            blind_results.append(create_blind_case(client, case))
            evidence["blind_cases"] = blind_results
            OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    all_original_runs = [run for case in evidence["original_nine_runs"] for run in case["runs"]]
    evidence["summary"] = {
        "original_successes": sum(bool(item["success"]) for item in all_original_runs),
        "original_total": len(all_original_runs),
        "each_original_at_least_two": all(
            case["success_count"] >= 2 for case in evidence["original_nine_runs"]
        ),
        "blind_successes": sum(
            bool(case["variation"]["success"]) for case in evidence["blind_cases"]
        ),
        "blind_total": len(evidence["blind_cases"]),
    }
    evidence["finished_at"] = datetime.now(UTC).isoformat()
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence["summary"], ensure_ascii=False, indent=2))
    print(OUTPUT)


if __name__ == "__main__":
    main()
