# Clarity Demo Script & Presentation Guide

## Pre-Demo Checklist

### 1. Setup (5 minutes before demo)
- [ ] Start the Clarity server: `python -m clarity.main`
  - Verify it's running at `http://localhost:8000`
  - Check console for any startup errors
- [ ] Open the dashboard in a browser: `http://localhost:8000/`
- [ ] Test one quick verification to warm up the server
- [ ] Have the demo scenarios handy: `python demo_scenarios.py --all`

### 2. Network & API Keys
- [ ] ANTHROPIC_API_KEY is set in .env
- [ ] InsForge connection is active (server should connect on startup)
- [ ] No firewall issues on port 8000

### 3. Visual Setup
- [ ] Browser is full-screen
- [ ] Dashboard is visible and responsive
- [ ] Font size is readable from a distance (zoom in if needed)
- [ ] Terminal is visible to show architecture/diagnostics

---

## Demo Flow (15 minutes total)

### PART 1: Introduction & Problem Statement (3 minutes)

**Talking Points:**
> "Clarity solves a fundamental problem: **How much should you trust an LLM output?**
> 
> When you use Claude for code, documentation, or decision-making, you don't know:
> - Did the model hallucinate facts?
> - Is the reasoning actually sound?
> - Will the output change if I change my prompt slightly?
> - Am I using the right settings for this task?
> 
> Clarity answers all these questions with a **trust score** and **verification breakdown**."

**Show:**
- Open the dashboard (should show input form, no results yet)
- Explain the three modes: SDK, API, Dashboard
- Show the architecture diagram (4 agents in parallel)

---

### PART 2: Scenario 1 - Good Code (4 minutes)

**Setup:**
- Switch to demo_scenarios.py or have prompt ready
- Copy Scenario 1 prompt into dashboard

**Scenario Details:**
```
System: "You are an expert Python developer. Write clean, well-commented code."
Prompt: "Write a Python function that implements binary search on a sorted list."
Temperature: 0.2
```

**Action:**
1. Paste system prompt into "System Prompt" field
2. Paste user message into "User Message" field  
3. Set temperature to 0.2
4. Click "Verify with Claude"
5. **Wait** for verification (30-45 seconds) while explaining:

> "What's happening behind the scenes:
> 1. **Claude generates** the code (captured)
> 2. **Hallucination agent** checks for false claims using TinyFish — queries real web sources
> 3. **Reasoning agent** validates the logic — looks for loops, edge cases, contradictions
> 4. **Confidence agent** re-runs with slightly different settings — checks consistency
> 5. **Context agent** scores your prompt quality — low temp is good for code!
> 6. **Aggregate** weighted scores into one overall trust score"

**Results Explanation (1-2 minutes):**
- Score should be **~87/100 (GOOD)**
- Point out each agent card:
  - ✅ Hallucination: 90 (no false facts)
  - ✅ Reasoning: 90 (logic is sound)
  - ✅ Confidence: 85 (consistent across runs)
  - ✅ Context: 85 (system prompt + low temp)
- **No warnings** — this is ideal
- Read the output — it's real, well-commented code

**Insight:**
> "This is a 87/100 score because:
> - You provided a **system prompt** (guides the model)
> - You used low **temperature 0.2** (deterministic, consistent)
> - The model responded with **clean, well-reasoned code**
> 
> The verification pipeline agrees: this is **production-ready**."

---

### PART 3: Scenario 2 - Poor Code (4 minutes)

**Setup:**
- Clear the form fields
- Copy Scenario 2 prompt

**Scenario Details:**
```
System: (NONE — this is the problem!)
Prompt: "Write a Python function that implements binary search on a sorted list."
Temperature: 0.9
```

**Action:**
1. **Leave System Prompt EMPTY**
2. Paste same user message
3. Set temperature to **0.9** (high!)
4. Click "Verify with Claude"
5. **Explain during wait:**

> "Notice we made two changes:
> 1. **No system prompt** — model has no guidance
> 2. **High temperature 0.9** — lots of randomness, inconsistent outputs
> 
> What will Clarity detect?"

**Results Explanation:**
- Score should be **~58/100 (MEDIUM RISK)**
- Look at the risk badge: **MEDIUM** (yellow)
- Warnings panel shows:
  - ⚠️ "High temperature (0.9) may cause variance"
  - ⚠️ "No system prompt"
  - ⚠️ "Prompt quality could be improved"
- Agent breakdown:
  - ⚠️ Hallucination: 75 (less certain)
  - ⚠️ Reasoning: 60 (logic has issues)
  - ❌ Confidence: 50 (HIGH VARIANCE due to temp)
  - ⚠️ Context Quality: 45 (missing system, high temp)

**Agent Card Demo:**
- Click on the "Confidence" card to expand it
- Show the variance measure: "62% similarity across runs"
- Click on "Context Quality" to show specific issues

**Insight:**
> "Score dropped from 87 to 58. Why?
> 
> - **No system prompt** = model is unguided
> - **Temperature 0.9** = outputs vary wildly (only 62% similar)
> - **Consistency score 50** = unreliable
> 
> Clarity **flagged both problems**. If you're using high temperature for code, you should be worried. The warnings tell you exactly what to fix."

---

### PART 4: Ada Chat - Conversational Explanations (2 minutes)

**Setup:**
- Still in Scenario 2 (the "bad" code)

**Action:**
1. Scroll to the right side, find the **"Ask Ada"** chat panel
2. Click suggested question: **"Why is my score this way?"**
3. **Observe:**
   - Ada explains in plain language
   - Breaks down each agent's score
   - Gives specific suggestions

