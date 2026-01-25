"""
Voyage Recommendation Chatbot for Cargill-SMU Datathon 2026
===========================================================
A Streamlit-based chatbot that displays REAL optimization results
and supports what-if scenarios with actual recalculations.

ENHANCED: Plotly interactive charts, Cargill branding, TCE heatmap
FIXED: Scenario sliders now affect all visualizations
NEW: Blank chat on start, sticky header, market vessel/cargo view

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
from datetime import datetime
from typing import Dict, List, Any, Tuple
import uuid

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

# Cargill brand colors and professional styling with STICKY HEADER
st.markdown("""
<style>
    /* Sticky header container */
    .sticky-header {
        position: sticky;
        top: 0;
        z-index: 999;
        background: #0e1117;
        padding: 10px 0;
        margin: -1rem -1rem 1rem -1rem;
        padding: 1rem;
    }
    
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
    .scenario-box {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border-left: 4px solid #d97706;
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 0 8px 8px 0;
        color: #92400e;
        font-size: 0.85rem;
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
    .welcome-box {
        background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%);
        border-left: 4px solid #0284c7;
        padding: 20px;
        margin: 20px 0;
        border-radius: 0 12px 12px 0;
        color: #0c4a6e;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Make metrics row sticky */
    [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:first-child {
        position: sticky;
        top: 0;
        z-index: 999;
        background: #0e1117;
        padding: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# PLOTLY VISUALIZATION FUNCTIONS
# =============================================================================

def viz_tce_bar(data: List[Dict], scenario_label: str = "") -> go.Figure:
    """Horizontal bar chart - TCE comparison with Cargill colors."""
    df = pd.DataFrame(data)
    df['label'] = df['vessel'] + ' → ' + df['cargo']
    df = df.sort_values('tce', ascending=True)
    
    colors = ['#00843D' if x > 15000 else '#16a34a' if x > 10000 else '#eab308' if x > 0 else '#dc2626' for x in df['tce']]
    
    fig = go.Figure(go.Bar(
        y=df['label'],
        x=df['tce'],
        orientation='h',
        marker_color=colors,
        text=[f"${x:,.0f}" for x in df['tce']],
        textposition='outside'
    ))
    
    title = "TCE Comparison by Voyage"
    if scenario_label:
        title += f" ({scenario_label})"
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color='#00843D')),
        xaxis_title="TCE ($/day)",
        height=max(300, len(df) * 50),
        margin=dict(l=20, r=100, t=50, b=40),
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    return fig


def viz_heatmap(data: List[Dict], scenario_label: str = "") -> go.Figure:
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
    
    title = "TCE Matrix: All Vessel-Cargo Combinations"
    if scenario_label:
        title += f" ({scenario_label})"
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color='#00843D')),
        xaxis_title="Cargo",
        yaxis_title="Vessel",
        height=400,
        margin=dict(l=20, r=20, t=50, b=40)
    )
    return fig


