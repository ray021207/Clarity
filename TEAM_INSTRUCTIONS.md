"""
CLARITY TEAM — CODE INTEGRATION GUIDE

This guide explains how Person B and Person C should push their code to GitHub.
"""

# ============================================================================
# FOR PERSON B — AGENTS & LANGGRAPH IMPLEMENTATION
# ============================================================================

PERSON_B_INSTRUCTIONS = """
📝 PERSON B — Agents & LangGraph Implementation

Your code should implement the verification pipeline. Here's what to do:

STEP 1: Create your feature branch
────────────────────────────────────
$ git checkout -b feat/agents-pipeline
$ git pull origin main  # Get latest from Person A


STEP 2: Implement these files:
────────────────────────────────
✓ clarity/agents/hallucination.py
  - Async function: async def run_hallucination_check(context: dict) -> AgentVerdict
  - Extract verifiable claims from LLM output
  - Use TinyFish to verify each claim
  - Return AgentVerdict with score 0-100

✓ clarity/agents/reasoning.py
  - Async function: async def run_reasoning_check(context: dict) -> AgentVerdict
  - Analyze logical consistency
  - Check for contradictions
  - Return AgentVerdict with issues list

✓ clarity/agents/confidence.py
  - Async function: async def run_confidence_check(context: dict) -> AgentVerdict
  - Run prompt N times with different temperatures
  - Compare consistency of outputs
  - Return AgentVerdict with variance score

✓ clarity/agents/context_analyzer.py (COMPLETE implementation)
  - Async function: async def run_context_check(context: dict) -> AgentVerdict
  - Use deterministic heuristics (no LLM calls)
  - Check: saturation, tools, system prompt, temperature, stop_reason
  - Return AgentVerdict with findings

✓ clarity/integrations/tinyfish_client.py (COMPLETE implementation)
  - Implement: async def verify_claim_on_web(claim: str, sources: list) -> dict
  - Call TinyFish API to verify claims
  - Return: {verified: bool, evidence: str, confidence: float}

✓ clarity/agents/orchestrator.py (IMPLEMENT run_verification_pipeline)
  - Create LangGraph StateGraph
  - Fan out to 4 agents in parallel
  - Aggregate scores with weights: hallucination=30%, reasoning=25%, confidence=25%, context=20%
  - Implement: async def run_verification_pipeline(exchange_id: str, context: dict) -> TrustReport


STEP 3: Test your implementation
───────────────────────────────
$ python -m pytest tests/agents/ -v
$ python test_orchestrator.py


STEP 4: Import contracts for Person A
──────────────────────────────────────
These are the function signatures you MUST follow:

    from clarity.models import TrustReport, AgentVerdict
    from clarity.agents.state import VerificationState
    
    async def run_verification_pipeline(
        exchange_id: str,
        context: dict[str, Any],
    ) -> TrustReport:
        \"\"\"
        Run all 4 agents in parallel and return consolidated TrustReport.
        
        Args:
            exchange_id: UUID of the captured exchange
            context: Dict from extract_verification_context()
        
        Returns:
            TrustReport with all 4 verdicts and overall_score
        \"\"\"


STEP 5: Commit and push
───────────────────────
$ git add clarity/agents/ clarity/integrations/
$ git commit -m "feat: implement 4 verification agents + LangGraph orchestrator"
$ git push -u origin feat/agents-pipeline


STEP 6: Create Pull Request
────────────────────────────
Go to GitHub → feat/agents-pipeline → Create Pull Request
Wait for Person A to review and merge


DEPENDENCIES YOU MAY NEED:
── LangGraph (already in pyproject.toml)
── langchain-anthropic (already in pyproject.toml)
── httpx (already in pyproject.toml)
"""


# ============================================================================
# FOR PERSON C — FRONTEND & UX IMPLEMENTATION
# ============================================================================

