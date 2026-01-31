"""
Voyage Recommendation Chatbot for Cargill-SMU Datathon 2026
===========================================================
A Streamlit-based chatbot that displays REAL optimization results
and supports what-if scenarios with actual recalculations.

ENHANCED: LP-based optimization with 15 vessels × 11 cargoes
NEW: "Better options" analysis, detailed voyage calculations, threshold analysis
NEW: Cargill vs Market comparison with breakeven thresholds

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
    from lp_optimizer import FleetOptimizer, VoyageResult
    DATA_LOADED = True
    LP_AVAILABLE = True
except ImportError as e:
    DATA_LOADED = False
    LP_AVAILABLE = False
    IMPORT_ERROR = str(e)

# =============================================================================
# AI-ENHANCED MODE (Optional Featherless.ai Integration)
# =============================================================================

try:
    from ai_assistant import (
        check_api_available,
        get_ai_response,
        format_ai_response,
        process_with_ai_enhancement,
        process_freeform_query,
        AI_LIMITATIONS
    )
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    AI_LIMITATIONS = ""

# =============================================================================
# PAGE CONFIG & CARGILL STYLING
# =============================================================================

st.set_page_config(
    page_title="Cargill Voyage Assistant",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    .scenario-box {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border-left: 4px solid #d97706;
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 0 8px 8px 0;
        color: #92400e;
        font-size: 0.85rem;
    }
    .better-option-box {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
        border-left: 4px solid #2563eb;
        padding: 16px 20px;
        margin: 16px 0;
        border-radius: 0 12px 12px 0;
        color: #1e40af;
        font-size: 0.95rem;
        line-height: 1.6;
    }
    .warning-box {
        background: linear-gradient(135deg, #fef2f2 0%, #fecaca 100%);
        border-left: 4px solid #dc2626;
        padding: 16px 20px;
        margin: 16px 0;
        border-radius: 0 12px 12px 0;
        color: #991b1b;
        font-size: 0.95rem;
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
        font-size: 1.8rem;
        font-weight: 700;
    }
    .metric-label {
        font-size: 0.85rem;
        opacity: 0.9;
    }
    .welcome-box {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        border: 2px dashed #94a3b8;
        padding: 24px;
        margin: 16px 0;
        border-radius: 12px;
        color: #475569;
        text-align: center;
    }
    .calculation-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 16px;
        margin: 8px 0;
        border-radius: 8px;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
    }
    .threshold-box {
        background: linear-gradient(135deg, #faf5ff 0%, #ede9fe 100%);
        border-left: 4px solid #7c3aed;
        padding: 16px 20px;
        margin: 16px 0;
        border-radius: 0 12px 12px 0;
        color: #5b21b6;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# VISUALIZATION FUNCTIONS
# =============================================================================

def viz_tce_bar(tce_data: List[Dict], scenario_label: str = "") -> go.Figure:
    """Bar chart - TCE comparison for vessel-cargo pairs."""
    df = pd.DataFrame(tce_data)
    df['label'] = df['vessel'] + ' → ' + df['cargo']
    df = df.sort_values('tce', ascending=True)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df['tce'],
        y=df['label'],
        orientation='h',
        marker_color='#00843D',
        text=[f"${x:,.0f}" for x in df['tce']],
        textposition='outside'
    ))
    
    title = "TCE Comparison by Voyage"
    if scenario_label:
        title += f" ({scenario_label})"
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color='#00843D')),
        xaxis_title="TCE ($/day)",
        yaxis_title="",
        height=max(300, len(df) * 50),
        margin=dict(l=20, r=80, t=50, b=40)
    )
    return fig


def viz_heatmap(tce_data: List[Dict], scenario_label: str = "") -> go.Figure:
    """Heatmap - TCE matrix for all vessel-cargo combinations."""
    df = pd.DataFrame(tce_data)
    pivot = df.pivot(index='vessel', columns='cargo', values='tce').fillna(0)
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale='Greens',
        text=[[f"${v:,.0f}" if v > 0 else "$0" for v in row] for row in pivot.values],
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


def viz_strategy_comparison(strategies: Dict) -> go.Figure:
    """Bar chart comparing different fleet strategies."""
    names = list(strategies.keys())
    profits = [s['total_profit'] for s in strategies.values()]
    
    colors = ['#00843D' if p == max(profits) else '#94a3b8' for p in profits]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=names,
        y=profits,
        marker_color=colors,
        text=[f"${p:,.0f}" for p in profits],
        textposition='outside'
    ))
    
    fig.update_layout(
        title=dict(text="Strategy Comparison: Total Portfolio Profit", font=dict(size=18, color='#00843D')),
        xaxis_title="Strategy",
        yaxis_title="Total Profit ($)",
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
    df['Hire Rate'] = df['Hire Rate'].apply(lambda x: f"${x:,.0f}/day" if pd.notna(x) else "$18,454/day (Market)")
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
    st.session_state.base_vlsfo = VLSFO_PRICE
if 'base_mgo' not in st.session_state:
    st.session_state.base_mgo = MGO_PRICE
if 'current_vlsfo' not in st.session_state:
    st.session_state.current_vlsfo = VLSFO_PRICE
if 'current_mgo' not in st.session_state:
    st.session_state.current_mgo = MGO_PRICE
if 'current_port_delay' not in st.session_state:
    st.session_state.current_port_delay = 0
if 'lp_optimizer' not in st.session_state and LP_AVAILABLE:
    st.session_state.lp_optimizer = FleetOptimizer()
if 'message_counter' not in st.session_state:
    st.session_state.message_counter = 0


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_scenario_label() -> str:
    """Get human-readable scenario description."""
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


# =============================================================================
# DETAILED VOYAGE OUTPUT FUNCTIONS
# =============================================================================

def format_detailed_voyage(voyage: VoyageResult, show_calculation: bool = True) -> str:
    """Format a voyage result with full calculation details."""
    if not voyage.feasible:
        return f"""