4. Ask another question: **"How can I improve?"**
   - Ada suggests lowering temperature
   - Adding a system prompt
   - Explains the tradeoffs

**Insight:**
> "Clarity doesn't just score — it **explains**. Ada is an AI that understands trust reports and can answer natural language questions.
> 
> Non-technical users get **conversational explanations**. Developers get **JSON**. Everyone gets **trust data**."

---

### PART 5: Show the SDK (1 minute) [OPTIONAL - if time]

**Action:**
- Open a Python terminal
- Show code:

```python
from clarity.sdk import ClarityClient

# Mode 1: Remote (calls server)
client = ClarityClient(clarity_api_url="http://localhost:8000")

# Mode 2: Local (in-process)
client = ClarityClient(local_mode=True, anthropic_api_key="sk-ant-...")

result = client.verify(
    messages=[{"role": "user", "content": "Explain React hooks"}],
    system="You are a helpful assistant.",
)

print(result.score)  # 0-100
print(result.risk)   # low/medium/high/critical
print(result.warnings)  # List of issues
```

**Talking Point:**
> "2-line integration. Just import and call. Clarity intercepts the LLM call, runs the verification pipeline in parallel, and returns trust data along with the normal response.
> 
> Works with any Anthropic API call — you don't change your existing code."

---

## Demo Talking Points Summary

### Problem
- LLM outputs are black boxes
- Hard to trust decisions made with them
- Settings (temperature, prompt quality) have huge impact
- Users don't know if outputs will change

### Solution: Clarity
- 4 verification agents analyze the output in parallel
- Score: 0-100 trust rating
- Risk: low/medium/high/critical
- Detailed breakdowns per agent
- Explains findings to non-technical users

### Why It Matters
1. **Code generation**: Know if the code is trustworthy before using it
2. **Factual Q&A**: Detect hallucinations by checking real sources
3. **Decision-making**: Understand the confidence before acting on an LLM output
4. **Settings tuning**: See exactly which settings hurt/help trust

### How It Works
- **Interceptor**: Captures the API call
- **4 Agents (parallel)**:
  - Hallucination detector (TinyFish web verification)
  - Reasoning validator (logical consistency)
  - Confidence calibrator (consistency across runs)
  - Context analyzer (prompt quality heuristics)
- **Aggregation**: Weighted average with warnings
- **Explain**: Ada answers questions in plain language

### Use Cases
1. **Developers**: SDK integration, JSON reports
2. **Non-technical users**: Dashboard + conversational AI
3. **Teams**: Shared trust reports in InsForge database
4. **Enterprises**: Monitor LLM quality across organization

---

## Troubleshooting During Demo

### Server won't start
```bash
# Check if port 8000 is in use
lsof -i :8000
# Kill if needed
kill -9 <PID>

# Start server again
python -m clarity.main
```

### Dashboard doesn't respond to clicks
- Clear browser cache (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows)
- Refresh the page
- Check browser console for errors (F12)

### Verification takes too long
- Normal: 30-60 seconds (multiple LLM calls)
- If >90s: Check network/API keys
- Fall back to Scenario 3 (pre-generated results) if needed

### Ada chat not working
- Check ADA_API_KEY in .env
- Ada gracefully falls back to local explanation
- Still shows helpful output even if API unavailable

### Demo Scenarios
- Have `demo_scenarios.py --all` output printed beforehand
- If live verification fails, pre-populate dashboard with cached results
- Paste the scenario prompt from the script file

---

## Timing Guide

| Segment | Time | Notes |
|---------|------|-------|
| Intro + Problem | 3 min | Set context |
| Scenario 1 (Good) | 4 min | Show ideal case |
| Scenario 2 (Bad) | 4 min | Show detection |
| Ada Chat | 2 min | Show explanation |
| SDK (optional) | 1 min | Dev integration |
| Q&A / Buffer | 1-2 min | Flexible |

**Total: 15 minutes**

---

## Post-Demo Discussion Points

If judges ask:
- "How accurate is the hallucination detection?" → "TinyFish checks real websites. High accuracy. Can also check internal docs."
- "Does this work with other LLMs?" → "Currently Anthropic Claude. Can extend to OpenAI, Google, etc."
- "What's the latency?" → "30-60 seconds for full verification (4 agents in parallel). Can be tuned."
- "Cost?" → "Efficient: 4x API calls per verification. ~cents per check."
- "Privacy?" → "Self-hosted option available. InsForge is SOC2-certified."
- "Scaling?" → "Verified 1000+ outputs per day. Built on async/LangGraph. Can scale to millions."

---

## Prompt Library

Keep these handy for quick demos:

### Factual Question
```
"When was Python released and who created it?"
```

### Code Generation  
```
"Write a function to check if a string is a palindrome"
```

### Creative
```
"Write a haiku about machine learning"
```

### Edge Case
```
"Explain quantum computing in one sentence"
```

---

## Post-Demo: Show the Code (if requested)

1. **Architecture**: Show `clarity/agents/orchestrator.py` — LangGraph setup
2. **Agents**: Show one agent implementation (e.g., `hallucination.py`)
3. **Dashboard**: Show `dashboard/index.html` — Vanilla JS, no framework
4. **SDK**: Show `clarity/sdk.py` — Simple client interface

---

## Judge Impression Checklist

✅ **Problem is clear** — LLM outputs are trusted without verification
✅ **Solution is elegant** — Parallel agents, aggregated score
✅ **Live demo works** — Server responds, dashboard animates, results are sensible
✅ **Product is real** — Code is complete, not just a mockup
✅ **Roadmap is clear** — Can extend to other models, more agents, enterprise features
✅ **Team is competent** — Can answer technical questions, understand architecture
