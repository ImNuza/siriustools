"""
AI-Enhanced Assistant Module for Cargill Voyage Chatbot
========================================================
Integrates Featherless.ai API (Qwen/Qwen2.5-72B-Instruct) to provide
natural language responses enhanced with voyage optimization context.

This module is OPTIONAL - the core chatbot works without it.

Author: Team Sirius
Date: January 2026
"""

import os
import json
import requests
from typing import Dict, Any, Optional, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

FEATHERLESS_API_KEY = "rc_04c90e05c6d921186006dcacbfdc4abd1781b62bcf623928b3289e60a488d0ab"
FEATHERLESS_API_URL = "https://api.featherless.ai/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct"

# Limitations disclaimer
AI_LIMITATIONS = """
<div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-left: 4px solid #d97706; padding: 12px 16px; margin: 8px 0; border-radius: 0 8px 8px 0; color: #92400e; font-size: 0.85rem;">
<strong>⚠️ AI-Enhanced Mode Limitations:</strong><br>
• Responses may occasionally contain inaccuracies - always verify with the data<br>
• API latency may cause slower responses (2-5 seconds)<br>
• AI cannot directly modify optimization parameters<br>
• Complex calculations should use the rule-based mode for accuracy<br>
• API has rate limits and may fail under heavy usage<br>
• AI responses are generated, not retrieved from verified sources
</div>
"""

# System prompt for the AI
SYSTEM_PROMPT = """You are a Cargill Ocean Transportation voyage optimization assistant. 
You help traders make data-driven decisions about vessel-cargo allocation.

CONTEXT:
- You have access to voyage optimization results from a Linear Programming model
- The model optimizes 15 vessels × 11 cargoes (165 combinations)
- Key metrics: TCE (Time Charter Equivalent), voyage profit, bunker costs
- Current bunker price: VLSFO ${vlsfo}/MT
- Current port delay assumption: {port_delay} additional days

CURRENT OPTIMIZATION RESULTS:
{optimization_context}

GUIDELINES:
1. Always ground your answers in the actual optimization data provided
2. When discussing TCE or profit, cite specific numbers from the context
3. If asked about something not in the data, say "I don't have that information in the current dataset"
4. Be concise but thorough - traders value precision
5. Highlight risks and thresholds when relevant
6. Use professional maritime/trading terminology

IMPORTANT: You are enhancing the user experience with natural language, but the core calculations 
come from the LP optimizer. Do not invent numbers - only use what's in the context."""


# =============================================================================
# API FUNCTIONS
# =============================================================================