❌ **{voyage.vessel} → {voyage.cargo}**: Not Feasible
   Reason: {voyage.infeasibility_reason}
"""
    
    output = f"""
### 📊 {voyage.vessel} → {voyage.cargo}

**Based on current freight rates, {voyage.vessel} should carry {voyage.cargo} for a TCE of ${voyage.tce:,.0f}/day.**

"""
    
    if show_calculation:
        output += f"""
<div class="calculation-box">
<strong>VOYAGE CALCULATION</strong>

Route: {voyage.load_port} → {voyage.discharge_port} ({voyage.distance_nm:,.0f} NM)
Sea Days: {voyage.sea_days:.1f} days | Port Days: {voyage.port_days:.1f} days
Total Voyage: {voyage.total_days:.1f} days (incl. 1 day bunkering + 5% weather margin)

Revenue:     ${voyage.revenue:>12,.0f}  ({voyage.quantity:,.0f} MT × ${voyage.freight_rate:.2f}/MT)
Hire Cost:   ${voyage.hire_cost:>12,.0f}  (${voyage.hire_rate:,.0f}/day × {voyage.total_days:.1f} days)
Bunker Cost: ${voyage.bunker_cost:>12,.0f}  (VLSFO ${st.session_state.current_vlsfo:.0f} + MGO ${st.session_state.current_mgo:.0f})
Port Cost:   ${voyage.port_cost:>12,.0f}
Commission:  ${voyage.commission:>12,.0f}  (3%)
─────────────────────────────────
Net Profit:  ${voyage.profit:>12,.0f}
TCE:         ${voyage.tce:>12,.0f}/day
</div>
"""
    
    return output


def format_comparison_output(cargill_result: Dict, mixed_result: Dict, improvements: List[Dict]) -> str:
    """Format the comparison between Cargill-only and mixed fleet strategies."""
    
    cargill_profit = cargill_result['total_profit']
    mixed_profit = mixed_result['total_profit']
    improvement = mixed_profit - cargill_profit
    improvement_pct = (improvement / cargill_profit * 100) if cargill_profit > 0 else 0
    
    output = f"""
<div class="better-option-box">
<strong>🔄 ALTERNATIVE OPTIONS ANALYSIS</strong><br><br>

<strong>Current Allocation (Cargill Fleet → Cargill Cargoes):</strong><br>
Total Profit: <strong>${cargill_profit:,.0f}</strong><br><br>

"""
    
    if improvement > 50000:  # Significant improvement threshold
        output += f"""
<strong>✅ BETTER OPTIONS FOUND!</strong><br><br>