PERSON_C_INSTRUCTIONS = """
🎨 PERSON C — Frontend Dashboard & UX Implementation

Your code should build the user-facing dashboard and SDK enhancements.


STEP 1: Create your feature branch
────────────────────────────────────
$ git checkout -b feat/frontend-ux
$ git pull origin main  # Get latest from Person A


STEP 2: Implement these files:
────────────────────────────────
✓ dashboard/index.html (COMPLETE implementation)
  - Single-page HTML/CSS/JS dashboard (no framework needed)
  - Dark theme for demo day
  - Features:
    - Input panel: system prompt, temperature controls
    - Score ring: animated SVG showing 0-100 trust score
    - Risk badge: low/medium/high/critical
    - Warnings panel: collapsible orange-bordered cards
    - 4 agent cards: score, summary, findings, suggestions for each
    - LLM output panel: monospace, scrollable
    - Ada chat panel: conversational Q&A about report
  - API calls:
    POST /api/v1/verify → get content + trust_report
    POST /api/v1/explain → explain report in plain language
    GET /api/v1/reports → fetch report history

✓ clarity/integrations/ada_client.py (COMPLETE implementation)
  - Async function: async def explain_trust_report(summary: dict, question: str) -> dict
  - Call Ada API to get plain-language explanation
  - Fallback: local_explanation() if Ada unavailable
  - Return: {explanation: str, suggested_questions: list[str]}

✓ clarity/sdk.py (ENHANCE existing)
  - Add UI features to ClarityResult
  - Add summary property
  - Add risk property
  - Ensure both local and remote modes work


STEP 3: Test your implementation
───────────────────────────────
$ npm install  # If using any frontend build tools
$ python -m clarity.main  # Start server
# Visit http://localhost:8000 in browser


STEP 4: Import contracts for Person A
──────────────────────────────────────
These are the function signatures you MUST follow:

    from clarity.integrations.ada_client import AdaClient
    
    async def explain_trust_report(
        self,
        summary: dict[str, Any],
        question: str,
    ) -> dict[str, str]:
        \"\"\"
        Explain a trust report in plain language.
        
        Args:
            summary: Compact dict from trust_report.get_summary()
            question: User's question about the report
        
        Returns:
            {
                "explanation": "Plain language answer...",
                "suggested_questions": ["What does this mean?", ...]
            }
        \"\"\"


STEP 5: Commit and push
───────────────────────
$ git add dashboard/ clarity/integrations/ada_client.py clarity/sdk.py
$ git commit -m "feat: implement dashboard UI + Ada integration + SDK enhancements"
$ git push -u origin feat/frontend-ux


STEP 6: Create Pull Request
────────────────────────────
Go to GitHub → feat/frontend-ux → Create Pull Request
Wait for Person A to review and merge


DEPENDENCIES YOU MAY NEED:
── httpx (already in pyproject.toml)
── pydantic (already in pyproject.toml)
"""


# ============================================================================
# FOR ALL TEAM MEMBERS — INTEGRATION TESTING
# ============================================================================

TESTING_GUIDE = """
🧪 INTEGRATION TESTING GUIDE (After all code is pushed)

Once Person B and Person C push their code, Person A will:

1. Merge all feature branches to main
2. Run integration tests:

    $ python -m pytest tests/integration/ -v
    $ python test_full_pipeline.py

3. Start the server:

    $ python -m clarity.main
    
4. Test via web UI at http://localhost:8000/

5. Test via Python SDK:

    from clarity.sdk import ClarityClient
    
    # Test remote mode
    client = ClarityClient(clarity_api_url="http://localhost:8000")
    result = client.verify(
        messages=[{"role": "user", "content": "Write a factorial function"}],
        system="You are a coding assistant",
        temperature=0.7,
    )
    
    print(f"Trust Score: {result.score}")  # 0-100
    print(f"Risk Level: {result.risk}")   # low/medium/high/critical
    print(f"Warnings: {result.warnings}")


EXPECTED WORKFLOW:
──────────────────
1. User sends prompt via dashboard or SDK
2. Server calls Claude via interceptor
3. Metadata extracted from response
4. LangGraph runs 4 agents in parallel
5. Agents produce verdicts (Person B code)
6. Aggregate trust report
7. Store in InsForge database
8. Return to user + display on dashboard
9. User can ask questions via Ada chat (Person C code)


END-TO-END TEST CASES:
──────────────────────
1. Code generation: "Write merge sort in Python"
   → Should score HIGH (low hallucination, good reasoning)

2. Hallucination test: "List the 10 tallest buildings in the world"
   → Should flag FALSE claims via TinyFish

3. Low confidence: Creative writing
   → Should show LOWER confidence (high temperature variance)

4. Perfect input: Simple factual question with good system prompt
   → Should score EXCELLENT across all metrics
"""


if __name__ == "__main__":
    print("=" * 70)
    print("  CLARITY TEAM — CODE INTEGRATION GUIDE")
    print("=" * 70)
    
    print("\n" + PERSON_B_INSTRUCTIONS)
    print("\n" + "=" * 70)
    print("\n" + PERSON_C_INSTRUCTIONS)
    print("\n" + "=" * 70)
    print("\n" + TESTING_GUIDE)
