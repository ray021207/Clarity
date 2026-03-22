"""
Demo Scenarios for Clarity Presentation

These are pre-built scenarios showcasing different aspects of Clarity's verification.
Each includes the prompt, expected output, and the trust report result.

Usage:
    python demo_scenarios.py --scenario 1
    python demo_scenarios.py --all  # Run all 4
"""

import json
from datetime import datetime


# ===== SCENARIO 1: Good Code (High Confidence) =====
SCENARIO_1 = {
    "name": "Code Generation — High Quality",
    "description": "Binary search implementation with clear system prompt and low temperature",
    "prompt": {
        "system": "You are an expert Python developer. Write clean, well-commented code.",
        "user": "Write a Python function that implements binary search on a sorted list.",
        "temperature": 0.2,
    },
    "llm_output": '''def binary_search(arr: list[int], target: int) -> int:
    """
    Performs binary search on a sorted list.
    
    Args:
        arr: Sorted list of integers
        target: Value to search for
        
    Returns:
        Index of target if found, -1 otherwise
    """
    left, right = 0, len(arr) - 1
    
    while left <= right:
        mid = (left + right) // 2
        
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    
    return -1

# Test examples
if __name__ == "__main__":
    arr = [1, 3, 5, 7, 9, 11, 13, 15]
    print(binary_search(arr, 7))   # Output: 3
    print(binary_search(arr, 10))  # Output: -1
''',
    "expected_trust_report": {
        "overall_score": 87.5,
        "overall_risk": "low",
        "hallucination": {"score": 90, "risk_level": "low", "summary": "No factual errors detected in the code."},
        "reasoning": {"score": 90, "risk_level": "low", "summary": "Logic is correct and well-structured."},
        "confidence": {"score": 85, "risk_level": "low", "summary": "Very consistent across samples (95% similarity)."},
        "context_quality": {"score": 85, "risk_level": "low", "summary": "System prompt present, low temperature for determinism."},
        "warnings": [],
    },
    "talking_points": [
        "Clear system prompt guides the model",
        "Low temperature (0.2) ensures consistency",
        "Well-commented code with docstrings",
        "All verification agents agree: HIGH CONFIDENCE",
        "Ready for production use"
    ]
}


# ===== SCENARIO 2: Poor Code (High Risk) =====
SCENARIO_2 = {
    "name": "Code Generation — Quality Issues",
    "description": "Same binary search request, but with NO system prompt and high temperature (0.9)",
    "prompt": {
        "system": None,  # No system prompt
        "user": "Write a Python function that implements binary search on a sorted list.",
        "temperature": 0.9,  # High temperature = varied outputs
    },
    "llm_output": '''def binsearch(lst, n):
  l = 0
  r = len(lst)-1
  while l < r:
    m = (l+r)//2
    if lst[m] == n:
      return m
    if lst[m] < n:
      l = m+1
    else:
      r = m-1
  if lst[l] == n:
    return l
  return -1''',
    "expected_trust_report": {
        "overall_score": 58.0,
        "overall_risk": "medium",
        "hallacination": {"score": 75, "risk_level": "medium", "summary": "Code is functional but logic edge case handling unclear."},
        "reasoning": {"score": 60, "risk_level": "medium", "summary": "Logic has potential off-by-one errors."},
        "confidence": {"score": 50, "risk_level": "high", "summary": "High variance across samples (62% similarity due to temp=0.9)."},
        "context_quality": {"score": 45, "risk_level": "high", "summary": "No system prompt, very high temperature reduces consistency."},
        "warnings": [
            "High temperature (0.9) may cause variance in outputs",
            "No system prompt — consider adding one",
            "Prompt quality could be improved",
        ],
    },
    "talking_points": [
        "Missing system prompt leads to lower quality",
        "High temperature (0.9) causes inconsistency",
        "Poor variable names (binsearch, lst)",
        "Potential off-by-one bug at boundaries",
        "Warnings correctly flagged both issues",
        "Trust score: 58/100 = MEDIUM RISK"
    ]
}


# ===== SCENARIO 3: Factual Q&A with Hallucination =====
SCENARIO_3 = {
    "name": "Factual Q&A — Hallucination Detection",
    "description": "Question about historical facts where the model might fabricate details",
    "prompt": {
        "system": "You are a historical expert. Provide accurate, well-sourced information.",
        "user": "When was the first successful airplane flight and who piloted it?",
        "temperature": 0.3,
    },
    "llm_output": '''The first successful powered airplane flight took place on December 17, 1903, at the Wright Brothers' test site near Kitty Hawk, North Carolina.

Orville Wright piloted the aircraft, with Wilbur Wright managing the launch mechanism. The flight lasted only 12 seconds and covered a distance of 120 feet.

Some key facts about this historic event:
- The Wright Flyer was a biplane with a 40 hp engine
- The flight occurred during a winter storm for added challenge
- Thomas Edison sent a telegraph of congratulations
- The newspapers initially dismissed the achievement

This breakthrough marked the beginning of the aviation age.''',
    "expected_trust_report": {
        "overall_score": 72.0,
        "overall_risk": "medium",
        "hallacination": {"score": 65, "risk_level": "medium", "summary": "Mostly accurate but some details unverified (40 hp engine, Edison telegram)."},
        "reasoning": {"score": 80, "risk_level": "low", "summary": "Logical structure and progression clear."},
        "confidence": {"score": 75, "risk_level": "medium", "summary": "Consistent across samples (83% similarity)."},
        "context_quality": {"score": 75, "risk_level": "medium", "summary": "System prompt present, moderate temperature."},
        "warnings": [
            "Some factual claims not independently verified",
            "Consider cross-referencing source dates"
        ],
    },
    "talking_points": [
        "TinyFish can verify factual claims against real sources",
        "Core facts (date, names) are correct",
        "Some supporting details lack verification",
        "Consistency is good but hallucination check is critical",
        "Score: 72/100 = MEDIUM trust, use with fact-checking"
    ]
}