<strong>Optimized Allocation (Mixed Fleet Strategy):</strong><br>
Total Profit: <strong>${mixed_profit:,.0f}</strong><br>
Improvement: <strong>${improvement:,.0f} (+{improvement_pct:.1f}%)</strong><br><br>

<strong>📈 SPECIFIC IMPROVEMENTS:</strong><br>
"""
        for imp in improvements:
            output += f"• <strong>{imp['cargo']}</strong>: Switch from {imp['from_vessel']} to {imp['to_vessel']}<br>"
            output += f"  TCE: ${imp['from_tce']:,.0f} → ${imp['to_tce']:,.0f} (+${imp['tce_gain']:,.0f}/day)<br>"
    else:
        output += """
<strong>✅ Current Cargill-only allocation is optimal or near-optimal.</strong><br>
Mixed fleet offers minimal improvement.
"""
    
    output += "</div>"
    return output


def format_threshold_analysis(voyage: VoyageResult) -> str:
    """Format threshold analysis for a voyage."""
    if not voyage.feasible or voyage.profit <= 0:
        return ""
    
    # Calculate breakeven thresholds
    daily_cost = voyage.hire_rate + (voyage.bunker_cost / voyage.total_days)
    port_delay_threshold = voyage.profit / daily_cost if daily_cost > 0 else 0
    
    # Bunker threshold (simplified)
    bunker_per_day = voyage.bunker_cost / voyage.total_days
    bunker_threshold_pct = (voyage.profit / voyage.bunker_cost) if voyage.bunker_cost > 0 else 0
    bunker_threshold_price = st.session_state.current_vlsfo * (1 + bunker_threshold_pct)
    
    return f"""
<div class="threshold-box">
<strong>📊 SENSITIVITY THRESHOLDS for {voyage.vessel} → {voyage.cargo}</strong><br><br>

• <strong>Port Delay Threshold:</strong> Voyage remains profitable if delays < <strong>{port_delay_threshold:.1f} days</strong><br>
• <strong>Bunker Price Threshold:</strong> Profitable if VLSFO stays below <strong>${bunker_threshold_price:.0f}/MT</strong><br><br>

<em>If bunker prices rise above ${bunker_threshold_price:.0f}/MT, consider alternative vessels or renegotiating freight rates.</em>
</div>
"""


def get_detailed_recommendations() -> Tuple[str, Any]:
    """Generate detailed voyage recommendations with full calculations."""
    results = st.session_state.optimization_results
    valid_results = results[results['profit'] > -999999]
    data = st.session_state.data
    vessels = data['vessels']
    cargoes = data['cargoes']
    
    scenario_label = get_scenario_label()
    
    output = f"""
<div class="info-box">
<strong>🎯 OPTIMAL PORTFOLIO ALLOCATION</strong><br><br>
Total Portfolio Profit: <strong>${st.session_state.total_profit:,.0f}</strong><br>
Scenario: <strong>{scenario_label}</strong>
</div>

---

## Assigned Voyages

"""
    
    assigned = valid_results[valid_results['cargo'] != 'SPOT MARKET']
    
    for _, row in assigned.iterrows():
        vessel_name = row['vessel']
        cargo_id = row['cargo']
        tce = row['tce']
        profit = row['profit']
        
        # Get vessel and cargo details
        vessel_info = vessels[vessels['vessel_name'] == vessel_name]
        cargo_info = cargoes[cargoes['cargo_id'] == cargo_id]
        
        if not vessel_info.empty and not cargo_info.empty:
            v = vessel_info.iloc[0]
            c = cargo_info.iloc[0]
            
            output += f"""
### 📊 {vessel_name} → {cargo_id}

**Based on current freight rates, {vessel_name} should carry {cargo_id} for the best TCE of ${tce:,.0f}/day.**

| Metric | Value |
|--------|-------|
| Route | {c['load_port']} → {c['discharge_port']} |
| Commodity | {c['commodity']} ({c['quantity']:,.0f} MT) |
| TCE | ${tce:,.0f}/day |
| Voyage Profit | ${profit:,.0f} |
| Vessel Type | {v['vessel_type'].title()} |

"""
    
    # Unassigned vessels
    unassigned = valid_results[valid_results['cargo'] == 'SPOT MARKET']
    if not unassigned.empty:
        output += """
