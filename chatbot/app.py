"""
Voyage Recommendation Chatbot for Cargill-SMU Datathon 2026
===========================================================
A simple Streamlit-based chatbot that answers questions about
voyage recommendations and supports what-if scenarios.

Usage:
    streamlit run app.py

Author: Team [Your Team Name]
Date: January 2026
"""

import streamlit as st
import sys
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

# Import our modules
try:
    from data_loader import load_all_data
    from freight_calculator import FreightCalculator
    DATA_LOADED = True
except ImportError as e:
    DATA_LOADED = False
    IMPORT_ERROR = str(e)


# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="Cargill Voyage Assistant",
    page_icon="🚢",
    layout="wide"
)


# =============================================================================
# INITIALIZE SESSION STATE
# =============================================================================

if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'data' not in st.session_state and DATA_LOADED:
    with st.spinner("Loading data..."):
        st.session_state.data = load_all_data()
        st.session_state.calculator = FreightCalculator(
            st.session_state.data, 
            use_eco_speed=True
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_voyage_summary():
    """Generate a summary of the optimal voyage recommendations."""
    # This is a placeholder - replace with actual calculations
    return """
**Optimal Vessel-Cargo Allocation:**

| Vessel | Cargo | Route | TCE |
|--------|-------|-------|-----|
| ANN BELL | CARGILL_1 | West Africa - China | $XX,XXX/day |
| OCEAN HORIZON | CARGILL_2 | Australia - China | $XX,XXX/day |
| PACIFIC GLORY | CARGILL_3 | Brazil - China | $XX,XXX/day |

**Total Portfolio Profit:** $X,XXX,XXX
"""


def process_query(query: str) -> str:
    """
    Process user query and generate response.
    
    In a full implementation, this would use OpenAI API for natural language understanding.
    """
    query_lower = query.lower()
    
    # Recommendation queries
    if any(word in query_lower for word in ['recommend', 'best', 'optimal', 'allocation']):
        return get_voyage_summary()
    
    # Vessel-specific queries
    if 'ann bell' in query_lower:
        return """
**ANN BELL** is currently at Qingdao, China (ETD: Feb 25, 2026)

- DWT: 180,803 MT
- Hire Rate: $11,750/day
- Economical Speed: 12.0 kn (laden) / 12.5 kn (ballast)

**Recommended Cargo:** CARGILL_1 (West Africa - China Bauxite)
- TCE: $XX,XXX/day
- Voyage Profit: $X,XXX,XXX
"""
    
    # What-if scenarios
    if 'what if' in query_lower or 'bunker' in query_lower:
        if 'increase' in query_lower or 'rise' in query_lower:
            return """
**Bunker Price Sensitivity Analysis:**

If bunker prices increase by 20%:
- Current VLSFO price: $490/MT (Singapore)
- New VLSFO price: $588/MT

**Impact on Recommendations:**
- ANN BELL → CARGILL_1: TCE drops from $XX,XXX to $XX,XXX/day
- Recommendation remains unchanged until bunker prices increase by **XX%**

**Threshold:** At $XXX/MT VLSFO, PACIFIC GLORY → CARGILL_2 becomes optimal.
"""
    
    # Port delay queries
    if 'delay' in query_lower or 'congestion' in query_lower:
        return """
**Port Delay Sensitivity Analysis:**

If China port delays increase by 3 days:
- Additional waiting time at discharge ports
- Impact on voyage duration and profitability

**Impact on Recommendations:**
- Voyages to China become less profitable
- Threshold: At **X additional days**, shorter routes become preferred

**Recommendation:** Monitor port congestion reports for Qingdao and Lianyungang.
"""
    
    # Help / default response
    return """
I can help you with:

1. **Voyage Recommendations** - Ask "What is the best voyage for our fleet?"
2. **Vessel Information** - Ask "Tell me about ANN BELL"
3. **What-If Scenarios** - Ask "What if bunker prices increase by 20%?"
4. **Port Delays** - Ask "How do port delays affect our recommendation?"

Try one of these questions!
"""


# =============================================================================
# MAIN UI
# =============================================================================

st.title("🚢 Cargill Voyage Assistant")
st.markdown("*Your AI co-pilot for voyage optimization decisions*")

# Sidebar with quick actions
with st.sidebar:
    st.header("Quick Actions")
    
    if st.button("📊 Show Recommendations"):
        st.session_state.messages.append({
            "role": "user",
            "content": "What are the optimal voyage recommendations?"
        })
        st.session_state.messages.append({
            "role": "assistant",
            "content": get_voyage_summary()
        })
    
    st.divider()
    
    st.header("Scenario Controls")
    bunker_change = st.slider("Bunker Price Change (%)", -20, 50, 0)
    port_delay = st.slider("Additional Port Days", 0, 10, 0)
    
    if st.button("🔄 Recalculate"):
        response = f"""
**Scenario Analysis Results:**

- Bunker Price Change: {bunker_change:+d}%
- Additional Port Days: {port_delay}

[Recalculating recommendations...]

*Results will be displayed here after implementation.*
"""
        st.session_state.messages.append({
            "role": "assistant",
            "content": response
        })

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask about voyage recommendations..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate and display response
    response = process_query(prompt)
    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.markdown(response)


# =============================================================================
# FOOTER
# =============================================================================

st.divider()
st.caption("Cargill-SMU Datathon 2026 | Team [Your Team Name]")


