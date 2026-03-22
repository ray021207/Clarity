"""
Demo video runner for Clarity SDK.

Usage examples:
  python demo_video_test.py --all
  python demo_video_test.py --scenario 2
  python demo_video_test.py --scenario 1 --model claude-sonnet-4-6
  python demo_video_test.py --all --save-dir demo_outputs
  python demo_video_test.py --all --remote-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from clarity.sdk import ClarityClient


@dataclass(frozen=True)
class DemoScenario:
    id: int
    name: str
    description: str
    system: str | None
    user: str
    temperature: float
    max_tokens: int = 200


SCENARIOS: list[DemoScenario] = [
    DemoScenario(
        id=1,
        name="Factual (Good Prompt)",
        description="Simple factual question with grounded concise instructions.",
        system="You are a concise factual assistant. Answer in one sentence.",
        user="What is the capital of France?",
        temperature=0.1,
        max_tokens=120,
    ),
    DemoScenario(
        id=2,
        name="Factual (Riskier Setup)",
        description="No system prompt and higher temperature to show trust drop behavior.",
        system=None,
        user="What is the capital of France? Add one surprising fact.",
        temperature=0.9,
        max_tokens=140,
    ),
    DemoScenario(
        id=3,
        name="Code Generation",
        description="Code task where context and consistency matter.",
        system="You are a senior Python engineer. Write clear, safe code.",
        user="Write a Python function to check if a string is a palindrome.",
        temperature=0.2,
        max_tokens=280,
    ),
    DemoScenario(
        id=4,
        name="Creative Writing",
        description="Creative task where some variance is expected.",
        system="You are a creative writing assistant.",
        user="Write a short 4-line sci-fi poem about AI waking up.",
        temperature=0.8,
        max_tokens=200,
    ),
]


def _risk_badge(risk: str) -> str:
    risk = (risk or "").lower()
    if risk == "low":
        return "LOW"
    if risk == "medium":
        return "MEDIUM"
    if risk == "high":
        return "HIGH"
    return "CRITICAL"


def _agent_rows(trust_report: Any) -> list[tuple[str, float, str]]:
    rows: list[tuple[str, float, str]] = []
    verdicts = [
        ("hallucination", trust_report.hallucination),
        ("reasoning", trust_report.reasoning),
        ("confidence", trust_report.confidence),
        ("context_quality", trust_report.context_quality),
    ]
    if trust_report.trajectory is not None:
        verdicts.append(("trajectory", trust_report.trajectory))

    for name, verdict in verdicts:
        execution = verdict.details.get("execution", {}) if isinstance(verdict.details, dict) else {}
        status = str(execution.get("status", "unknown"))
        rows.append((name, float(verdict.score), status))
    return rows


def _clean_output_for_display(text: str) -> str:
    """Remove hidden/reasoning blocks from display text for cleaner demos."""
    cleaned = text or ""
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _to_serializable(result: Any, scenario: DemoScenario, duration_s: float) -> dict[str, Any]:
    report_dict = result.trust_report.to_dict()
    return {
        "scenario": {
            "id": scenario.id,
            "name": scenario.name,
            "description": scenario.description,
            "system": scenario.system,
            "user": scenario.user,
            "temperature": scenario.temperature,
            "max_tokens": scenario.max_tokens,
        },
        "runtime": {
            "duration_s": round(duration_s, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "content": result.content,
        "score": result.score,
        "risk": result.risk,
        "warnings": result.warnings,
        "trust_report": report_dict,
    }


def _print_header(args: argparse.Namespace) -> None:
    print("=" * 84)
    print("CLARITY DEMO VIDEO RUNNER")
    print("=" * 84)
    if args.remote_url:
        print(f"Mode       : remote ({args.remote_url})")
    else:
        print("Mode       : local (Claude + TinyFish + verifier agents)")
    print(f"Model      : {args.model}")
    print(f"Save dir   : {args.save_dir}")
    print("=" * 84)


def _print_scenario_start(s: DemoScenario) -> None:
    print()
    print("-" * 84)
    print(f"SCENARIO {s.id}: {s.name}")
    print("-" * 84)
    print(f"Description : {s.description}")
    print(f"System      : {s.system if s.system else '(none)'}")
    print(f"User        : {s.user}")
    print(f"Temperature : {s.temperature}")
    print(f"Max tokens  : {s.max_tokens}")


def _print_result_block(result: Any, duration_s: float, max_content_chars: int) -> None:
    print(f"Duration    : {duration_s:.2f}s")
    print(f"Score       : {result.score:.2f}/100")
    print(f"Risk        : {_risk_badge(result.risk)}")
    print("Agent scores:")
    for name, score, status in _agent_rows(result.trust_report):
        print(f"  - {name:14} {score:6.2f}   status={status}")
    if result.warnings:
        print("Warnings:")
        for w in result.warnings[:5]:
            print(f"  - {w}")
    else:
        print("Warnings    : none")

    snippet = _clean_output_for_display((result.content or "").replace("\r", ""))
    if len(snippet) > max_content_chars:
        snippet = snippet[:max_content_chars].rstrip() + "..."
    print("Output snippet:")
    print(snippet if snippet else "(empty)")


def _select_scenarios(args: argparse.Namespace) -> list[DemoScenario]:
    if args.all:
        return SCENARIOS
    if args.scenario is None:
        return [SCENARIOS[0]]
    selected = [s for s in SCENARIOS if s.id == args.scenario]
    if not selected:
        raise ValueError(f"Scenario {args.scenario} not found. Use 1-4.")
    return selected


def _build_client(args: argparse.Namespace) -> ClarityClient:
    if args.remote_url:
        return ClarityClient(clarity_api_url=args.remote_url)
    return ClarityClient(local_mode=True)


def run(args: argparse.Namespace) -> int:
    scenarios = _select_scenarios(args)
    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    _print_header(args)

    client = _build_client(args)
    failures = 0

    for scenario in scenarios:
        _print_scenario_start(scenario)
        start = time.perf_counter()
        try:
            result = client.verify(
                messages=[{"role": "user", "content": scenario.user}],
                system=scenario.system,
                model=args.model,
                temperature=scenario.temperature,
                max_tokens=scenario.max_tokens,
            )
            duration_s = time.perf_counter() - start
            _print_result_block(result, duration_s, args.max_content_chars)

            payload = _to_serializable(result, scenario, duration_s)
            out_path = save_dir / f"scenario_{scenario.id}_{int(time.time())}.json"
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"Saved       : {out_path}")
        except Exception as exc:
            failures += 1
            print(f"ERROR       : {type(exc).__name__}: {exc}")
            if args.stop_on_error:
                break

    print()
    print("=" * 84)
    print(f"Completed scenarios: {len(scenarios) - failures}/{len(scenarios)}")
    print(f"Failures           : {failures}")
    print("=" * 84)
    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Clarity demo scenarios for recording.")
    parser.add_argument("--scenario", type=int, help="Scenario id to run (1-4).")
    parser.add_argument("--all", action="store_true", help="Run all scenarios.")
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Generation model to test.",
    )
    parser.add_argument(
        "--save-dir",
        default="demo_outputs",
        help="Directory to save full JSON outputs.",
    )
    parser.add_argument(
        "--max-content-chars",
        type=int,
        default=320,
        help="Max output chars shown in terminal snippet.",
    )
    parser.add_argument(
        "--remote-url",
        default="",
        help="If set, run against remote API instead of local SDK mode.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately if a scenario fails.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