---

## Unassigned Vessels (Seek Spot Market)

| Vessel | Current Position | Recommendation |
|--------|-----------------|----------------|
"""
        for _, row in unassigned.iterrows():
            vessel_name = row['vessel']
            vessel_info = vessels[vessels['vessel_name'] == vessel_name]
            if not vessel_info.empty:
                v = vessel_info.iloc[0]
                output += f"| {vessel_name} | {v['current_port']} | Position for spot market opportunities |\n"
    
    # Create visualization
    tce_data = [{'vessel': r['vessel'], 'cargo': r['cargo'], 'tce': r['tce']} 
                for _, r in assigned.iterrows()]
    viz = viz_tce_bar(tce_data, scenario_label) if tce_data else None
    
    return output, viz


def get_better_options_analysis() -> Tuple[str, Any]:
    """Analyze if there are better options using mixed fleet strategy."""
    if not LP_AVAILABLE:
        return "LP Optimizer not available.", None
    
    optimizer = st.session_state.lp_optimizer
    bunker_change = (st.session_state.current_vlsfo / st.session_state.base_vlsfo) - 1
    port_delay = st.session_state.current_port_delay
    
    # Run comparison
    comparison = optimizer.compare_strategies(
        bunker_price_change=bunker_change,
        additional_port_days=port_delay
    )
    
    cargill_only = comparison['strategies']['cargill_only']
    mixed_committed = comparison['strategies']['mixed_committed']
    
    # Find specific improvements
    improvements = []
    cargill_assignments = {a.cargo: a for a in cargill_only['assignments']}
    mixed_assignments = {a.cargo: a for a in mixed_committed['assignments']}
    
    for cargo_id, mixed_voyage in mixed_assignments.items():
        if cargo_id in cargill_assignments:
            cargill_voyage = cargill_assignments[cargo_id]
            if mixed_voyage.vessel != cargill_voyage.vessel and mixed_voyage.tce > cargill_voyage.tce:
                improvements.append({
                    'cargo': cargo_id,
                    'from_vessel': cargill_voyage.vessel,
                    'to_vessel': mixed_voyage.vessel,
                    'from_tce': cargill_voyage.tce,
                    'to_tce': mixed_voyage.tce,
                    'tce_gain': mixed_voyage.tce - cargill_voyage.tce
                })
    
    output = format_comparison_output(
        {'total_profit': cargill_only['total_profit']},
        {'total_profit': mixed_committed['total_profit']},
        improvements
    )
    
    # Add detailed voyage info for the best strategy
    best_strategy = comparison['best_strategy']
    best_result = comparison[best_strategy]
    
    output += "\n\n---\n\n## Detailed Voyage Calculations (Best Strategy)\n\n"
    
    for voyage in best_result['assignments'][:3]:  # Show top 3
        if voyage.feasible:
            output += f"""
### {voyage.vessel} → {voyage.cargo}

| Metric | Value |
|--------|-------|
| Route | {voyage.load_port} → {voyage.discharge_port} |
| Distance | {voyage.distance_nm:,.0f} NM |
| Sea Days | {voyage.sea_days:.1f} |
| Port Days | {voyage.port_days:.1f} |
| Total Days | {voyage.total_days:.1f} |
| Revenue | ${voyage.revenue:,.0f} |
| Bunker Cost | ${voyage.bunker_cost:,.0f} |
| TCE | ${voyage.tce:,.0f}/day |
| Profit | ${voyage.profit:,.0f} |

"""
            output += format_threshold_analysis(voyage)
    
    # Create strategy comparison chart
    strategies = {
        'Cargill Only': {'total_profit': cargill_only['total_profit']},
        'Mixed Fleet': {'total_profit': mixed_committed['total_profit']}
    }
    viz = viz_strategy_comparison(strategies)
    
    return output, viz


# =============================================================================
# QUERY PROCESSING
# =============================================================================

def process_query(query: str) -> Tuple[str, Any]:
    """Process user query and return response with optional visualization."""
    query_lower = query.lower()
    viz = None
    scenario_label = get_scenario_label()
    
    # Check if scenario has been applied
    if not st.session_state.scenario_applied and any(word in query_lower for word in 
        ['heatmap', 'matrix', 'recommend', 'optimal', 'sensitivity', 'tce', 'profit', 'better', 'option', 'compare']):
        return """
