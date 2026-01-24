"""
Voyage Recommendation Chatbot for Cargill-SMU Datathon 2026
===========================================================
A Streamlit-based chatbot that displays REAL optimization results
and supports what-if scenarios with actual recalculations.

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
import itertools

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# =============================================================================
# IMPORT DATA AND FUNCTIONS
# =============================================================================

try:
    from data_loader import load_all_data, get_distance
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
# CORE CALCULATION FUNCTIONS (Embedded for chatbot)
# =============================================================================

def calculate_voyage_profit(vessel: pd.Series, cargo: pd.Series, 
                            distance_lookup: dict,
                            vlsfo_price: float = 490.0,
                            mgo_price: float = 650.0,
                            use_eco_speed: bool = True,
                            weather_margin: float = 0.05,
                            extra_port_days: int = 0) -> dict:
    """Calculate voyage profit for a vessel-cargo combination."""
    
    # Get distances
    dist_ballast = get_distance(vessel['current_port'], cargo['load_port'], distance_lookup)
    dist_laden = get_distance(cargo['load_port'], cargo['discharge_port'], distance_lookup)
    
    if dist_ballast is None or dist_laden is None:
        return {
            "vessel": vessel['vessel_name'],
            "cargo": cargo['cargo_id'],
            "is_feasible": False,
            "feasibility_notes": "Distance not found",
            "profit": -999999999,
            "tce": -999999999
        }
    
    # Get speeds and consumption
    if use_eco_speed:
        speed_ballast = vessel['speed_ballast_eco']
        speed_laden = vessel['speed_laden_eco']
        cons_ballast = vessel['consumption_ballast_eco_vlsf']
        cons_laden = vessel['consumption_laden_eco_vlsf']
    else:
        speed_ballast = vessel['speed_ballast_warranted']
        speed_laden = vessel['speed_laden_warranted']
        cons_ballast = vessel['consumption_ballast_warranted_vlsf']
        cons_laden = vessel['consumption_laden_warranted_vlsf']
    
    mgo_cons = vessel['consumption_mgo_sea']
    port_cons = vessel['consumption_port_working_vlsf']
    
    # Calculate sea time (days)
    days_ballast = (dist_ballast / (speed_ballast * 24)) * (1 + weather_margin)
    days_laden = (dist_laden / (speed_laden * 24)) * (1 + weather_margin)
    
    # Calculate port time (days)
    cargo_qty = min(vessel['dwt'], cargo['quantity'] * 1.05)
    days_load = (cargo_qty / cargo['load_rate']) + (cargo['load_turn_time'] / 24) + 1
    days_discharge = (cargo_qty / cargo['discharge_rate']) + (cargo['discharge_turn_time'] / 24) + 1
    
    # Add extra port days from scenario
    days_load += extra_port_days / 2
    days_discharge += extra_port_days / 2
    
    total_days = days_ballast + days_laden + days_load + days_discharge
    
    # Check laycan feasibility
    arrival_date = vessel['etd'] + timedelta(days=days_ballast)
    is_feasible = arrival_date <= cargo['laycan_end']
    feasibility_notes = "Feasible" if is_feasible else f"Arrives {arrival_date.date()} > laycan {cargo['laycan_end'].date()}"
    
    # Calculate fuel consumption
    vlsfo_sea = (days_ballast * cons_ballast) + (days_laden * cons_laden)
    vlsfo_port = (days_load + days_discharge) * port_cons
    total_vlsfo = vlsfo_sea + vlsfo_port
    total_mgo = (days_ballast + days_laden) * mgo_cons
    
    # Calculate costs
    fuel_cost = (total_vlsfo * vlsfo_price) + (total_mgo * mgo_price)
    port_cost = cargo['port_cost_load'] + cargo['port_cost_discharge']
    
    # Calculate revenue
    gross_revenue = cargo_qty * cargo['freight_rate']
    commission = gross_revenue * (cargo['commission_pct'] / 100)
    
    # Calculate profit and TCE
    total_cost = fuel_cost + port_cost + commission
    net_profit = gross_revenue - total_cost
    tce = net_profit / total_days if total_days > 0 else 0
    
    return {
        "vessel": vessel['vessel_name'],
        "cargo": cargo['cargo_id'],
        "route": f"{cargo['load_port']} → {cargo['discharge_port']}",
        "is_feasible": is_feasible,
        "feasibility_notes": feasibility_notes,
        "dist_ballast": round(dist_ballast, 0),
        "dist_laden": round(dist_laden, 0),
        "total_days": round(total_days, 1),
        "cargo_qty": round(cargo_qty, 0),
        "revenue": round(gross_revenue, 0),
        "fuel_cost": round(fuel_cost, 0),
        "port_cost": round(port_cost, 0),
        "total_cost": round(total_cost, 0),
        "profit": round(net_profit, 0),
        "tce": round(tce, 0)
    }


def run_optimization(data: dict, vlsfo_price: float = 490.0, mgo_price: float = 650.0,
                     extra_port_days: int = 0) -> tuple:
    """
    Run portfolio optimization and return results.
    
    Key insight: Only ANN BELL and OCEAN HORIZON can meet laycans for all 3 cargoes.
    PACIFIC GLORY and GOLDEN ASCENT are too late due to their ETDs.
    Therefore, we must outsource 1 cargo to a market charter.
    """
    
    vessels_df = data['vessels']
    cargoes_df = data['cargoes']
    distance_lookup = data['distance_lookup']
    
    cargill_vessels = vessels_df[vessels_df['vessel_type'] == 'cargill'].reset_index(drop=True)
    cargill_cargoes = cargoes_df[cargoes_df['cargo_type'] == 'cargill'].reset_index(drop=True)
    
    best_profit = -float('inf')
    best_allocation = []
    
    # Identify feasible vessels (those that can meet at least one laycan)
    feasible_vessel_names = ['ANN BELL', 'OCEAN HORIZON']  # Based on ETD analysis
    feasible_vessels = cargill_vessels[cargill_vessels['vessel_name'].isin(feasible_vessel_names)].reset_index(drop=True)
    unfeasible_vessels = cargill_vessels[~cargill_vessels['vessel_name'].isin(feasible_vessel_names)].reset_index(drop=True)
    
    n_feasible = len(feasible_vessels)
    n_cargoes = len(cargill_cargoes)
    
    # Try all combinations: 2 feasible vessels carry 2 cargoes, 1 cargo outsourced
    from itertools import combinations, permutations
    
    for cargo_pair in combinations(range(n_cargoes), n_feasible):
        for vessel_perm in permutations(range(n_feasible)):
            current_profit = 0
            current_allocation = []
            all_feasible = True
            
            # Assign feasible vessels to selected cargoes
            for v_idx, c_idx in zip(vessel_perm, cargo_pair):
                vessel = feasible_vessels.iloc[v_idx]
                cargo = cargill_cargoes.iloc[c_idx]
                
                result = calculate_voyage_profit(
                    vessel, cargo, distance_lookup,
                    vlsfo_price=vlsfo_price,
                    mgo_price=mgo_price,
                    extra_port_days=extra_port_days
                )
                
                if result['is_feasible']:
                    current_profit += result['profit']
                else:
                    all_feasible = False
                    break
                
                current_allocation.append(result)
            
            if not all_feasible:
                continue
            
            # Outsource the remaining cargo
            outsourced_idx = [i for i in range(n_cargoes) if i not in cargo_pair][0]
            outsourced_cargo = cargill_cargoes.iloc[outsourced_idx]
            
            # Calculate outsourcing profit
            market_hire = 18454  # $/day (average market rate)
            dist_laden = get_distance(outsourced_cargo['load_port'], outsourced_cargo['discharge_port'], distance_lookup) or 10000
            total_days = (dist_laden / (12.5 * 24)) * 1.05 + 10  # Rough estimate with port time
            fuel_cost = total_days * 50 * vlsfo_price
            hire_cost = total_days * market_hire
            port_cost = outsourced_cargo['port_cost_load'] + outsourced_cargo['port_cost_discharge']
            revenue = outsourced_cargo['quantity'] * outsourced_cargo['freight_rate']
            outsource_profit = revenue - fuel_cost - hire_cost - port_cost
            
            current_profit += outsource_profit
            current_allocation.append({
                "vessel": "MARKET CHARTER",
                "cargo": outsourced_cargo['cargo_id'],
                "route": f"{outsourced_cargo['load_port']} → {outsourced_cargo['discharge_port']}",
                "is_feasible": True,
                "feasibility_notes": "Outsourced to market vessel",
                "profit": round(outsource_profit, 0),
                "tce": 0,
                "total_days": round(total_days, 1)
            })
            
            # Add unfeasible vessels as available for spot market
            for _, vessel in unfeasible_vessels.iterrows():
                current_allocation.append({
                    "vessel": vessel['vessel_name'],
                    "cargo": "SPOT MARKET",
                    "route": "Available for market cargo",
                    "is_feasible": True,
                    "feasibility_notes": "Seeking market cargo (ETD too late for committed cargoes)",
                    "profit": 0,
                    "tce": 0,
                    "total_days": 0
                })
            
            if current_profit > best_profit:
                best_profit = current_profit
                best_allocation = current_allocation
    
    return pd.DataFrame(best_allocation), best_profit


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
        results_df, total_profit = run_optimization(st.session_state.data)
        st.session_state.optimization_results = results_df
        st.session_state.total_profit = total_profit
        st.session_state.base_vlsfo = 490.0
        st.session_state.base_mgo = 650.0


# =============================================================================
# HELPER FUNCTIONS
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
        if row['vessel'] != "MARKET CHARTER":
            table_rows.append(
                f"| {row['vessel']} | {row['cargo']} | {row['route'][:25]} | ${row['tce']:,.0f}/day | ${row['profit']:,.0f} |"
            )
        else:
            table_rows.append(
                f"| {row['vessel']} | {row['cargo']} | {row['route'][:25]} | N/A | ${row['profit']:,.0f} |"
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
        assignment_text = f"""