def viz_bunker_sensitivity(prices: List[float], profits: List[float], current_price: float,
                           scenario_label: str = "") -> go.Figure:
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
    
    idx = min(range(len(prices)), key=lambda i: abs(prices[i] - current_price))
    current_profit = profits[idx]
    
    fig.add_trace(go.Scatter(
        x=[current_price],
        y=[current_profit],
        mode='markers',
        name=f'Current (${current_price:.0f}/MT)',
        marker=dict(color='#eab308', size=14, symbol='star')
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Break-even")
    
    title = "Bunker Price Sensitivity Analysis"
    if scenario_label:
        title += f" ({scenario_label})"
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color='#00843D')),
        xaxis_title="VLSFO Price ($/MT)",
        yaxis_title="Portfolio Profit ($)",
        height=400,
        margin=dict(l=20, r=20, t=50, b=40),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def viz_vessel_table(vessels_df: pd.DataFrame, vessel_type: str = "all") -> go.Figure:
    """Table visualization for vessels."""
    if vessel_type != "all":
        vessels_df = vessels_df[vessels_df['vessel_type'] == vessel_type]
    
    display_cols = ['vessel_name', 'dwt', 'hire_rate', 'current_port', 'etd', 'vessel_type']
    df = vessels_df[display_cols].copy()
    df.columns = ['Vessel', 'DWT', 'Hire Rate', 'Port', 'ETD', 'Type']
    df['DWT'] = df['DWT'].apply(lambda x: f"{x:,}")
    df['Hire Rate'] = df['Hire Rate'].apply(lambda x: f"${x:,.0f}/day")
    df['ETD'] = pd.to_datetime(df['ETD']).dt.strftime('%Y-%m-%d')
    df['Type'] = df['Type'].str.title()
    
    colors = ['#dcfce7' if t == 'Cargill' else '#fef3c7' for t in df['Type']]
    
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=list(df.columns),
            fill_color='#00843D',
            font=dict(color='white', size=12),
            align='left'
        ),
        cells=dict(
            values=[df[col] for col in df.columns],
            fill_color=[colors],
            font=dict(color='#1f2937', size=11),
            align='left'
        )
    )])
    
    fig.update_layout(
        title=dict(text=f"Fleet Overview ({vessel_type.title()} Vessels)", font=dict(size=18, color='#00843D')),
        height=400,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig


def viz_cargo_table(cargoes_df: pd.DataFrame, cargo_type: str = "all") -> go.Figure:
    """Table visualization for cargoes."""
    if cargo_type != "all":
        cargoes_df = cargoes_df[cargoes_df['cargo_type'] == cargo_type]
    
    display_cols = ['cargo_id', 'commodity', 'quantity', 'load_port', 'discharge_port', 'cargo_type']
    df = cargoes_df[display_cols].copy()
    df.columns = ['Cargo ID', 'Commodity', 'Quantity', 'Load Port', 'Discharge Port', 'Type']
    df['Quantity'] = df['Quantity'].apply(lambda x: f"{x:,} MT")
    df['Type'] = df['Type'].str.title()
    
    colors = ['#dcfce7' if t == 'Cargill' else '#fef3c7' for t in df['Type']]
    
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=list(df.columns),
            fill_color='#00843D',
            font=dict(color='white', size=12),
            align='left'
        ),
        cells=dict(
            values=[df[col] for col in df.columns],
            fill_color=[colors],
            font=dict(color='#1f2937', size=11),
            align='left'
        )
    )])
    
    fig.update_layout(
        title=dict(text=f"Cargo Overview ({cargo_type.title()} Cargoes)", font=dict(size=18, color='#00843D')),
        height=400,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'data' not in st.session_state and DATA_LOADED:
    st.session_state.data = load_all_data()
if 'scenario_applied' not in st.session_state:
    st.session_state.scenario_applied = False
if 'optimization_results' not in st.session_state and DATA_LOADED:
    results = optimize_portfolio(include_market_cargoes=False, verbose=False)
    st.session_state.optimization_results = results
    valid = results[results['profit'] > -999999]
    st.session_state.total_profit = valid['profit'].sum()
if 'base_vlsfo' not in st.session_state:
    st.session_state.base_vlsfo = 490
if 'base_mgo' not in st.session_state:
    st.session_state.base_mgo = 649
if 'current_vlsfo' not in st.session_state:
    st.session_state.current_vlsfo = 490
if 'current_mgo' not in st.session_state:
    st.session_state.current_mgo = 649
if 'current_port_delay' not in st.session_state:
    st.session_state.current_port_delay = 0
if 'chat_counter' not in st.session_state:
    st.session_state.chat_counter = 0

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_scenario_label() -> str:
    """Get a label describing current scenario settings."""
    if not st.session_state.scenario_applied:
        return ""
    if (st.session_state.current_vlsfo == st.session_state.base_vlsfo and 
        st.session_state.current_port_delay == 0):
        return "Base Scenario"
    
    parts = []
    if st.session_state.current_vlsfo != st.session_state.base_vlsfo:
        pct = ((st.session_state.current_vlsfo / st.session_state.base_vlsfo) - 1) * 100
        parts.append(f"Bunker {pct:+.0f}%")
    if st.session_state.current_port_delay > 0:
        parts.append(f"+{st.session_state.current_port_delay} port days")
    
    return ", ".join(parts) if parts else "Base Scenario"


def run_optimization_with_scenario() -> tuple:
    """Run optimization with current scenario parameters."""
    import optimization as opt
    
    original_vlsfo = opt.VLSFO_PRICE
    original_mgo = opt.MGO_PRICE
    
    opt.VLSFO_PRICE = st.session_state.current_vlsfo
    opt.MGO_PRICE = st.session_state.current_mgo
    
    try:
        results_df = optimize_portfolio(
            include_market_cargoes=False, 
            verbose=False,
            extra_port_days=st.session_state.current_port_delay
        )
        total_profit = results_df[results_df['profit'] > -999999]['profit'].sum()
        return results_df, total_profit
    finally:
        opt.VLSFO_PRICE = original_vlsfo
        opt.MGO_PRICE = original_mgo


def get_all_tce_data_with_scenario() -> List[Dict]:
    """Get TCE data for all vessel-cargo combinations using current scenario."""
    import optimization as opt
    
    data = st.session_state.data
    vessels = data['vessels']
    cargoes = data['cargoes']
    cargill_cargoes = cargoes[cargoes['cargo_type'] == 'cargill']
    
    original_vlsfo = opt.VLSFO_PRICE
    original_mgo = opt.MGO_PRICE
    opt.VLSFO_PRICE = st.session_state.current_vlsfo
    opt.MGO_PRICE = st.session_state.current_mgo
    
    results = []
    try:
        for _, vessel in vessels[vessels['vessel_type'] == 'cargill'].iterrows():
            for _, cargo in cargill_cargoes.iterrows():
                try:
                    result = calculate_voyage_profit(
                        vessel=vessel,
                        cargo=cargo,
                        extra_port_days=st.session_state.current_port_delay
                    )
                    results.append({
                        'vessel': vessel['vessel_name'],
                        'cargo': cargo['cargo_id'],
                        'tce': result.get('tce', 0) if result else 0,
                        'profit': result.get('profit', 0) if result else 0
                    })
                except Exception as e:
                    results.append({
                        'vessel': vessel['vessel_name'],
                        'cargo': cargo['cargo_id'],
                        'tce': 0,
                        'profit': 0
                    })
    finally:
        opt.VLSFO_PRICE = original_vlsfo
        opt.MGO_PRICE = original_mgo
    
    return results


def apply_scenario(bunker_change: int, port_delay: int):
    """Apply scenario settings and update session state."""
    st.session_state.current_vlsfo = st.session_state.base_vlsfo * (1 + bunker_change / 100)
    st.session_state.current_mgo = st.session_state.base_mgo * (1 + bunker_change / 100)
    st.session_state.current_port_delay = port_delay
    st.session_state.scenario_applied = True
    
    results, profit = run_optimization_with_scenario()
    st.session_state.optimization_results = results
    st.session_state.total_profit = profit


def get_voyage_summary() -> str:
    """Generate formatted voyage summary."""
    results = st.session_state.optimization_results
    valid_results = results[results['profit'] > -999999]
    
    scenario_label = get_scenario_label()
    scenario_note = f"\n<div class='scenario-box'>📊 Scenario: {scenario_label}</div>" if scenario_label else ""
    
    summary = f"""
<div class="info-box">
<strong>🎯 Optimal Portfolio Allocation</strong><br><br>
<strong>Total Portfolio Profit: ${st.session_state.total_profit:,.0f}</strong>
</div>
{scenario_note}

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


def get_vessel_info(vessel_name: str) -> str:
    """Get information about a specific vessel."""
    data = st.session_state.data
    vessels = data['vessels']
    vessel = vessels[vessels['vessel_name'].str.lower() == vessel_name.lower()]
    
    if vessel.empty:
        return f"Vessel '{vessel_name}' not found."
    
    v = vessel.iloc[0]
    return f"""
**🚢 {v['vessel_name']}** ({v['vessel_type'].title()})

| Attribute | Value |
|-----------|-------|
| DWT | {v['dwt']:,} MT |
| Hire Rate | ${v['hire_rate']:,.0f}/day |
| Current Port | {v['current_port']} |
| ETD | {v['etd']} |
| Ballast Speed (Eco) | {v['speed_ballast_eco']} knots |
| Laden Speed (Eco) | {v['speed_laden_eco']} knots |
"""


def process_query(query: str) -> Tuple[str, Any]:
    """Process user query and return response with optional visualization."""
    query_lower = query.lower()
    viz = None
    scenario_label = get_scenario_label()
    
    # Check if scenario has been applied
    if not st.session_state.scenario_applied and any(word in query_lower for word in 
        ['heatmap', 'matrix', 'recommend', 'optimal', 'sensitivity', 'tce', 'profit']):
        return """
<div class="welcome-box">
⚠️ <strong>Please apply a scenario first!</strong><br><br>
Use the sidebar to set your bunker price and port delay assumptions, then click <strong>"Apply Scenario"</strong> to see results.
</div>
""", None
    
    # Show all vessels
    if any(word in query_lower for word in ['all vessel', 'fleet', 'show vessel', 'list vessel']):
        data = st.session_state.data
        viz = viz_vessel_table(data['vessels'], 'all')
        return "Here's the complete fleet overview (Cargill + Market vessels):", viz
    
    # Show all cargoes
    if any(word in query_lower for word in ['all cargo', 'show cargo', 'list cargo']):
        data = st.session_state.data
        viz = viz_cargo_table(data['cargoes'], 'all')
        return "Here's the complete cargo overview (Cargill + Market cargoes):", viz
    
    # Heatmap request
    if any(word in query_lower for word in ['heatmap', 'matrix', 'all combinations', 'compare all']):
        tce_data = get_all_tce_data_with_scenario()
        viz = viz_heatmap(tce_data, scenario_label)
        response = "Here's the TCE matrix showing all vessel-cargo combinations:"
        if scenario_label:
            response += f"\n\n*Using scenario: {scenario_label}*"
        return response, viz
    
    # Recommendation queries
    if any(word in query_lower for word in ['recommend', 'best', 'optimal', 'allocation', 'summary']):
        results = st.session_state.optimization_results
        valid = results[(results['profit'] > -999999) & (results['cargo'] != 'SPOT MARKET')]
        tce_data = [{'vessel': r['vessel'], 'cargo': r['cargo'], 'tce': r['tce']} 
                    for _, r in valid.iterrows()]
        if tce_data:
            viz = viz_tce_bar(tce_data, scenario_label)
        return get_voyage_summary(), viz
    
    # Sensitivity analysis
    if any(word in query_lower for word in ['sensitivity', 'bunker impact', 'what if bunker']):
        import optimization as opt
        original_vlsfo = opt.VLSFO_PRICE
        original_mgo = opt.MGO_PRICE
        
        prices = list(range(400, 801, 50))
        profits = []
        
        for price in prices:
            opt.VLSFO_PRICE = price
            opt.MGO_PRICE = st.session_state.base_mgo * (price / st.session_state.base_vlsfo)
            try:
                results = optimize_portfolio(
                    include_market_cargoes=False, 
                    verbose=False,
                    extra_port_days=st.session_state.current_port_delay
                )
                profit = results[results['profit'] > -999999]['profit'].sum()
                profits.append(profit)
            except:
                profits.append(0)
        
        opt.VLSFO_PRICE = original_vlsfo
        opt.MGO_PRICE = original_mgo
        
        viz = viz_bunker_sensitivity(prices, profits, st.session_state.current_vlsfo, scenario_label)
        response = "Here's how portfolio profit changes with bunker prices:"
        if st.session_state.current_port_delay > 0:
            response += f"\n\n*Note: Includes +{st.session_state.current_port_delay} port delay days*"
        return response, viz
    
    # Vessel-specific queries
    vessel_names = ['ann bell', 'ocean horizon', 'pacific glory', 'golden ascent',
                    'atlantic fortune', 'pacific vanguard', 'coral emperor', 'everest ocean',
                    'polaris spirit', 'iron century', 'mountain trader', 'navis pride',
                    'aurora sky', 'zenith glory', 'titan legacy']
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
            viz = viz_tce_bar(tce_data, scenario_label)
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
3. **🚢 Fleet Overview** - "Show all vessels" (includes market vessels)
4. **📦 Cargo Overview** - "Show all cargoes" (includes market cargoes)
5. **💰 Profit Analysis** - "What is the total profit?"
6. **📈 TCE Analysis** - "What are the TCE values?"
7. **📉 Sensitivity Analysis** - "Show bunker sensitivity"
8. **🔄 Scenarios** - Use the sidebar sliders to test what-if scenarios

**Tip:** Start by clicking "Apply Scenario" in the sidebar!
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

# STICKY METRICS ROW - Only show if scenario applied
if st.session_state.scenario_applied:
    # Create a container that will be sticky
    metrics_container = st.container()
    with metrics_container:
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
        
        # Show current scenario
        scenario_label = get_scenario_label()
        if scenario_label:
            st.markdown(f"""
            <div class="scenario-box">
                📊 <strong>Active Scenario:</strong> {scenario_label}
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
        key="bunker_slider",
        help="Adjust bunker prices to see impact on recommendations"
    )
    
    port_delay = st.slider(
        "Additional Port Days", 
        min_value=0, 
        max_value=10, 
        value=0,
        key="port_slider",
        help="Add extra waiting days at ports"
    )
    
    if st.button("🔄 Apply Scenario", type="primary", use_container_width=True):
        apply_scenario(bunker_change, port_delay)
        st.session_state.messages.append({
            "role": "assistant", 
            "content": f"""
<div class="info-box">
<strong>📊 Scenario Applied</strong><br><br>
• Bunker price change: <strong>{bunker_change:+d}%</strong> (VLSFO: ${st.session_state.current_vlsfo:.0f}/MT)<br>
• Additional port days: <strong>{port_delay}</strong><br><br>
New portfolio profit: <strong>${st.session_state.total_profit:,.0f}</strong>
</div>

All visualizations will now reflect this scenario. Click any Quick Action to see results!
"""
        })
        st.rerun()
    
    if st.button("🔄 Reset to Base", use_container_width=True):
        apply_scenario(0, 0)
        # Reset slider values in session state
        st.session_state.bunker_slider = 0
        st.session_state.port_slider = 0
        st.session_state.messages.append({
            "role": "assistant",
            "content": "✅ Reset to base scenario (VLSFO: $490/MT, no port delays)"
        })
        st.rerun()
    
    st.divider()
    
    st.markdown("### ⚡ Quick Actions")
    
    if st.button("📋 Show Recommendations", use_container_width=True):
        st.session_state.chat_counter += 1
        st.session_state.messages.append({"role": "user", "content": "What are the optimal voyage recommendations?"})
        response, viz = process_query("optimal allocation")
        st.session_state.messages.append({"role": "assistant", "content": response, "viz": viz, "id": st.session_state.chat_counter})
        st.rerun()
    
    if st.button("🗺️ Show TCE Heatmap", use_container_width=True):
        st.session_state.chat_counter += 1
        st.session_state.messages.append({"role": "user", "content": "Show me all vessel-cargo combinations"})
        response, viz = process_query("heatmap")
        st.session_state.messages.append({"role": "assistant", "content": response, "viz": viz, "id": st.session_state.chat_counter})
        st.rerun()
    
    if st.button("📉 Bunker Sensitivity", use_container_width=True):
        st.session_state.chat_counter += 1
        st.session_state.messages.append({"role": "user", "content": "Show bunker price sensitivity"})
        response, viz = process_query("sensitivity")
        st.session_state.messages.append({"role": "assistant", "content": response, "viz": viz, "id": st.session_state.chat_counter})
        st.rerun()
    
    st.divider()
    
    st.markdown("### 📦 Data Explorer")
    
    if st.button("🚢 Show All Vessels", use_container_width=True):
        st.session_state.chat_counter += 1
        st.session_state.messages.append({"role": "user", "content": "Show all vessels"})
        response, viz = process_query("all vessels fleet")
        st.session_state.messages.append({"role": "assistant", "content": response, "viz": viz, "id": st.session_state.chat_counter})
        st.rerun()
    
    if st.button("📦 Show All Cargoes", use_container_width=True):
        st.session_state.chat_counter += 1
        st.session_state.messages.append({"role": "user", "content": "Show all cargoes"})
        response, viz = process_query("all cargoes")
        st.session_state.messages.append({"role": "assistant", "content": response, "viz": viz, "id": st.session_state.chat_counter})
        st.rerun()
    
    st.divider()
    
    st.markdown("### 💬 Chat History")
    
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_counter = 0
        st.session_state.scenario_applied = False
        st.rerun()
    
    st.caption(f"Messages: {len(st.session_state.messages)}")
    
    st.divider()
    
    if st.session_state.scenario_applied:
        st.caption(f"**Current Prices:**")
        st.caption(f"VLSFO: ${st.session_state.current_vlsfo:.0f}/MT")
        st.caption(f"MGO: ${st.session_state.current_mgo:.0f}/MT")
        if st.session_state.current_port_delay > 0:
            st.caption(f"Port Delay: +{st.session_state.current_port_delay} days")
    else:
        st.caption("*Apply a scenario to begin*")