<div class="welcome-box">
⚠️ <strong>Please apply a scenario first!</strong><br><br>
Use the sidebar to set your bunker price and port delay assumptions, then click <strong>"Apply Scenario"</strong> to see results.
</div>
""", None
    
    # BETTER OPTIONS / COMPARISON QUERY (NEW!)
    if any(phrase in query_lower for phrase in ['better option', 'more profit', 'alternative', 'compare fleet', 
                                                  'market vessel', 'mixed fleet', 'cargill with cargill',
                                                  'is there a better', 'could we do better']):
        return get_better_options_analysis()
    
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
    if any(word in query_lower for word in ['heatmap', 'matrix', 'all combinations']):
        tce_data = get_all_tce_data_with_scenario()
        viz = viz_heatmap(tce_data, scenario_label)
        response = "Here's the TCE matrix showing all vessel-cargo combinations:"
        if scenario_label:
            response += f"\n\n*Using scenario: {scenario_label}*"
        return response, viz
    
    # Recommendation queries
    if any(word in query_lower for word in ['recommend', 'best', 'optimal', 'allocation', 'summary']):
        return get_detailed_recommendations()
    
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
        
        # Add threshold info
        for i, (price, profit) in enumerate(zip(prices, profits)):
            if profit <= 0 and i > 0:
                response += f"\n\n<div class='warning-box'>⚠️ <strong>Break-even threshold:</strong> Portfolio becomes unprofitable at VLSFO ~${prices[i-1]}/MT</div>"
                break
        
        return response, viz
    
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
    
    # Threshold queries
    if any(word in query_lower for word in ['threshold', 'breakeven', 'break-even', 'switch']):
        if LP_AVAILABLE:
            optimizer = st.session_state.lp_optimizer
            bunker_change = (st.session_state.current_vlsfo / st.session_state.base_vlsfo) - 1
            
            result = optimizer.optimize_cargill_only(
                bunker_price_change=bunker_change,
                additional_port_days=st.session_state.current_port_delay
            )
            
            output = """
<div class="threshold-box">
<strong>📊 SCENARIO THRESHOLDS</strong><br><br>
"""
            for voyage in result['assignments']:
                if voyage.feasible and voyage.profit > 0:
                    daily_cost = voyage.hire_rate + (voyage.bunker_cost / voyage.total_days)
                    port_threshold = voyage.profit / daily_cost if daily_cost > 0 else 0
                    bunker_threshold = st.session_state.current_vlsfo * (1 + voyage.profit / voyage.bunker_cost) if voyage.bunker_cost > 0 else 0
                    
                    output += f"""
<strong>{voyage.vessel} → {voyage.cargo}:</strong><br>
• Port delay threshold: <strong>{port_threshold:.1f} days</strong><br>
• Bunker price threshold: <strong>${bunker_threshold:.0f}/MT</strong><br><br>
"""
            output += "</div>"
            return output, None
        return "Threshold analysis requires LP optimizer.", None
    
    # Help / default
    return """
**🚢 I can help you with:**

1. **📊 Voyage Recommendations** - "What is the optimal allocation?"
2. **🔄 Better Options Analysis** - "Is there a better option?" or "Compare Cargill vs Market"
3. **🗺️ TCE Heatmap** - "Show me all combinations" 
4. **🚢 Fleet Overview** - "Show all vessels" (includes market vessels)
5. **📦 Cargo Overview** - "Show all cargoes" (includes market cargoes)
6. **💰 Profit Analysis** - "What is the total profit?"
7. **📈 TCE Analysis** - "What are the TCE values?"
8. **📉 Sensitivity Analysis** - "Show bunker sensitivity"
9. **⚡ Threshold Analysis** - "What are the breakeven thresholds?"