**Recommended Assignment:** {a['cargo']}
- Route: {a['route']}
- TCE: ${a['tce']:,.0f}/day
- Voyage Profit: ${a['profit']:,.0f}
- Duration: {a['total_days']} days
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
    
    base_vlsfo = 490.0
    base_mgo = 650.0
    
    new_vlsfo = base_vlsfo * (1 + bunker_change_pct / 100)
    new_mgo = base_mgo * (1 + bunker_change_pct / 100)
    
    # Run optimization with new parameters
    new_results, new_profit = run_optimization(
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
        if row['vessel'] != "MARKET CHARTER":
            table_rows.append(
                f"| {row['vessel']} | {row['cargo']} | ${row['tce']:,.0f}/day | ${row['profit']:,.0f} |"
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
**Change:** ${profit_change:+,.0f} ({profit_change/baseline_profit*100:+.1f}%)

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
        avg_tce = results[results['vessel'] != 'MARKET CHARTER']['tce'].mean()
        return f"""
**TCE Summary:**

Average TCE across fleet: **${avg_tce:,.0f}/day**

Individual vessel TCEs:
{results[results['vessel'] != 'MARKET CHARTER'][['vessel', 'cargo', 'tce']].to_markdown(index=False)}
"""
    
    # Profit queries
    if 'profit' in query_lower:
        return f"""
**Portfolio Profit Summary:**

Total Portfolio Profit: **${st.session_state.total_profit:,.0f}**

Breakdown by voyage:
{st.session_state.optimization_results[['vessel', 'cargo', 'profit']].to_markdown(index=False)}
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
st.caption("Cargill-SMU Datathon 2026 | Team [Your Team Name]")


