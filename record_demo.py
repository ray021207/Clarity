"""
Automated demo script for Clarity video recording.
Run this while recording your screen + narrating the voiceover.
Includes timing markers and feature demonstrations.
"""

import asyncio
import time
import json
from datetime import datetime
import httpx
import subprocess
import sys

# Demo configuration
DEMO_STEPS = [
    {
        "time": "0:00-0:30",
        "title": "INTRO",
        "narration": "Meet Clarity: An AI Output Verification Layer. Today I'll show you how to ensure your LLM outputs are trustworthy, accurate, and well-reasoned.",
        "action": "Show dashboard at http://localhost:8000",
        "duration": 30,
    },
    {
        "time": "0:30-1:30",
        "title": "DASHBOARD OVERVIEW",
        "narration": "Here's our clean, dark-themed dashboard. Built with FastAPI, LangGraph, and modern web technologies. You input your LLM prompt and response, and Clarity analyzes it in real-time.",
        "action": "Point to input fields, explain layout",
        "duration": 60,
    },
    {
        "time": "1:30-2:00",
        "title": "FILL TEST DATA",
        "narration": "Let me fill in an example. Here's a system prompt asking for accurate code, a user request, and Claude's response about calculating factorial.",
        "action": "Fill example code verification scenario",
        "duration": 30,
    },
    {
        "time": "2:00-2:30",
        "title": "CLICK VERIFY",
        "narration": "Now I'll click Verify. Behind the scenes, Clarity captures the request, passes it through our interceptor, and routes it to our verification pipeline.",
        "action": "Click Verify button, show loading",
        "duration": 30,
    },
    {
        "time": "2:30-3:30",
        "title": "WAIT FOR RESULTS",
        "narration": "While it processes, let me explain what's happening. Our backend calls Claude via the Anthropic SDK, captures all metadata, then passes it through 4 specialized verification agents.",
        "action": "Wait for agent results, show score appearing",
        "duration": 60,
    },
    {
        "time": "3:30-4:30",
        "title": "HALLUCINATION DETECTOR",
        "narration": "First agent: Hallucination Detector. It checks for factual errors, inconsistencies, and made-up claims. This code gets 85/100 because it's factually correct.",
        "action": "Highlight hallucination agent card",
        "duration": 60,
    },
    {
        "time": "4:30-5:15",
        "title": "REASONING VALIDATOR",
        "narration": "Second: Reasoning Validator. It ensures the logical flow is sound, steps follow from premises, and conclusions are justified. Score: 90/100.",
        "action": "Highlight reasoning agent card",
        "duration": 45,
    },
    {
        "time": "5:15-6:00",
        "title": "CONFIDENCE CALIBRATOR",
        "narration": "Third: Confidence Calibrator. It checks if the model's certainty matches actual correctness. Sometimes models express high confidence in incorrect answers. Score: 75/100.",
        "action": "Highlight confidence agent card",
        "duration": 45,
    },
    {
        "time": "6:00-6:45",
        "title": "CONTEXT ANALYZER",
        "narration": "Fourth: Context Analyzer. It evaluates the effectiveness of your system prompt and provides feedback on how to improve your LLM instructions. Score: 88/100.",
        "action": "Highlight context analyzer agent card",
        "duration": 45,
    },
    {
        "time": "6:45-7:30",
        "title": "OVERALL SCORE",
        "narration": "Combining all four agents with weighted scoring: Hallucination 30%, Reasoning 25%, Confidence 25%, Context 20%. Overall trust score: 82 out of 100. Risk level: LOW.",
        "action": "Show overall score ring, risk badge",
        "duration": 45,
    },
    {
        "time": "7:30-8:15",
        "title": "DETAILED FINDINGS",
        "narration": "Scroll down to see findings from each agent. Every detection includes specific evidence and suggestions for improvement.",
        "action": "Scroll to show agent findings, warnings",
        "duration": 45,
    },
    {
        "time": "8:15-8:45",
        "title": "DATABASE PERSISTENCE",
        "narration": "Every report is automatically stored in our InsForge PostgreSQL database. You can retrieve reports by ID, list historical reports, and filter by risk level.",
        "action": "Show database info, reports list endpoint",
        "duration": 30,
    },
    {
        "time": "8:45-9:15",
        "title": "TECHNICAL ARCHITECTURE",
        "narration": "Built with production-ready tech: FastAPI backend, LangGraph agents, PostgreSQL persistence, Anthropic Claude API, and a modern React dashboard.",
        "action": "Show code structure in VS Code or GitHub",
        "duration": 30,
    },
    {
        "time": "9:15-9:45",
        "title": "USE CASES",
        "narration": "Use case 1: Enterprise teams vetting AI outputs before release. Use case 2: Research validating model consistency. Use case 3: Development catching hallucinations during testing.",
        "action": "Show use case scenarios",
        "duration": 30,
    },
    {
        "time": "9:45-10:00",
        "title": "CALL TO ACTION",
        "narration": "Clarity makes AI outputs explainable, verifiable, and trustworthy. Check us out on GitHub. Thanks for watching!",
        "action": "Show GitHub repo, documentation links",
        "duration": 15,
    },
]