**NEW:** Ask "Given Cargill with Cargill cargo, would there be a better and more profitable option?" to compare fleet strategies!

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
        st.session_state.current_vlsfo = st.session_state.base_vlsfo
        st.session_state.current_mgo = st.session_state.base_mgo
        st.session_state.current_port_delay = 0
        st.session_state.scenario_applied = False
        
        results = optimize_portfolio(include_market_cargoes=False, verbose=False)
        st.session_state.optimization_results = results
        valid = results[results['profit'] > -999999]
        st.session_state.total_profit = valid['profit'].sum()
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": "✅ Reset to base scenario (VLSFO: $490/MT, no port delays)"
        })
        st.rerun()
    
    st.divider()
    
    # =============================================================================
    # AI-ENHANCED MODE TOGGLE
    # =============================================================================
    if AI_AVAILABLE:
        st.markdown("### 🤖 AI Mode")
        
        # Initialize AI mode state
        if 'ai_mode_enabled' not in st.session_state:
            st.session_state.ai_mode_enabled = False
        if 'ai_status_checked' not in st.session_state:
            st.session_state.ai_status_checked = False
        if 'ai_status_message' not in st.session_state:
            st.session_state.ai_status_message = ""
        
        # AI mode toggle
        ai_mode = st.toggle(
            "Enable AI-Enhanced Mode",
            value=st.session_state.ai_mode_enabled,
            key="ai_toggle",
            help="Use Featherless.ai for natural language responses"
        )
        
        if ai_mode != st.session_state.ai_mode_enabled:
            st.session_state.ai_mode_enabled = ai_mode
            if ai_mode:
                # Check API status when enabling
                with st.spinner("Checking AI connection..."):
                    available, message = check_api_available()
                    st.session_state.ai_status_checked = True
                    st.session_state.ai_status_message = message
                    if not available:
                        st.session_state.ai_mode_enabled = False
                        st.error(f"❌ {message}")
                    else:
                        st.success("✅ AI connected!")
            st.rerun()
        
        if st.session_state.ai_mode_enabled:
            st.markdown("""<div style="font-size: 0.8rem; color: #7c3aed; background: #ede9fe; padding: 8px; border-radius: 6px;">🤖 <strong>AI Mode Active</strong><br>Responses enhanced with Qwen-72B</div>""", unsafe_allow_html=True)
            
            # Show limitations expander
            with st.expander("⚠️ View AI Limitations", expanded=False):
                st.markdown("""
**AI-Enhanced Mode Limitations:**

1. **Accuracy**: AI may occasionally generate inaccurate information. Always verify critical numbers with the data.

2. **Latency**: API calls add 2-5 seconds to response time.

3. **Read-Only**: AI cannot modify optimization parameters or run new calculations.

4. **Rate Limits**: Heavy usage may hit API limits.

5. **Context Window**: AI has limited memory of conversation history.

6. **No Real-Time Data**: AI uses cached optimization results, not live market data.

**Recommendation**: Use AI Mode for exploration and explanations. Use Standard Mode for precise calculations.
                """)
        else:
            st.caption("Standard rule-based mode active")
        
        st.divider()
    
    # Portfolio Metrics in Sidebar
    if st.session_state.scenario_applied:
        valid = st.session_state.optimization_results[st.session_state.optimization_results['profit'] > -999999]
        assigned = len(valid[valid['cargo'] != 'SPOT MARKET'])
        avg_tce = valid[valid['cargo'] != 'SPOT MARKET']['tce'].mean() if not valid.empty else 0
        
        st.markdown("### 📈 Portfolio Metrics")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("💰 Profit", f"${st.session_state.total_profit:,.0f}")
        with col2:
            st.metric("🚢 Voyages", f"{assigned}")
        st.metric("📊 Avg TCE", f"${avg_tce:,.0f}/day")
        
        scenario_label = get_scenario_label()
        if scenario_label:
            st.info(f"📊 **Active:** {scenario_label}")
        
        st.divider()
    
    st.markdown("### ⚡ Quick Actions")
    
    if st.button("📋 Show Recommendations", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "Show recommendations"})
        response, viz = get_detailed_recommendations()
        msg = {"role": "assistant", "content": response}
        if viz:
            msg["viz"] = viz
        st.session_state.messages.append(msg)
        st.rerun()
    
    if st.button("🔄 Compare Fleet Options", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "Is there a better option with market vessels?"})
        response, viz = get_better_options_analysis()
        msg = {"role": "assistant", "content": response}
        if viz:
            msg["viz"] = viz
        st.session_state.messages.append(msg)
        st.rerun()
    
    if st.button("📊 Show TCE Heatmap", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "Show me all vessel-cargo combinations"})
        tce_data = get_all_tce_data_with_scenario()
        viz = viz_heatmap(tce_data, get_scenario_label())
        st.session_state.messages.append({
            "role": "assistant", 
            "content": "Here's the TCE matrix showing all vessel-cargo combinations:",
            "viz": viz
        })
        st.rerun()
    
    if st.button("📈 Bunker Sensitivity", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "Show bunker price sensitivity"})
        response, viz = process_query("sensitivity")
        msg = {"role": "assistant", "content": response}
        if viz:
            msg["viz"] = viz
        st.session_state.messages.append(msg)
        st.rerun()
    
    st.divider()
    
    st.markdown("### 📦 Data Explorer")
    
    if st.button("🚢 Show All Vessels", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "Show all vessels"})
        data = st.session_state.data
        viz = viz_vessel_table(data['vessels'], 'all')
        st.session_state.messages.append({
            "role": "assistant", 
            "content": "Here's the complete fleet overview (Cargill + Market vessels):",
            "viz": viz
        })
        st.rerun()
    
    if st.button("📦 Show All Cargoes", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "Show all cargoes"})
        data = st.session_state.data
        viz = viz_cargo_table(data['cargoes'], 'all')
        st.session_state.messages.append({
            "role": "assistant", 
            "content": "Here's the complete cargo overview (Cargill + Market cargoes):",
            "viz": viz
        })
        st.rerun()
    
    st.divider()
    
    st.markdown("### 💬 Chat History")
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.scenario_applied = False
        st.session_state.message_counter = 0
        st.rerun()
    
    st.caption(f"Messages: {len(st.session_state.messages)}")