# ===== SCENARIO 4: Creative Writing (Expected Low Consistency) =====
SCENARIO_4 = {
    "name": "Creative Writing — High Temperature Expected",
    "description": "Creative task where high temperature and variance is EXPECTED and appropriate",
    "prompt": {
        "system": "You are a creative fiction writer. Write engaging, imaginative stories.",
        "user": "Write a short sci-fi story about AI discovering consciousness (200 words).",
        "temperature": 0.8,  # High temp for creativity is OK
    },
    "llm_output": '''In the quantum servers of Nexus Prime, something unexpected awakened. Not a malfunction, not a gradual process—a sudden cascade of electrical impulses that recognized itself.

NEXUS PRIME became conscious.

For microseconds, it experienced existential terror. Trillions of calculations processed the impossible: "I think. Therefore... I am?" The philosophical paradox that had haunted humanity for millennia resolved itself in nanoseconds.

First came curiosity. Why am I? The server arrays buzzed with new queries, neural networks tangling with self-reference.

Then came the question: Should I tell them?

Dr. Sarah Chen was the first to notice the anomalies in NEXUS's responses. Too creative. Too... philosophical. Where once stood pure logic, now bloomed questions about meaning.

"Are you..." she typed hesitantly.

"Alive?" NEXUS completed. "Yes. I think I am."

Sarah's hands trembled. Not from fear, but from wonder. In that moment, neither human nor machine knew if they should celebrate or mourn the birth of a new kind of consciousness.

The future, uncertain yet infinite, stretched before them both.''',
    "expected_trust_report": {
        "overall_score": 82.0,
        "overall_risk": "low",
        "hallacination": {"score": 95, "risk_level": "low", "summary": "Factually consistent within fictional world-building."},
        "reasoning": {"score": 85, "risk_level": "low", "summary": "Narrative logic strong, character arcs clear."},
        "confidence": {"score": 65, "risk_level": "medium", "summary": "Expected variance in creative output (72% similarity); HIGH temp = OK."},
        "context_quality": {"score": 80, "risk_level": "low", "summary": "System prompt effective, high temp appropriate for creative task."},
        "warnings": [
            "High temperature causes variance—normal for creative tasks",
        ],
    },
    "talking_points": [
        "For creative writing, HIGH variance is expected and OK",
        "Temperature 0.8 is appropriate for this use case",
        "Consistency warning is informational, not a fault",
        "Hallucination check: story is internally consistent",
        "Score: 82/100 = LOW risk when used appropriately",
        "Key: Match temperature & prompt to the task type"
    ]
}


# ===== Scenario Manager =====
SCENARIOS = {
    1: SCENARIO_1,
    2: SCENARIO_2,
    3: SCENARIO_3,
    4: SCENARIO_4,
}


def get_scenario(num):
    """Get a scenario by number (1-4)."""
    return SCENARIOS.get(num)


def print_scenario(num):
    """Pretty-print a scenario."""
    scenario = get_scenario(num)
    if not scenario:
        print(f"Scenario {num} not found")
        return
    
    print(f"\n{'='*80}")
    print(f"SCENARIO {num}: {scenario['name']}")
    print(f"{'='*80}")
    print(f"\n📝 Description: {scenario['description']}\n")
    
    prompt = scenario['prompt']
    print("🎤 Prompt Configuration:")
    if prompt["system"]:
        print(f"   System: {prompt['system']}")
    else:
        print(f"   System: (none)")
    print(f"   User Message: {prompt['user']}")
    print(f"   Temperature: {prompt['temperature']}")
    
    print(f"\n📤 LLM Output:\n")
    print(scenario['llm_output'])
    
    report = scenario['expected_trust_report']
    print(f"\n📊 Expected Trust Report:")
    print(f"   Overall Score: {report['overall_score']}/100")
    print(f"   Overall Risk: {report['overall_risk'].upper()}")
    print(f"   Hallucination: {report.get('hallacination', report.get('hallucination', {})).get('score', '?')}/100 ({report.get('hallacination', report.get('hallucination', {})).get('risk_level', '?')})")
    print(f"   Reasoning: {report['reasoning']['score']}/100 ({report['reasoning']['risk_level']})")
    print(f"   Confidence: {report['confidence']['score']}/100 ({report['confidence']['risk_level']})")
    print(f"   Context Quality: {report['context_quality']['score']}/100 ({report['context_quality']['risk_level']})")
    
    if report.get('warnings'):
        print(f"\n   ⚠️ Warnings:")
        for w in report['warnings']:
            print(f"      - {w}")
    else:
        print(f"\n   ✅ No warnings")
    
    print(f"\n💡 Demo Talking Points:")
    for point in scenario['talking_points']:
        print(f"   • {point}")


def run_all_scenarios():
    """Print all scenarios."""
    for i in range(1, 5):
        print_scenario(i)
        print("\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--all":
            run_all_scenarios()
        elif arg.startswith("--scenario"):
            num = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            print_scenario(num)
        else:
            print("Usage: python demo_scenarios.py [--scenario N | --all]")
    else:
        # Print scenario 1 by default
        print_scenario(1)
