"""
Voyage Recommendation Chatbot for Cargill-SMU Datathon 2026
===========================================================
A Streamlit-based chatbot that displays REAL optimization results
and supports what-if scenarios with actual recalculations.

REFACTORED: Now imports from src/ modules instead of duplicating code.

Usage:
    cd chatbot
    streamlit run app.py

Author: Team Sirius
Date: January 2026
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import timedelta

# =============================================================================
# IMPORT FROM SRC MODULES (Single Source of Truth)
# =============================================================================

# Add src directory to path
SRC_PATH = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(SRC_PATH))

try:
    from data_loader import load_all_data, get_distance
    from optimization import (
        calculate_voyage_profit,
        optimize_portfolio,
        bunker_sensitivity_analysis,
        VLSFO_PRICE,
        MGO_PRICE
    )
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
# CHATBOT-SPECIFIC WRAPPER FUNCTIONS
# =============================================================================

def run_chatbot_optimization(data: dict, vlsfo_price: float = None, 
                              mgo_price: float = None,
                              extra_port_days: int = 0) -> tuple:
    """
    Wrapper around optimization.optimize_portfolio for chatbot use.
    Handles scenario parameters and returns formatted results.
    
    This function exists because the chatbot needs to:
    1. Pass custom bunker prices for scenarios
    2. Handle extra port days for what-if analysis
    3. Return results in a chatbot-friendly format
    """
    import optimization as opt
    
    # Temporarily modify global prices if provided
    original_vlsfo = opt.VLSFO_PRICE
    original_mgo = opt.MGO_PRICE
    
    if vlsfo_price is not None:
        opt.VLSFO_PRICE = vlsfo_price
    if mgo_price is not None:
        opt.MGO_PRICE = mgo_price
    
    try:
        # Run the optimization from src/optimization.py
        results_df = optimize_portfolio(
            include_market_cargoes=False, 
            verbose=False,
            extra_port_days=extra_port_days
        )
        
        # Calculate total profit from results
        total_profit = results_df[results_df['profit'] > -999999]['profit'].sum()
        
        return results_df, total_profit
    finally:
        # Restore original prices
        opt.VLSFO_PRICE = original_vlsfo
        opt.MGO_PRICE = original_mgo


# =============================================================================
# INITIALIZE SESSION STATE
# =============================================================================

if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'data' not in st.session_state and DATA_LOADED:
    with st.spinner("Loading voyage data..."):
        st.session_state.data = load_all_data()

if 'optimization_results' not in st.session_state and DATA_LOADED:
    with st.spinner("Running optimization..."):
        results_df, total_profit = run_chatbot_optimization(st.session_state.data)
        st.session_state.optimization_results = results_df
        st.session_state.total_profit = total_profit
        st.session_state.base_vlsfo = VLSFO_PRICE
        st.session_state.base_mgo = MGO_PRICE


# =============================================================================
# HELPER FUNCTIONS (UI-specific, not duplicating calculation logic)
# =============================================================================

def get_voyage_summary() -> str:
    """Generate summary from REAL optimization results."""
    if not DATA_LOADED or 'optimization_results' not in st.session_state:
        return "⚠️ Data not loaded. Please check the data files."
    
    results = st.session_state.optimization_results
    total_profit = st.session_state.total_profit
    
    # Build the table
    table_rows = []
    for _, row in results.iterrows():
        # Skip infeasible results
        if row.get('profit', 0) < -999999:
            continue
            
        route = row.get('route', 'N/A')
        if pd.isna(route):
            route = 'N/A'
        else:
            route = str(route)[:25]
        
        tce = row.get('tce', 0)
        if pd.isna(tce) or tce < -999999:
            tce_str = "N/A"
        else:
            tce_str = f"${tce:,.0f}/day"
        
        profit = row.get('profit', 0)
        if pd.isna(profit):
            profit = 0
            
        table_rows.append(
            f"| {row['vessel']} | {row['cargo']} | {route} | {tce_str} | ${profit:,.0f} |"
        )
    
    table = "\n".join(table_rows)
    
    return f"""
**🚢 Optimal Vessel-Cargo Allocation:**

| Vessel | Cargo | Route | TCE | Profit |
|--------|-------|-------|-----|--------|
{table}

---
**💰 Total Portfolio Profit: ${total_profit:,.0f}**