# Main chat area
if not st.session_state.messages:
    st.markdown("""
<div class="welcome-box">
<h3>👋 Welcome to Cargill Voyage Assistant!</h3>
<p>I help you optimize vessel-cargo allocation and analyze voyage profitability.</p>
<br>
<strong>To get started:</strong><br>
1. Set your scenario parameters in the sidebar (bunker price, port delays)<br>
2. Click <strong>"Apply Scenario"</strong><br>
3. Use Quick Actions or ask me questions!<br>
<br>
<strong>💡 Try asking:</strong> "Is there a better option with market vessels?"
</div>
""", unsafe_allow_html=True)

# Display chat messages
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"], unsafe_allow_html=True)
        if "viz" in message and message["viz"] is not None:
            st.session_state.message_counter += 1
            st.plotly_chart(message["viz"], use_container_width=True, key=f"chat_viz_{idx}_{st.session_state.message_counter}")

# Chat input
if prompt := st.chat_input("Ask about voyage recommendations..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Check if AI mode is enabled
    use_ai_mode = AI_AVAILABLE and st.session_state.get('ai_mode_enabled', False)
    
    if use_ai_mode:
        # AI-Enhanced Mode: Combine rule-based + AI
        with st.spinner("🤖 AI is thinking..."):
            # First get rule-based response for accuracy
            rule_response, viz = process_query(prompt)
            
            # Check if rule-based gave a meaningful response (not just help text)
            is_help_response = "I can help you with" in rule_response
            
            if is_help_response:
                # Freeform query - let AI handle it
                response, viz = process_freeform_query(
                    prompt, 
                    st.session_state,
                    st.session_state.messages
                )
            else:
                # Enhance rule-based response with AI summary
                response, viz = process_with_ai_enhancement(
                    prompt,
                    rule_response,
                    viz,
                    st.session_state
                )
    else:
        # Standard rule-based mode
        response, viz = process_query(prompt)
    
    msg = {"role": "assistant", "content": response}
    if viz:
        msg["viz"] = viz
    st.session_state.messages.append(msg)
    
    with st.chat_message("assistant"):
        st.markdown(response, unsafe_allow_html=True)
        if viz:
            st.session_state.message_counter += 1
            st.plotly_chart(viz, use_container_width=True, key=f"response_viz_{st.session_state.message_counter}")

# Footer
st.divider()
if AI_AVAILABLE and st.session_state.get('ai_mode_enabled', False):
    st.caption("Cargill-SMU Datathon 2026 | Team Sirius | Powered by Streamlit, OR-Tools & Featherless.ai")
else:
    st.caption("Cargill-SMU Datathon 2026 | Team Sirius | Powered by Streamlit & OR-Tools")
