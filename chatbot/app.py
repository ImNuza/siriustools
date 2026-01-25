"""
Voyage Recommendation Chatbot for Cargill-SMU Datathon 2026
===========================================================
A Streamlit-based chatbot that displays REAL optimization results
and supports what-if scenarios with actual recalculations.

ENHANCED: Plotly interactive charts, Cargill branding, TCE heatmap

Usage:
    cd chatbot
    streamlit run app.py

Author: Team Sirius
Date: January 2026
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sys
from pathlib import Path
from datetime import timedelta
from typing import Dict, List, Any, Tuple

# =============================================================================
# IMPORT FROM SRC MODULES (Single Source of Truth)
# =============================================================================

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
# PAGE CONFIG & CARGILL STYLING
# =============================================================================

st.set_page_config(
    page_title="Cargill Voyage Assistant",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load Plotly from CDN to avoid proxy issues
st.markdown("""
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
""", unsafe_allow_html=True)

# Cargill brand colors and professional styling
st.markdown("""
<style>
    .main-header { 
        font-size: 2.2rem; 
        font-weight: 700; 
        color: #00843D; 
        margin-bottom: 0;
    }
    .sub-header { 
        font-size: 1rem; 
        color: #6B7280; 
        margin-top: 0;
    }
    .info-box {
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
        border-left: 4px solid #00843D;
        padding: 16px 20px;
        margin: 16px 0;
        border-radius: 0 12px 12px 0;
        color: #166534;
        font-size: 0.95rem;
        line-height: 1.6;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .portfolio-summary {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 16px;
        border-radius: 8px;
        margin: 12px 0;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-size: 1rem;
        color: #1e293b;
        font-weight: 500;
    }
    .metric-card {
        background: linear-gradient(135deg, #00843D 0%, #006B31 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin: 8px 0;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
    }
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    .stChatMessage {
        border-radius: 12px;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# PLOTLY VISUALIZATION FUNCTIONS
# =============================================================================

def viz_tce_bar(data: List[Dict]) -> go.Figure:
    """Horizontal bar chart - TCE comparison with Cargill colors."""
    df = pd.DataFrame(data)
    df['label'] = df['vessel'] + ' → ' + df['cargo']
    df = df.sort_values('tce', ascending=True)
    
    # Cargill green gradient based on TCE value
    colors = ['#00843D' if x > 15000 else '#16a34a' if x > 10000 else '#eab308' if x > 0 else '#dc2626' for x in df['tce']]
    
    fig = go.Figure(go.Bar(
        y=df['label'],
        x=df['tce'],
        orientation='h',
        marker_color=colors,
        text=[f"${x:,.0f}" for x in df['tce']],
        textposition='outside'
    ))
    
    fig.update_layout(
        title=dict(text="TCE Comparison by Voyage", font=dict(size=18, color='#00843D')),
        xaxis_title="TCE ($/day)",
        height=max(300, len(df) * 50),
        margin=dict(l=20, r=100, t=50, b=40),
        showlegend=False,
        hovermode='closest',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    return fig


def viz_heatmap(data: List[Dict]) -> go.Figure:
    """Heatmap - all vessel-cargo TCE combinations."""
    vessels = sorted(set(r['vessel'] for r in data))
    cargoes = sorted(set(r['cargo'] for r in data))
    
    matrix = []
    text_matrix = []
    
    for vessel in vessels:
        row = []
        text_row = []
        for cargo in cargoes:
            tce = next((r['tce'] for r in data if r['vessel'] == vessel and r['cargo'] == cargo), 0)
            row.append(tce)
            text_row.append(f"${tce:,.0f}")
        matrix.append(row)
        text_matrix.append(text_row)
    
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=cargoes,
        y=vessels,
        colorscale='RdYlGn',
        text=text_matrix,
        texttemplate="%{text}",
        textfont=dict(size=11),
        hovertemplate="%{y} → %{x}<br>TCE: $%{z:,.0f}/day<extra></extra>"
    ))
    
    fig.update_layout(
        title=dict(text="TCE Matrix: All Vessel-Cargo Combinations", font=dict(size=18, color='#00843D')),
        xaxis_title="Cargo",
        yaxis_title="Vessel",
        height=400,
        margin=dict(l=20, r=20, t=50, b=40)
    )
    return fig


def viz_profit_waterfall(vessel: str, cargo: str, gross: float, commission: float, 
                         fuel: float, hire: float, port: float, profit: float) -> go.Figure:
    """Waterfall chart - profit breakdown for a voyage."""
    fig = go.Figure(go.Waterfall(
        x=['Gross Freight', 'Commission', 'Fuel Cost', 'Charter Hire', 'Port Costs', 'Voyage Profit'],
        y=[gross, -commission, -fuel, -hire, -port, profit],
        measure=['absolute', 'relative', 'relative', 'relative', 'relative', 'total'],
        text=[f"${gross:,.0f}", f"-${commission:,.0f}", f"-${fuel:,.0f}", 
              f"-${hire:,.0f}", f"-${port:,.0f}", f"${profit:,.0f}"],
        textposition='outside',
        increasing_marker_color='#00843D',
        decreasing_marker_color='#dc2626',
        totals_marker_color='#0ea5e9'
    ))
    
    fig.update_layout(
        title=dict(text=f"Profit Breakdown: {vessel} → {cargo}", font=dict(size=18, color='#00843D')),
        yaxis_title="Amount (USD)",
        height=400,
        margin=dict(l=20, r=20, t=50, b=40),
        showlegend=False
    )
    return fig


def viz_bunker_sensitivity(prices: List[float], profits: List[float], current_price: float) -> go.Figure:
    """Line chart - bunker price sensitivity analysis."""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=prices,
        y=profits,
        mode='lines+markers',
        name='Portfolio Profit',
        line=dict(color='#00843D', width=3),
        marker=dict(size=8),
        fill='tozeroy',
        fillcolor='rgba(0, 132, 61, 0.1)'
    ))
    
    # Mark current price
    current_profit = profits[len(profits)//2] if profits else 0
    fig.add_trace(go.Scatter(
        x=[current_price],
        y=[current_profit],
        mode='markers',
        name=f'Current (${current_price}/MT)',
        marker=dict(color='#eab308', size=14, symbol='star')
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Break-even")
    
    fig.update_layout(
        title=dict(text="Bunker Price Sensitivity Analysis", font=dict(size=18, color='#00843D')),
        xaxis_title="VLSFO Price ($/MT)",
        yaxis_title="Portfolio Profit ($)",
        height=400,
        margin=dict(l=20, r=20, t=50, b=40),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'data' not in st.session_state and DATA_LOADED:
    st.session_state.data = load_all_data()
if 'optimization_results' not in st.session_state and DATA_LOADED:
    results = optimize_portfolio(include_market_cargoes=False, verbose=False)
    st.session_state.optimization_results = results
    valid = results[results['profit'] > -999999]
    st.session_state.total_profit = valid['profit'].sum()
if 'base_vlsfo' not in st.session_state:
    st.session_state.base_vlsfo = 490
if 'base_mgo' not in st.session_state:
    st.session_state.base_mgo = 649

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def run_chatbot_optimization(vlsfo_price: float = None, mgo_price: float = None,
                              extra_port_days: int = 0) -> tuple:
    """Run optimization with custom parameters."""
    import optimization as opt
    
    original_vlsfo = opt.VLSFO_PRICE
    original_mgo = opt.MGO_PRICE
    
    if vlsfo_price is not None:
        opt.VLSFO_PRICE = vlsfo_price
    if mgo_price is not None:
        opt.MGO_PRICE = mgo_price
    
    try:
        results_df = optimize_portfolio(include_market_cargoes=False, verbose=False,
                                        extra_port_days=extra_port_days)
        total_profit = results_df[results_df['profit'] > -999999]['profit'].sum()
        return results_df, total_profit
    finally:
        opt.VLSFO_PRICE = original_vlsfo
        opt.MGO_PRICE = original_mgo


def get_all_tce_data() -> List[Dict]:
    """Get TCE data for all vessel-cargo combinations for heatmap."""
    data = st.session_state.data
    vessels = data['vessels']
    cargoes = data['cargoes']
    cargill_cargoes = cargoes[cargoes['cargo_type'] == 'cargill']
    
    results = []
    for _, vessel in vessels[vessels['vessel_type'] == 'cargill'].iterrows():
        for _, cargo in cargill_cargoes.iterrows():
            try:
                # calculate_voyage_profit uses global DISTANCE_LOOKUP, not a parameter
                result = calculate_voyage_profit(
                    vessel=vessel,
                    cargo=cargo
                )
                results.append({
                    'vessel': vessel['vessel_name'],
                    'cargo': cargo['cargo_id'],
                    'tce': result.get('tce', 0) if result else 0,
                    'profit': result.get('profit', 0) if result else 0
                })
            except Exception as e:
                # Log the error for debugging
                print(f"Error calculating {vessel['vessel_name']} -> {cargo['cargo_id']}: {e}")
                results.append({
                    'vessel': vessel['vessel_name'],
                    'cargo': cargo['cargo_id'],
                    'tce': 0,
                    'profit': 0
                })
    return results


def get_voyage_summary() -> str:
    """Generate formatted voyage summary."""
    results = st.session_state.optimization_results
    valid_results = results[results['profit'] > -999999]
    
    summary = f"""
<div class="info-box">
<strong>🎯 Optimal Portfolio Allocation</strong><br><br>
<strong>Total Portfolio Profit: ${st.session_state.total_profit:,.0f}</strong>
</div>

**Assigned Voyages:**
"""
    for _, row in valid_results.iterrows():
        if row['cargo'] != 'SPOT MARKET':
            summary += f"\n- **{row['vessel']}** → {row['cargo']}: TCE ${row['tce']:,.0f}/day, Profit ${row['profit']:,.0f}"
    
    unassigned = results[results['cargo'] == 'SPOT MARKET']
    if not unassigned.empty:
        summary += "\n\n**Unassigned Vessels (seek spot market):**"
        for _, row in unassigned.iterrows():
            summary += f"\n- {row['vessel']}"
    
    return summary


def run_scenario_analysis(bunker_change: int, port_delay: int) -> str:
    """Run scenario analysis with modified parameters."""
    new_vlsfo = st.session_state.base_vlsfo * (1 + bunker_change / 100)
    new_mgo = st.session_state.base_mgo * (1 + bunker_change / 100)
    
    new_results, new_profit = run_chatbot_optimization(
        vlsfo_price=new_vlsfo,
        mgo_price=new_mgo,
        extra_port_days=port_delay
    )
    
    profit_change = new_profit - st.session_state.total_profit
    pct_change = (profit_change / st.session_state.total_profit * 100) if st.session_state.total_profit else 0
    
    st.session_state.optimization_results = new_results
    st.session_state.total_profit = new_profit
    
    return f"""
<div class="info-box">
<strong>📊 Scenario Analysis Results</strong><br><br>
<strong>Parameters:</strong><br>
• Bunker price change: {bunker_change:+d}%<br>
• Additional port days: {port_delay}<br><br>
<strong>Impact:</strong><br>
• New portfolio profit: <strong>${new_profit:,.0f}</strong><br>
• Change from base: <strong>${profit_change:+,.0f}</strong> ({pct_change:+.1f}%)
</div>
"""


def get_vessel_info(vessel_name: str) -> str:
    """Get information about a specific vessel."""
    data = st.session_state.data
    vessels = data['vessels']
    vessel = vessels[vessels['vessel_name'].str.lower() == vessel_name.lower()]
    
    if vessel.empty:
        return f"Vessel '{vessel_name}' not found."
    
    v = vessel.iloc[0]
    return f"""
**🚢 {v['vessel_name']}**

| Attribute | Value |
|-----------|-------|
| DWT | {v['dwt']:,} MT |
| Hire Rate | ${v['hire_rate']:,.0f}/day |
| Current Port | {v['current_port']} |
| ETD | {v['etd']} |
| Ballast Speed | {v['ballast_speed']} knots |
| Laden Speed | {v['laden_speed']} knots |
"""


def process_query(query: str) -> Tuple[str, Any]:
    """Process user query and return response with optional visualization."""
    query_lower = query.lower()
    viz = None
    
    # Heatmap request
    if any(word in query_lower for word in ['heatmap', 'matrix', 'all combinations', 'compare all']):
        tce_data = get_all_tce_data()
        viz = viz_heatmap(tce_data)
        return "Here's the TCE matrix showing all vessel-cargo combinations:", viz
    
    # Recommendation queries
    if any(word in query_lower for word in ['recommend', 'best', 'optimal', 'allocation', 'summary']):
        results = st.session_state.optimization_results
        valid = results[(results['profit'] > -999999) & (results['cargo'] != 'SPOT MARKET')]
        tce_data = [{'vessel': r['vessel'], 'cargo': r['cargo'], 'tce': r['tce']} 
                    for _, r in valid.iterrows()]
        if tce_data:
            viz = viz_tce_bar(tce_data)
        return get_voyage_summary(), viz
    
    # Sensitivity analysis
    if any(word in query_lower for word in ['sensitivity', 'bunker impact', 'what if bunker']):
        prices = list(range(400, 801, 50))
        profits = []
        for price in prices:
            _, profit = run_chatbot_optimization(vlsfo_price=price)
            profits.append(profit)
        viz = viz_bunker_sensitivity(prices, profits, st.session_state.base_vlsfo)
        return "Here's how portfolio profit changes with bunker prices:", viz
    
    # Vessel-specific queries
    vessel_names = ['ann bell', 'ocean horizon', 'pacific glory', 'golden ascent']
    for vessel in vessel_names:
        if vessel in query_lower:
            return get_vessel_info(vessel), None
    
    # TCE queries
    if 'tce' in query_lower:
        results = st.session_state.optimization_results
        valid = results[(results['tce'] > -999999) & (results['cargo'] != 'SPOT MARKET')]
        if not valid.empty:
            avg_tce = valid['tce'].mean()
            tce_data = [{'vessel': r['vessel'], 'cargo': r['cargo'], 'tce': r['tce']} 
                        for _, r in valid.iterrows()]
            viz = viz_tce_bar(tce_data)
            return f"**Average TCE: ${avg_tce:,.0f}/day**", viz
        return "No valid TCE data available.", None
    
    # Profit queries
    if 'profit' in query_lower:
        results = st.session_state.optimization_results
        valid = results[results['profit'] > -999999]
        response = f"""
**Portfolio Profit Summary:**

Total Portfolio Profit: **${st.session_state.total_profit:,.0f}**

| Vessel | Cargo | Profit |
|--------|-------|--------|
"""
        for _, r in valid.iterrows():
            if r['cargo'] != 'SPOT MARKET':
                response += f"| {r['vessel']} | {r['cargo']} | ${r['profit']:,.0f} |\n"
        return response, None
    
    # Help / default
    return """
**🚢 I can help you with:**

1. **📊 Voyage Recommendations** - "What is the optimal allocation?"
2. **🗺️ TCE Heatmap** - "Show me all combinations" 
3. **🚢 Vessel Information** - "Tell me about Ann Bell"
4. **💰 Profit Analysis** - "What is the total profit?"
5. **📈 TCE Analysis** - "What are the TCE values?"
6. **📉 Sensitivity Analysis** - "Show bunker sensitivity"
7. **🔄 Scenarios** - Use the sidebar sliders to test what-if scenarios

Try asking one of these questions!
""", None


# =============================================================================
# MAIN UI
# =============================================================================

# Header with Cargill branding
st.markdown('<p class="main-header">🚢 Cargill Voyage Assistant</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Your AI co-pilot for voyage optimization decisions | Team Sirius</p>', unsafe_allow_html=True)

if not DATA_LOADED:
    st.error(f"Failed to load data: {IMPORT_ERROR}")
    st.stop()

# Metrics row
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">${st.session_state.total_profit:,.0f}</div>
        <div class="metric-label">Portfolio Profit</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    valid = st.session_state.optimization_results[st.session_state.optimization_results['profit'] > -999999]
    assigned = len(valid[valid['cargo'] != 'SPOT MARKET'])
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{assigned}</div>
        <div class="metric-label">Voyages Assigned</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    avg_tce = valid[valid['cargo'] != 'SPOT MARKET']['tce'].mean() if not valid.empty else 0
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">${avg_tce:,.0f}</div>
        <div class="metric-label">Avg TCE/day</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Sidebar with scenario controls
with st.sidebar:
    st.markdown("### 📊 Scenario Analysis")
    
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
    
    if st.button("🔄 Run Scenario", type="primary", use_container_width=True):
        response = run_scenario_analysis(bunker_change, port_delay)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()
    
    st.divider()
    
    st.markdown("### ⚡ Quick Actions")
    
    if st.button("📋 Show Recommendations", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "What are the optimal voyage recommendations?"})
        response, viz = process_query("optimal allocation")
        st.session_state.messages.append({"role": "assistant", "content": response, "viz": viz})
        st.rerun()
    
    if st.button("🗺️ Show TCE Heatmap", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "Show me all vessel-cargo combinations"})
        response, viz = process_query("heatmap")
        st.session_state.messages.append({"role": "assistant", "content": response, "viz": viz})
        st.rerun()
    
    if st.button("📉 Bunker Sensitivity", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "Show bunker price sensitivity"})
        response, viz = process_query("sensitivity")
        st.session_state.messages.append({"role": "assistant", "content": response, "viz": viz})
        st.rerun()
    
    st.divider()
    
    st.caption(f"**Current Prices:**")
    st.caption(f"VLSFO: ${st.session_state.base_vlsfo}/MT")
    st.caption(f"MGO: ${st.session_state.base_mgo}/MT")

# Display chat messages
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"], unsafe_allow_html=True)
        if message.get("viz") is not None:
            st.plotly_chart(message["viz"], use_container_width=True, key=f"chat_viz_{idx}")

# Chat input
if prompt := st.chat_input("Ask about voyage recommendations..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    response, viz = process_query(prompt)
    st.session_state.messages.append({"role": "assistant", "content": response, "viz": viz})
    with st.chat_message("assistant"):
        st.markdown(response, unsafe_allow_html=True)
        if viz is not None:
            st.plotly_chart(viz, use_container_width=True, key=f"new_viz_{len(st.session_state.messages)}")

# Show initial summary if no messages
if not st.session_state.messages:
    st.info("👋 Welcome! Ask me about voyage recommendations or use the sidebar to run scenarios.")
    with st.expander("📊 Current Optimal Allocation", expanded=True):
        st.markdown(get_voyage_summary(), unsafe_allow_html=True)
        # Show initial heatmap
        tce_data = get_all_tce_data()
        if tce_data:
            st.plotly_chart(viz_heatmap(tce_data), use_container_width=True, key="initial_heatmap")

# =============================================================================
# FOOTER
# =============================================================================

st.divider()
st.caption("Cargill-SMU Datathon 2026 | Team Sirius | Powered by Streamlit & Plotly")
