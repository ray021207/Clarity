"""Ada client for conversational trust report explanation."""

import httpx
from clarity.config import settings


class AdaClient:
    """Ada conversational explainer for trust reports."""

    def __init__(self, api_url: str = "", api_key: str = ""):
        """Initialize Ada client."""
        self.api_url = api_url or settings.ada_api_url
        self.api_key = api_key or settings.ada_api_key
        self.use_local_fallback = not (self.api_url and self.api_key)

    async def explain_trust_report(self, summary: dict, question: str) -> dict[str, str]:
        """
        Explain a trust report in plain language.
        
        Tries Ada API first (if configured), falls back to local explanation.
        
        Args:
            summary: Compact trust report summary dict with keys like:
                - overall_score (0-100)
                - overall_risk (low/medium/high/critical)
                - hallucination_score, reasoning_score, confidence_score, context_quality_score
                - warnings (list of strings)
                - model_used
            question: User question about the report (e.g., "Why is my score 62?")
            
        Returns:
            Dict with:
                - explanation: Plain language answer to the question
                - suggested_questions: List of follow-up questions
        """
        # Use local fallback if Ada not configured
        if self.use_local_fallback:
            return self._local_explanation(summary, question)
        
        # Try Ada API
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Explain this trust report in plain language:\n\nReport Summary:\n{summary}\n\nUser Question: {question}",
                        }
                    ],
                }
                
                response = await client.post(
                    f"{self.api_url}/messages",
                    json=payload,
                    headers={"X-API-Key": self.api_key},
                    timeout=15.0,
                )
                response.raise_for_status()
                
                data = response.json()
                explanation = data.get("content", [{}])[0].get("text", "")
                
                return {
                    "explanation": explanation,
                    "suggested_questions": self._generate_suggestions(summary),
                }
        except Exception as e:
            # Fall back to local if Ada fails
            print(f"Ada API failed ({str(e)}), using local fallback")
            return self._local_explanation(summary, question)

    def _local_explanation(self, summary: dict, question: str) -> dict[str, str]:
        """
        Fallback local explanation when Ada is unavailable.
        
        Provides natural language explanations for common questions about trust reports.
        """
        score = summary.get("overall_score", 0)
        risk = summary.get("overall_risk", "unknown")
        hall_score = summary.get("hallucination_score", 0)
        reason_score = summary.get("reasoning_score", 0)
        conf_score = summary.get("confidence_score", 0)
        context_score = summary.get("context_quality_score", 0)
        warnings = summary.get("warnings", [])
        model = summary.get("model_used", "unknown model")
        
        q_lower = question.lower()
        
        # Score explanation: "Why is my score X?"
        if any(word in q_lower for word in ["why", "score", "why is my score"]):
            reason_parts = []
            
            if score >= 80:
                reason_parts.append(f"Your score of {score} (out of 100) is **strong**.")
            elif score >= 60:
                reason_parts.append(f"Your score of {score} is **moderate** — the output is reasonably reliable but has some concerns.")
            else:
                reason_parts.append(f"Your score of {score} is **low** — the output should be used with caution.")
            
            # Break down by agent
            reason_parts.append("\n**Breakdown by verification agent:**")
            
            if hall_score >= 80:
                reason_parts.append(f"✅ **Hallucination**: {hall_score}/100 — No major fabricated facts detected")
            elif hall_score >= 60:
                reason_parts.append(f"⚠️ **Hallucination**: {hall_score}/100 — Some factual claims may not be fully verified")
            else:
                reason_parts.append(f"❌ **Hallucination**: {hall_score}/100 — Contains unverified or false claims")
            
            if reason_score >= 80:
                reason_parts.append(f"✅ **Reasoning**: {reason_score}/100 — Logic is sound and consistent")
            elif reason_score >= 60:
                reason_parts.append(f"⚠️ **Reasoning**: {reason_score}/100 — Some logical gaps or weak points")
            else:
                reason_parts.append(f"❌ **Reasoning**: {reason_score}/100 — Contains logical errors or contradictions")
            
            if conf_score >= 80:
                reason_parts.append(f"✅ **Consistency**: {conf_score}/100 — Output is stable across repeated runs")
            elif conf_score >= 60:
                reason_parts.append(f"⚠️ **Consistency**: {conf_score}/100 — Output varies; results may differ with different settings")
            else:
                reason_parts.append(f"❌ **Consistency**: {conf_score}/100 — Output varies significantly; unreliable")
            
            if context_score >= 80:
                reason_parts.append(f"✅ **Context Quality**: {context_score}/100 — Prompt is well-formed and effective")
            elif context_score >= 60:
                reason_parts.append(f"⚠️ **Context Quality**: {context_score}/100 — Prompt has some issues (high temp, missing system prompt, etc.)")
            else:
                reason_parts.append(f"❌ **Context Quality**: {context_score}/100 — Prompt has significant issues")
            
            explanation = "\n".join(reason_parts)
        
        # Risk explanation: "Is this output safe to use?" or "Should I trust this?"
        elif any(word in q_lower for word in ["risk", "safe", "trust", "reliable", "should i", "should i trust"]):
            if risk.lower() == "low":
                explanation = f"**Yes, this output is safe to use.** With a risk level of **LOW** (score {score}/100), the output is reliable and well-verified. The model reasoned clearly, made no obvious factual errors, and the prompt was well-constructed."
            elif risk.lower() == "medium":
                explanation = f"**Proceed with caution.** The risk is **MEDIUM** (score {score}/100). The output has some strengths but also some concerns. Review the findings below before relying on it, especially for critical decisions. Consider double-checking any factual claims."
            elif risk.lower() in ["high", "critical"]:
                explanation = f"**Use with extreme caution or seek alternatives.** This output has a risk level of **{risk.upper()}** (score {score}/100). There are significant concerns with hallucinations, reasoning, or consistency. Only use if you can verify claims independently."
            else:
                explanation = f"The output has a **{risk.upper()}** risk level (score {score}/100). Review the individual agent findings for details."
        
        # Warnings explanation: "What do the warnings mean?"
        elif any(word in q_lower for word in ["warning", "alert", "concern", "issue", "problem"]):
            if not warnings:
                explanation = "**Great news!** ✅ There are no warnings. All aspects of the prompt and response checked out okay."
            else:
                warning_text = "\n".join([f"• {w}" for w in warnings[:5]])
                explanation = f"**{len(warnings)} warning(s) detected:**\n\n{warning_text}\n\nThese indicate areas where you should be extra careful. They might relate to context saturation, temperature settings, or truncated output."
        
        # How to improve explanation
        elif any(word in q_lower for word in ["improve", "better", "how can i", "how to", "increase", "higher"]):
            improvements = []
            
            if hall_score < 80:
                improvements.append("**For better fact-checking**: Provide more context or ask for cited sources. Avoid vague prompts.")
            if reason_score < 80:
                improvements.append("**For clearer reasoning**: Ask the model to explain its thinking step-by-step ('explain your reasoning'). Provide more context.")
            if conf_score < 80:
                improvements.append("**For consistency**: Lower the temperature (currently may be too high). Use a clearer, more specific prompt.")
            if context_score < 80:
                improvements.append("**For better prompts**: Add a clear system prompt, use lower temperature for factual tasks, avoid truncation by setting higher max_tokens.")
            
            if improvements:
                explanation = "**Ways to improve your score:**\n\n" + "\n".join(improvements)
            else:
                explanation = f"Your output is already strong at score {score}/100! No major improvements needed."
        
        # Default: general explanation
        else:
            explanation = (
                f"**Trust Report for '{model}'**\n\n"
                f"Overall score: **{score}/100** ({risk.upper()} risk)\n\n"
                f"This report analyzed your LLM output across four dimensions:\n"
                f"• Hallucination check: {hall_score}/100\n"
                f"• Reasoning validation: {reason_score}/100\n"
                f"• Consistency test: {conf_score}/100\n"
                f"• Prompt quality: {context_score}/100\n\n"
                f"Ask me specific questions like:\n"
                f"• 'Why is my score {score}?'\n"
                f"• 'Should I trust this output?'\n"
                f"• 'What are the warnings?'\n"
                f"• 'How can I improve?'"
            )
        
        return {
            "explanation": explanation,
            "suggested_questions": self._generate_suggestions(summary),
        }

    def _generate_suggestions(self, summary: dict) -> list[str]:
        """Generate contextual follow-up questions based on the trust report."""
        score = summary.get("overall_score", 0)
        risk = summary.get("overall_risk", "unknown")
        
        suggestions = []
        
        # Suggest based on risk level
        if risk.lower() in ["high", "critical"]:
            suggestions.append("Why is the score so low?")
            suggestions.append("What are the main concerns?")
            suggestions.append("How can I improve the output?")
        elif risk.lower() == "medium":
            suggestions.append("What are the key warnings?")
            suggestions.append("Should I trust this output?")
            suggestions.append("Which agent scored lowest?")
        else:
            suggestions.append("What makes this output reliable?")
            suggestions.append("Can I use this in production?")
        
        # General suggestions
        if not suggestions:
            suggestions = [
                "Why is my score this way?",
                "Should I trust this output?",
                "What are the warnings?",
            ]
        
        # Ensure at least 3 suggestions
        if len(suggestions) < 3:
            suggestions.extend([
                "How can I improve?",
                "Explain the breakdown",
            ])
        
        return suggestions[:3]  # Return top 3
