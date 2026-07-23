"""Real local-API MVP audit. Uses the configured provider but never reads or prints its key."""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:3002/api/v1"
EVIDENCE = ROOT / "docs" / "audit-evidence-v1.json"


def call(client: httpx.Client, method: str, path: str, **kwargs: object) -> dict:
    response = client.request(method, f"{BASE}{path}", **kwargs)
    if response.is_error:
        raise RuntimeError(f"{method} {path}: HTTP {response.status_code} {response.text}")
    return response.json()


def confirm(client: httpx.Client, question_id: str, **fields: object) -> dict:
    return call(
        client,
        "POST",
        f"/questions/{question_id}/confirm",
        json={**fields, "acknowledge_complete": True},
    )


def variations_with_retry(client: httpx.Client, question_id: str) -> tuple[dict | None, list[str]]:
    failures: list[str] = []
    for _ in range(3):
        response = client.post(f"{BASE}/questions/{question_id}/variations", json={})
        if response.status_code == 200:
            return response.json(), failures
        failures.append(f"HTTP {response.status_code}: {response.json().get('detail')}")
    return None, failures


def summarize(
    question_id: str,
    analysis: dict,
    variations: dict | None,
    failures: list[str],
) -> dict:
    variation_summary = (
        {
            "run_id": variations["id"],
            "model": variations["model_name"],
            "duration_ms": variations["duration_ms"],
            "types": [item["type"] for item in variations["variants"]],
            "items": variations["variants"],
            "failed_attempts_before_success": failures,
        }
        if variations is not None
        else {
            "run_id": None,
            "types": [],
            "items": [],
            "failed_attempts_before_success": failures,
        }
    )
    return {
        "question_id": question_id,
        "analysis": {
            "status": analysis["status"],
            "model": analysis["model_name"],
            "duration_ms": analysis["duration_ms"],
            "subject": analysis["subject"],
            "grade": analysis["grade"],
            "knowledge_points": analysis["knowledge_points"],
            "final_answer": analysis["final_answer"],
            "steps": len(analysis["solution_steps"]),
            "possible_mistakes": len(analysis["possible_mistakes"]),
            "memory_tip": analysis["memory_tip"],
            "next_time_checklist": analysis["next_time_checklist"],
            "verification": analysis["verification"],
        },
        "variations": variation_summary,
    }