TEST_DATA = {
    "system": "You are a helpful coding assistant. Provide accurate, working Python code with clear explanations.",
    "user_message": "Write a Python function to calculate the factorial of a number",
    "response": """def factorial(n):
    '''
    Calculate the factorial of n.
    
    Args:
        n: A non-negative integer
        
    Returns:
        The factorial of n
    '''
    if n < 0:
        raise ValueError("Input must be non-negative")
    if n == 0 or n == 1:
        return 1
    return n * factorial(n - 1)

# Test the function
print(f"5! = {factorial(5)}")      # Output: 120
print(f"0! = {factorial(0)}")      # Output: 1
print(f"10! = {factorial(10)}")    # Output: 3628800
"""
}

def print_header():
    """Print demo header."""
    print("\n" + "="*70)
    print("  CLARITY DEMO - AUTOMATED RECORDING GUIDE")
    print("="*70)
    print("\n📹 INSTRUCTIONS:")
    print("  1. Start screen recording NOW (OBS, Zoom, QuickTime, etc.)")
    print("  2. Open http://localhost:8000 in a browser")
    print("  3. Keep this terminal visible for timing cues")
    print("  4. Follow the narration guide below")
    print("  5. Record your voiceover while this script runs")
    print("\n⏱️  DEMO TIMING: 10 minutes total\n")

def print_step(step, elapsed):
    """Print a demo step."""
    print(f"\n{'─'*70}")
    print(f"⏱️  [{step['time']}] {step['title']}")
    print(f"{'─'*70}")
    print(f"\n📝 NARRATION:")
    print(f"   {step['narration']}")
    print(f"\n✋ ACTION:")
    print(f"   {step['action']}")
    print(f"\n⏳ Hold for: {step['duration']} seconds")

async def verify_server():
    """Check if server is running."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/api/v1/health", timeout=2)
            return response.status_code == 200
    except:
        return False

async def run_demo_flow():
    """Run through demo flow with timing."""
    
    print_header()
    
    # Check server
    print("🔍 Checking server...")
    server_ok = await verify_server()
    if not server_ok:
        print("❌ Server not running at localhost:8000")
        print("   Start it first: python -m clarity.main")
        sys.exit(1)
    print("✅ Server is running!")
    
    print("\n⏱️ Demo starts in 5 seconds...")
    print("   Press Ctrl+C to stop anytime")
    time.sleep(5)
    
    start_time = time.time()
    
    for i, step in enumerate(DEMO_STEPS):
        print_step(step, time.time() - start_time)
        
        # Count down the step duration
        for remaining in range(step["duration"], 0, -5):
            time.sleep(min(5, remaining))
            elapsed = int(time.time() - start_time)
            minutes = elapsed // 60
            seconds = elapsed % 60
            print(f"\r  ⏱️  {minutes}:{seconds:02d} elapsed | {remaining}s remaining", end="")
        
        print()  # New line after countdown
    
    total_time = time.time() - start_time
    minutes = int(total_time) // 60
    seconds = int(total_time) % 60
    
    print("\n" + "="*70)
    print(f"✅ DEMO COMPLETE! Total time: {minutes}:{seconds:02d}")
    print("="*70)
    print("\n📹 NEXT STEPS:")
    print("  1. Stop your screen recording")
    print("  2. Edit video in your favorite editor (Premiere, DaVinci, etc.)")
    print("  3. Add intro/outro music")
    print("  4. Add captions/text overlays if desired")
    print("  5. Export and share!")
    print("\n💡 TIPS:")
    print("  • If you made mistakes, restart the demo and record again")
    print("  • You can pause and resume recording anytime")
    print("  • Zoom in on important details during recording")
    print("  • Use your cursor to point at key elements")

if __name__ == "__main__":
    try:
        asyncio.run(run_demo_flow())
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo stopped by user")
        sys.exit(0)