*Based on current bunker prices: VLSFO ${st.session_state.base_vlsfo}/MT*
"""


def get_vessel_info(vessel_name: str) -> str:
    """Get detailed info for a specific vessel."""
    if not DATA_LOADED:
        return "Data not loaded."
    
    vessels = st.session_state.data['vessels']
    vessel = vessels[vessels['vessel_name'].str.lower() == vessel_name.lower()]
    
    if vessel.empty:
        return f"Vessel '{vessel_name}' not found."
    
    v = vessel.iloc[0]
    
    # Find this vessel's assignment
    results = st.session_state.optimization_results
    assignment = results[results['vessel'].str.lower() == vessel_name.lower()]
    
    if not assignment.empty:
        a = assignment.iloc[0]
        tce = a.get('tce', 0)
        if pd.isna(tce) or tce < -999999:
            tce_str = "N/A"
        else:
            tce_str = f"${tce:,.0f}/day"
            
        total_days = a.get('total_days', 0)
        if pd.isna(total_days):
            total_days = 0
            
        assignment_text = f"""
**Recommended Assignment:** {a['cargo']}
- Route: {a.get('route', 'N/A')}
- TCE: {tce_str}
- Voyage Profit: ${a['profit']:,.0f}
- Duration: {total_days} days
"""
    else:
        assignment_text = "No assignment found."
    
    return f"""
**{v['vessel_name']}** ({v['vessel_type'].upper()})

📍 **Current Position:** {v['current_port']}
📅 **ETD:** {v['etd'].strftime('%Y-%m-%d')}

**Specifications:**
- DWT: {v['dwt']:,.0f} MT
- Eco Speed: {v['speed_laden_eco']} kn (laden) / {v['speed_ballast_eco']} kn (ballast)
- Consumption: {v['consumption_laden_eco_vlsf']} MT/day (laden)

{assignment_text}
"""


def run_scenario_analysis(bunker_change_pct: float, extra_port_days: int) -> str:
    """Run what-if scenario with new parameters."""
    if not DATA_LOADED:
        return "Data not loaded."
    
    base_vlsfo = st.session_state.base_vlsfo
    base_mgo = st.session_state.base_mgo
    
    new_vlsfo = base_vlsfo * (1 + bunker_change_pct / 100)
    new_mgo = base_mgo * (1 + bunker_change_pct / 100)
    
    # Run optimization with new parameters (using the src/optimization.py)
    new_results, new_profit = run_chatbot_optimization(
        st.session_state.data,
        vlsfo_price=new_vlsfo,
        mgo_price=new_mgo,
        extra_port_days=extra_port_days
    )
    
    # Compare with baseline
    baseline_profit = st.session_state.total_profit
    profit_change = new_profit - baseline_profit
    
    # Check if allocation changed
    baseline_alloc = st.session_state.optimization_results[['vessel', 'cargo']].values.tolist()
    new_alloc = new_results[['vessel', 'cargo']].values.tolist()
    allocation_changed = baseline_alloc != new_alloc
    
    # Build comparison table
    table_rows = []
    for _, row in new_results.iterrows():
        if row.get('profit', 0) < -999999:
            continue
        if row['cargo'] == 'SPOT MARKET':
            continue
            
        tce = row.get('tce', 0)
        if pd.isna(tce) or tce < -999999:
            tce_str = "N/A"
        else:
            tce_str = f"${tce:,.0f}/day"
            
        table_rows.append(
            f"| {row['vessel']} | {row['cargo']} | {tce_str} | ${row['profit']:,.0f} |"
        )
    
    table = "\n".join(table_rows)
    
    allocation_status = "⚠️ **ALLOCATION CHANGED!**" if allocation_changed else "✅ Allocation remains the same"
    
    return f"""
**📊 Scenario Analysis Results:**

**Parameters:**
- Bunker Price Change: {bunker_change_pct:+.0f}%
- VLSFO: ${base_vlsfo:.0f} → ${new_vlsfo:.0f}/MT
- Additional Port Days: {extra_port_days}

**Results:**

| Vessel | Cargo | TCE | Profit |
|--------|-------|-----|--------|
{table}

---
**Baseline Profit:** ${baseline_profit:,.0f}
**Scenario Profit:** ${new_profit:,.0f}
**Change:** ${profit_change:+,.0f} ({profit_change/baseline_profit*100 if baseline_profit else 0:+.1f}%)