def main() -> None:
    evidence: dict[str, object] = {
        "started_at": datetime.now(UTC).isoformat(),
        "base_url": BASE,
        "questions": [],
    }
    with httpx.Client(timeout=420) as client:
        evidence["health"] = call(client, "GET", "/health")
        providers = call(client, "GET", "/providers")
        evidence["providers"] = [
            {
                key: provider[key]
                for key in (
                    "capability",
                    "provider_type",
                    "display_name",
                    "base_url",
                    "model_name",
                    "timeout_seconds",
                    "has_api_key",
                )
            }
            for provider in providers
        ]
        evidence["connection_tests"] = [
            {
                "capability": provider["capability"],
                **call(client, "POST", f"/providers/{provider['id']}/test"),
            }
            for provider in providers
        ]

        corrected_text = (
            "在平面直角坐标系 xOy 中，抛物线 y=ax²+bx+c 与 x 轴交于 "
            "A(-1,0)、B(3,0)，与 y 轴交于 C(0,3)。"
            "（1）求抛物线解析式；（2）点 P 是抛物线弧 BC 上的动点，"
            "求△PBC面积的最大值及此时点P的坐标。"
        )
        connection = sqlite3.connect(ROOT / "data" / "app.db")
        row = connection.execute(
            "SELECT relative_path, original_filename, mime_type FROM question_assets "
            "ORDER BY created_at LIMIT 1"
        ).fetchone()
        existing = connection.execute(
            "SELECT question_id FROM question_confirmations WHERE confirmed_text = ? "
            "ORDER BY confirmed_at DESC LIMIT 1",
            (corrected_text,),
        ).fetchone()
        connection.close()
        if row is None:
            raise RuntimeError("No source image is available for the real image-flow audit")

        if existing:
            image_question = call(client, "GET", f"/questions/{existing[0]}")
            recognition = call(client, "GET", f"/questions/{existing[0]}/recognition")
            confirmation = call(client, "GET", f"/questions/{existing[0]}/confirmation")
            image_analysis = call(client, "GET", f"/questions/{existing[0]}/analysis")
            connection = sqlite3.connect(ROOT / "data" / "app.db")
            image_failures = [
                f"stored failed run: {error_code}"
                for (error_code,) in connection.execute(
                    "SELECT error_code FROM variation_runs "
                    "WHERE question_id = ? AND status = 'failed' ORDER BY created_at",
                    (existing[0],),
                )
            ]
            connection.close()
            image_variations = None
        else:
            image_path = ROOT / "data" / row[0]
            image_question = call(client, "POST", "/questions", json={"input_type": "image"})
            with image_path.open("rb") as source:
                call(
                    client,
                    "POST",
                    f"/questions/{image_question['id']}/image",
                    files={"file": (row[1], source, row[2])},
                )
            recognition = call(
                client, "POST", f"/questions/{image_question['id']}/recognize", json={}
            )
            confirmation = confirm(
                client,
                image_question["id"],
                confirmed_text=corrected_text,
                subject="初中数学",
                grade="九年级",
                user_answer="y=-x²+2x+3，最大面积为10",
                user_solution="用交点式求解析式；面积最大值直接取顶点。",
            )
            image_analysis = call(
                client, "POST", f"/questions/{image_question['id']}/analyze", json={}
            )
            call(
                client,
                "PUT",
                f"/questions/{image_question['id']}/learning",
                json={
                    "actual_error_reason": "method",
                    "actual_error_note": "没有把面积写成函数",
                },
            )
            image_variations, image_failures = variations_with_retry(client, image_question["id"])
        image_summary = summarize(
            image_question["id"], image_analysis, image_variations, image_failures
        )
        image_summary["input"] = {
            "type": "image",
            "recognition_model": recognition["model_name"],
            "recognition_confidence": recognition["confidence"],
            "recognition_duration_ms": recognition["duration_ms"],
            "ocr_was_manually_changed": recognition["recognized_text"].strip()
            != confirmation["confirmed_text"].strip(),
            "confirmed_text_hash": confirmation["confirmed_text_hash"],
            "student_answer_supplied": True,
            "student_solution_supplied": True,
        }
        evidence["questions"].append(image_summary)

        text_cases = [
            {
                "text": "解方程：|2x-3|=5。",
                "subject": "初中数学",
                "grade": "八年级",
                "user_answer": "x=4",
                "user_solution": "去掉绝对值，得到2x-3=5。",
                "reason": "concept",
                "note": "漏掉绝对值内为负数的情况",
            },
            {
                "text": (
                    "一只标有“6 V”的小灯泡正常发光时电阻为12 Ω。求小灯泡正常发光时的电流和电功率。"
                ),
                "subject": "初中物理",
                "grade": "九年级",
                "user_answer": "电流0.2 A，功率1.2 W",
                "user_solution": "使用I=U/R和P=UI计算。",
                "reason": "calculation",
                "note": "除法计算错误",
            },
        ]
        text_ids: list[str] = []
        for case in text_cases:
            created = call(
                client,
                "POST",
                "/questions",
                json={"input_type": "text", "source_text": case["text"]},
            )
            text_ids.append(created["id"])
            confirm(
                client,
                created["id"],
                confirmed_text=case["text"],
                subject=case["subject"],
                grade=case["grade"],
                user_answer=case["user_answer"],
                user_solution=case["user_solution"],
            )
            analysis = call(client, "POST", f"/questions/{created['id']}/analyze", json={})
            call(
                client,
                "PUT",
                f"/questions/{created['id']}/learning",
                json={"actual_error_reason": case["reason"], "actual_error_note": case["note"]},
            )
            variations, failures = variations_with_retry(client, created["id"])
            summary = summarize(created["id"], analysis, variations, failures)
            summary["input"] = {
                "type": "text",
                "student_answer_supplied": True,
                "student_solution_supplied": True,
            }
            evidence["questions"].append(summary)

        successful_text = next(
            (
                item
                for item in evidence["questions"]
                if item["input"]["type"] == "text" and item["variations"]["run_id"]
            ),
            None,
        )
        if successful_text is not None:
            target_id = successful_text["question_id"]
            before = call(client, "GET", f"/questions/{target_id}/variations")
            regenerated, regeneration_failures = variations_with_retry(client, target_id)
            before_questions = [item["question"] for item in before["variants"]]
            after_questions = (
                [item["question"] for item in regenerated["variants"]]
                if regenerated is not None
                else []
            )
            evidence["regeneration"] = {
                "question_id": target_id,
                "before_run_id": before["id"],
                "after_run_id": regenerated["id"] if regenerated else None,
                "different_run": bool(regenerated and before["id"] != regenerated["id"]),
                "different_questions": bool(regenerated and before_questions != after_questions),
                "same_positions": (
                    sum(
                        left == right
                        for left, right in zip(before_questions, after_questions, strict=True)
                    )
                    if regenerated
                    else None
                ),
                "failed_attempts_before_success": regeneration_failures,
            }
        else:
            evidence["regeneration"] = {
                "question_id": None,
                "different_run": False,
                "different_questions": False,
                "reason": "三道题均未生成通过二次验算的变式题",
            }

        notebook = call(client, "GET", "/notebook")
        evidence["persistence_before_restart"] = {
            "question_ids": [item["question_id"] for item in notebook["items"]],
            "audit_ids": [image_question["id"], *text_ids],
            "all_audit_questions_in_notebook": all(
                question_id in {item["question_id"] for item in notebook["items"]}
                for question_id in [image_question["id"], *text_ids]
            ),
        }
    evidence["finished_at"] = datetime.now(UTC).isoformat()
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "evidence": str(EVIDENCE),
                "question_ids": [item["question_id"] for item in evidence["questions"]],
                "regeneration": evidence["regeneration"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    started = time.perf_counter()
    try:
        main()
    finally:
        print(f"elapsed_seconds={time.perf_counter() - started:.1f}")