def check_api_available() -> Tuple[bool, str]:
    """Check if the Featherless.ai API is available and working."""
    try:
        headers = {
            "Authorization": f"Bearer {FEATHERLESS_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Simple test request
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10
        }
        
        response = requests.post(
            FEATHERLESS_API_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            return True, "API connected successfully"
        else:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
            return False, f"API error: {error_msg}"
            
    except requests.exceptions.Timeout:
        return False, "API timeout - server may be busy"
    except requests.exceptions.ConnectionError:
        return False, "Connection error - check internet connection"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def build_optimization_context(session_state) -> str:
    """Build context string from current optimization results."""
    try:
        results = session_state.optimization_results
        valid = results[results['profit'] > -999999]
        assigned = valid[valid['cargo'] != 'SPOT MARKET']
        
        context_lines = [
            f"Total Portfolio Profit: ${session_state.total_profit:,.0f}",
            f"Number of Assigned Voyages: {len(assigned)}",
            "",
            "ASSIGNED VOYAGES:"
        ]
        
        for _, row in assigned.iterrows():
            context_lines.append(
                f"- {row['vessel']} → {row['cargo']}: TCE ${row['tce']:,.0f}/day, Profit ${row['profit']:,.0f}"
            )
        
        # Add unassigned vessels
        unassigned = valid[valid['cargo'] == 'SPOT MARKET']
        if not unassigned.empty:
            context_lines.append("")
            context_lines.append("UNASSIGNED VESSELS (Available for spot market):")
            for _, row in unassigned.iterrows():
                context_lines.append(f"- {row['vessel']}")
        
        return "\n".join(context_lines)
        
    except Exception as e:
        return f"Error building context: {str(e)}"


def get_ai_response(
    user_query: str,
    session_state,
    conversation_history: list = None
) -> Tuple[str, bool]:
    """
    Get an AI-enhanced response from Featherless.ai.
    
    Returns:
        Tuple of (response_text, success_flag)
    """
    try:
        # Build the system prompt with current context
        optimization_context = build_optimization_context(session_state)
        
        system_prompt = SYSTEM_PROMPT.format(
            vlsfo=session_state.current_vlsfo,
            port_delay=session_state.current_port_delay,
            optimization_context=optimization_context
        )
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history if provided (last 4 exchanges max)
        if conversation_history:
            for msg in conversation_history[-8:]:  # Last 4 user-assistant pairs
                if msg["role"] in ["user", "assistant"]:
                    # Strip HTML from assistant messages for context
                    content = msg["content"]
                    if msg["role"] == "assistant":
                        # Simple HTML stripping
                        import re
                        content = re.sub(r'<[^>]+>', '', content)
                        content = content[:500]  # Limit length
                    messages.append({"role": msg["role"], "content": content})
        
        # Add current query
        messages.append({"role": "user", "content": user_query})
        
        # Make API request
        headers = {
            "Authorization": f"Bearer {FEATHERLESS_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": MODEL_NAME,
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        response = requests.post(
            FEATHERLESS_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result["choices"][0]["message"]["content"]
            return ai_response, True
        else:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
            return f"AI API Error: {error_msg}", False
            
    except requests.exceptions.Timeout:
        return "AI response timed out. The server may be busy. Please try again or use Standard Mode.", False
    except requests.exceptions.ConnectionError:
        return "Could not connect to AI service. Please check your internet connection.", False
    except Exception as e:
        return f"AI Error: {str(e)}", False


def format_ai_response(ai_text: str, include_disclaimer: bool = True) -> str:
    """Format the AI response with proper styling and optional disclaimer."""
    
    formatted = f"""
<div style="background: linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%); border-left: 4px solid #7c3aed; padding: 16px 20px; margin: 16px 0; border-radius: 0 12px 12px 0; color: #5b21b6; font-size: 0.95rem; line-height: 1.6;">
<strong>🤖 AI-Enhanced Response:</strong><br><br>
{ai_text}
</div>
"""
    
    if include_disclaimer:
        formatted += """
<div style="font-size: 0.75rem; color: #6b7280; margin-top: 8px;">
<em>💡 Tip: For precise calculations, use the Quick Actions or Standard Mode.</em>
</div>
"""
    
    return formatted


# =============================================================================
# HYBRID PROCESSING
# =============================================================================

def process_with_ai_enhancement(
    query: str,
    rule_based_response: str,
    rule_based_viz: Any,
    session_state
) -> Tuple[str, Any]:
    """
    Process a query with AI enhancement.
    
    This combines the rule-based response (for accuracy) with AI explanation (for clarity).
    """
    
    # First, get the AI's natural language interpretation
    ai_prompt = f"""The user asked: "{query}"

The system has already calculated the following response:
{rule_based_response[:1000]}

Please provide a brief, natural language summary that:
1. Highlights the key insight from this data
2. Explains what it means for the trader
3. Suggests what they might want to explore next

Keep it to 2-3 sentences. Be conversational but professional."""

    ai_response, success = get_ai_response(ai_prompt, session_state)
    
    if success:
        # Combine: AI summary first, then the detailed data
        combined = format_ai_response(ai_response, include_disclaimer=False)
        combined += "\n\n---\n\n"
        combined += rule_based_response
        return combined, rule_based_viz
    else:
        # Fall back to rule-based only
        return rule_based_response, rule_based_viz


def process_freeform_query(
    query: str,
    session_state,
    conversation_history: list = None
) -> Tuple[str, Any]:
    """
    Process a freeform query that doesn't match rule-based patterns.
    Uses AI to generate a contextual response.
    """
    
    ai_response, success = get_ai_response(query, session_state, conversation_history)
    
    if success:
        return format_ai_response(ai_response), None
    else:
        # Return error message
        return f"""
<div style="background: linear-gradient(135deg, #fef2f2 0%, #fecaca 100%); border-left: 4px solid #dc2626; padding: 16px 20px; margin: 16px 0; border-radius: 0 12px 12px 0; color: #991b1b; font-size: 0.95rem;">
<strong>❌ AI Mode Error</strong><br><br>
{ai_response}<br><br>
<em>Switching to Standard Mode for this query.</em>
</div>
""", None