{allocation_status}
"""


def process_query(query: str) -> str:
    """Process user query and generate response."""
    query_lower = query.lower()
    
    # Recommendation queries
    if any(word in query_lower for word in ['recommend', 'best', 'optimal', 'allocation', 'summary']):
        return get_voyage_summary()
    
    # Vessel-specific queries
    vessel_names = ['ann bell', 'ocean horizon', 'pacific glory', 'golden ascent']
    for vessel in vessel_names:
        if vessel in query_lower:
            return get_vessel_info(vessel)
    
    # TCE queries
    if 'tce' in query_lower:
        results = st.session_state.optimization_results
        valid_results = results[(results['tce'] > -999999) & (results['cargo'] != 'SPOT MARKET')]
        if not valid_results.empty:
            avg_tce = valid_results['tce'].mean()
            return f"""
**TCE Summary:**

Average TCE across fleet: **${avg_tce:,.0f}/day**

Individual vessel TCEs:
{valid_results[['vessel', 'cargo', 'tce']].to_markdown(index=False)}
"""
        return "No valid TCE data available."
    
    # Profit queries
    if 'profit' in query_lower:
        results = st.session_state.optimization_results
        valid_results = results[results['profit'] > -999999]
        return f"""
**Portfolio Profit Summary:**

Total Portfolio Profit: **${st.session_state.total_profit:,.0f}**

Breakdown by voyage:
{valid_results[['vessel', 'cargo', 'profit']].to_markdown(index=False)}
"""
    
    # Help / default
    return """
I can help you with:

1. **📊 Voyage Recommendations** - "What is the optimal allocation?"
2. **🚢 Vessel Information** - "Tell me about Ann Bell"
3. **💰 Profit Analysis** - "What is the total profit?"
4. **📈 TCE Analysis** - "What are the TCE values?"
5. **🔄 Scenarios** - Use the sidebar sliders to test what-if scenarios

Try asking one of these questions!
"""


# =============================================================================
# MAIN UI
# =============================================================================

st.title("🚢 Cargill Voyage Assistant")
st.markdown("*Your AI co-pilot for voyage optimization decisions*")

if not DATA_LOADED:
    st.error(f"Failed to load data: {IMPORT_ERROR}")
    st.stop()

# Sidebar with scenario controls
with st.sidebar:
    st.header("📊 Scenario Analysis")
    
    bunker_change = st.slider(
        "Bunker Price Change (%)", 
        min_value=-30, 
        max_value=50, 
        value=0,
        help="Adjust bunker prices to see impact on recommendations"
    )
    
    port_delay = st.slider(
        "Additional Port Days", 
        min_value=0, 
        max_value=10, 
        value=0,
        help="Add extra waiting days at ports"
    )
    
    if st.button("🔄 Run Scenario", type="primary"):
        response = run_scenario_analysis(bunker_change, port_delay)
        st.session_state.messages.append({
            "role": "assistant",
            "content": response
        })
        st.rerun()
    
    st.divider()
    
    st.header("⚡ Quick Actions")
    
    if st.button("📋 Show Recommendations"):
        st.session_state.messages.append({
            "role": "user",
            "content": "What are the optimal voyage recommendations?"
        })
        st.session_state.messages.append({
            "role": "assistant",
            "content": get_voyage_summary()
        })
        st.rerun()
    
    if st.button("💰 Show Profit Breakdown"):
        st.session_state.messages.append({
            "role": "user",
            "content": "Show me the profit breakdown"
        })
        st.session_state.messages.append({
            "role": "assistant",
            "content": process_query("profit")
        })
        st.rerun()
    
    st.divider()
    
    st.caption(f"**Current Prices:**")
    st.caption(f"VLSFO: ${st.session_state.base_vlsfo}/MT")
    st.caption(f"MGO: ${st.session_state.base_mgo}/MT")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask about voyage recommendations..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    response = process_query(prompt)
    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.markdown(response)

# Show initial summary if no messages
if not st.session_state.messages:
    st.info("👋 Welcome! Ask me about voyage recommendations or use the sidebar to run scenarios.")
    with st.expander("📊 Current Optimal Allocation", expanded=True):
        st.markdown(get_voyage_summary())

# =============================================================================
# FOOTER
# =============================================================================

st.divider()
st.caption("Cargill-SMU Datathon 2026 | Team Sirius")