# Display chat messages
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"], unsafe_allow_html=True)
        if message.get("viz") is not None:
            msg_id = message.get("id", idx)
            st.plotly_chart(message["viz"], use_container_width=True, key=f"viz_{msg_id}_{idx}")

# Chat input
if prompt := st.chat_input("Ask about voyage recommendations..."):
    st.session_state.chat_counter += 1
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    response, viz = process_query(prompt)
    st.session_state.messages.append({"role": "assistant", "content": response, "viz": viz, "id": st.session_state.chat_counter})
    with st.chat_message("assistant"):
        st.markdown(response, unsafe_allow_html=True)
        if viz is not None:
            st.plotly_chart(viz, use_container_width=True, key=f"new_viz_{st.session_state.chat_counter}")

# Show welcome message if no messages and no scenario applied
if not st.session_state.messages and not st.session_state.scenario_applied:
    st.markdown("""
    <div class="welcome-box">
    <h3>👋 Welcome to Cargill Voyage Assistant!</h3>
    <p>This tool helps you optimize vessel-cargo allocation and analyze different scenarios.</p>
    <br>
    <strong>To get started:</strong>
    <ol>
        <li>Set your <strong>Bunker Price Change</strong> and <strong>Port Delay</strong> assumptions in the sidebar</li>
        <li>Click <strong>"Apply Scenario"</strong> to calculate optimal allocation</li>
        <li>Use <strong>Quick Actions</strong> to explore recommendations, heatmaps, and sensitivity analysis</li>
    </ol>
    <br>
    <p>💡 <em>You can also type questions in the chat box below!</em></p>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# FOOTER
# =============================================================================

st.divider()
st.caption("Cargill-SMU Datathon 2026 | Team Sirius | Powered by Streamlit & Plotly")
