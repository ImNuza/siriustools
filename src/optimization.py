"""
Portfolio Optimization Engine for Cargill-SMU Datathon 2026
============================================================
Optimizes vessel-cargo allocation to maximize total portfolio profit.

Now uses data_loader.py for accurate vessel/cargo data from PPTX.

Author: Team Sirius
Date: January 2026
"""

import pandas as pd
import numpy as np
import itertools
from datetime import timedelta
from pathlib import Path

# Import data loader
import sys
sys.path.insert(0, str(Path(__file__).parent))
from data_loader import load_all_data, get_distance

# =============================================================================
# LOAD DATA FROM DATA_LOADER (Correct values from PPTX)
# =============================================================================

print("Loading data from data_loader...")
DATA = load_all_data()

# Extract dataframes
VESSELS_DF = DATA['vessels']
CARGOES_DF = DATA['cargoes']
DISTANCE_LOOKUP = DATA['distance_lookup']
BUNKER_PRICES = DATA['bunker_prices']

# Get bunker prices (Singapore as default)
VLSFO_PRICE = BUNKER_PRICES[BUNKER_PRICES['location'] == 'SINGAPORE']['vlsfo'].values[0]
MGO_PRICE = BUNKER_PRICES[BUNKER_PRICES['location'] == 'SINGAPORE']['mgo'].values[0]

print(f"VLSFO Price: ${VLSFO_PRICE}/MT")
print(f"MGO Price: ${MGO_PRICE}/MT")

# =============================================================================
# CALCULATION FUNCTIONS
# =============================================================================

def calculate_voyage_profit(vessel: pd.Series, cargo: pd.Series, 
                            use_eco_speed: bool = True,
                            weather_margin: float = 0.05,
                            extra_port_days: int = 0) -> dict:
    """
    Calculate voyage profit for a vessel-cargo combination.
    
    Args:
        vessel: Series from vessels DataFrame
        cargo: Series from cargoes DataFrame
        use_eco_speed: Use economical speed (True) or warranted speed (False)
        weather_margin: Additional time buffer for weather (default 5%)
        extra_port_days: Additional port waiting days for scenario analysis (default 0)
    
    Returns:
        Dictionary with voyage results
    """
    
    # 1. Get distances
    dist_ballast = get_distance(vessel['current_port'], cargo['load_port'], DISTANCE_LOOKUP)
    dist_laden = get_distance(cargo['load_port'], cargo['discharge_port'], DISTANCE_LOOKUP)
    
    if dist_ballast is None or dist_laden is None:
        return {
            "vessel": vessel['vessel_name'],
            "cargo": cargo['cargo_id'],
            "route": f"{cargo['load_port']} -> {cargo['discharge_port']}",
            "is_feasible": False,
            "feasibility_notes": f"Distance not found for route",
            "profit": -999999999,
            "tce": -999999999
        }
    
    # Check if freight rate is valid (market cargoes have NaN)
    if pd.isna(cargo['freight_rate']):
        return {
            "vessel": vessel['vessel_name'],
            "cargo": cargo['cargo_id'],
            "route": f"{cargo['load_port']} -> {cargo['discharge_port']}",
            "is_feasible": False,
            "feasibility_notes": "No freight rate (market cargo for bidding)",
            "profit": -999999999,
            "tce": -999999999
        }
    
    # 2. Get speeds and consumption based on mode
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
    
    # 3. Calculate sea time (days)
    days_ballast = (dist_ballast / (speed_ballast * 24)) * (1 + weather_margin)
    days_laden = (dist_laden / (speed_laden * 24)) * (1 + weather_margin)
    
    # 4. Calculate port time (days)
    cargo_qty = min(vessel['dwt'], cargo['quantity'] * 1.05)  # Max within 5% tolerance
    
    days_load = (cargo_qty / cargo['load_rate']) + (cargo['load_turn_time'] / 24)
    days_discharge = (cargo_qty / cargo['discharge_rate']) + (cargo['discharge_turn_time'] / 24)
    
    # Add 1 day buffer at each port for waiting
    days_load += 1
    days_discharge += 1
    
    # Add extra port days from scenario analysis (split between load and discharge)
    days_load += extra_port_days / 2
    days_discharge += extra_port_days / 2
    
    total_days = days_ballast + days_laden + days_load + days_discharge
    
    # 5. Check laycan feasibility
    arrival_date = vessel['etd'] + timedelta(days=days_ballast)
    is_feasible = arrival_date <= cargo['laycan_end']
    feasibility_notes = "Feasible" if is_feasible else f"Arrives {arrival_date.date()} > laycan end {cargo['laycan_end'].date()}"
    
    # 6. Calculate fuel consumption
    vlsfo_sea = (days_ballast * cons_ballast) + (days_laden * cons_laden)
    vlsfo_port = (days_load + days_discharge) * port_cons
    total_vlsfo = vlsfo_sea + vlsfo_port
    
    total_mgo = (days_ballast + days_laden) * mgo_cons
    
    # 7. Calculate costs
    fuel_cost = (total_vlsfo * VLSFO_PRICE) + (total_mgo * MGO_PRICE)
    port_cost = cargo['port_cost_load'] + cargo['port_cost_discharge']
    
    # 8. Calculate revenue
    gross_revenue = cargo_qty * cargo['freight_rate']
    commission = gross_revenue * (cargo['commission_pct'] / 100)
    
    # 9. Calculate profit and TCE
    total_cost = fuel_cost + port_cost + commission
    net_profit = gross_revenue - total_cost
    tce = net_profit / total_days if total_days > 0 else 0
    
    return {
        "vessel": vessel['vessel_name'],
        "vessel_type": vessel['vessel_type'],
        "cargo": cargo['cargo_id'],
        "cargo_type": cargo['cargo_type'],
        "route": f"{cargo['load_port']} -> {cargo['discharge_port']}",
        "is_feasible": is_feasible,
        "feasibility_notes": feasibility_notes,
        "dist_ballast": round(dist_ballast, 0),
        "dist_laden": round(dist_laden, 0),
        "days_ballast": round(days_ballast, 1),
        "days_laden": round(days_laden, 1),
        "days_port": round(days_load + days_discharge, 1),
        "total_days": round(total_days, 1),
        "cargo_qty": round(cargo_qty, 0),
        "revenue": round(gross_revenue, 0),
        "fuel_cost": round(fuel_cost, 0),
        "port_cost": round(port_cost, 0),
        "commission": round(commission, 0),
        "total_cost": round(total_cost, 0),
        "profit": round(net_profit, 0),
        "tce": round(tce, 0)
    }


def estimate_market_charter_cost(cargo: pd.Series) -> float:
    """
    Estimate cost to outsource a cargo to a market vessel.
    Used when a committed cargo cannot be carried by Cargill fleet.
    """
    # Use average market vessel profile
    avg_speed = 12.5  # Eco speed
    avg_cons = 50.0   # MT/day
    market_hire = 18454  # Baltic 5TC rate from PPTX
    
    # Assume ballast from Singapore (major hub)
    dist_ballast = get_distance('SINGAPORE', cargo['load_port'], DISTANCE_LOOKUP) or 3000
    dist_laden = get_distance(cargo['load_port'], cargo['discharge_port'], DISTANCE_LOOKUP) or 5000
    
    total_days = ((dist_ballast + dist_laden) / (avg_speed * 24)) + 7  # +7 port days
    
    fuel_cost = total_days * avg_cons * VLSFO_PRICE
    hire_cost = total_days * market_hire
    port_cost = cargo['port_cost_load'] + cargo['port_cost_discharge']
    
    total_outsource_cost = fuel_cost + hire_cost + port_cost
    
    # Revenue is still ours, but we pay the charter
    revenue = cargo['quantity'] * cargo['freight_rate']
    return revenue - total_outsource_cost


# =============================================================================
# OPTIMIZATION ENGINE
# =============================================================================

def optimize_portfolio(include_market_cargoes: bool = True, 
                       verbose: bool = True,
                       extra_port_days: int = 0) -> pd.DataFrame:
    """
    Find optimal vessel-cargo allocation to maximize portfolio profit.
    
    Strategy:
    1. Generate all permutations of cargoes for our 4 vessels
    2. Calculate P&L for each allocation
    3. For unassigned committed cargoes, add outsourcing cost
    4. Return the allocation with maximum total profit
    
    Args:
        include_market_cargoes: Whether to consider market cargoes
        verbose: Print progress and results
        extra_port_days: Additional port waiting days for scenario analysis (default 0)
    
    Returns:
        DataFrame with optimal allocation details
    """
    if verbose:
        print("\n" + "="*60)
        print("PORTFOLIO OPTIMIZATION")
        print("="*60)
    
    # Get Cargill vessels only
    cargill_vessels = VESSELS_DF[VESSELS_DF['vessel_type'] == 'cargill'].reset_index(drop=True)
    
    # Get cargoes
    cargill_cargoes = CARGOES_DF[CARGOES_DF['cargo_type'] == 'cargill'].reset_index(drop=True)
    
    if include_market_cargoes:
        market_cargoes = CARGOES_DF[CARGOES_DF['cargo_type'] == 'market'].reset_index(drop=True)
        all_cargoes = pd.concat([cargill_cargoes, market_cargoes], ignore_index=True)
    else:
        all_cargoes = cargill_cargoes
    
    if verbose:
        print(f"\nVessels: {len(cargill_vessels)} Cargill vessels")
        print(f"Cargoes: {len(cargill_cargoes)} committed + {len(all_cargoes) - len(cargill_cargoes)} market")
    
    n_vessels = len(cargill_vessels)
    n_cargoes = len(all_cargoes)
    
    best_profit = -float('inf')
    best_allocation = []
    
    # Handle case where we have fewer cargoes than vessels
    # We need to try all combinations of which vessels carry which cargoes
    cargo_indices = list(range(n_cargoes))
    vessel_indices = list(range(n_vessels))
    
    # If fewer cargoes than vessels, we assign all cargoes to some vessels
    # and leave other vessels for spot market
    from itertools import combinations
    
    n_to_assign = min(n_vessels, n_cargoes)
    
    for vessel_combo in combinations(vessel_indices, n_to_assign):
        for cargo_perm in itertools.permutations(cargo_indices, n_to_assign):
            current_profit = 0
            current_allocation = []
            
            # A. Calculate profit for each vessel-cargo pair in this combination
            for i, (v_idx, c_idx) in enumerate(zip(vessel_combo, cargo_perm)):
                vessel = cargill_vessels.iloc[v_idx]
                cargo = all_cargoes.iloc[c_idx]
                
                result = calculate_voyage_profit(vessel, cargo, extra_port_days=extra_port_days)
                
                # Only count feasible voyages
                if result['is_feasible']:
                    current_profit += result['profit']
                else:
                    current_profit += -1000000  # Heavy penalty for infeasible
                
                current_allocation.append(result)
            
            # B. Add vessels not assigned to any cargo (available for spot market)
            for v_idx in vessel_indices:
                if v_idx not in vessel_combo:
                    vessel = cargill_vessels.iloc[v_idx]
                    current_allocation.append({
                        "vessel": vessel['vessel_name'],
                        "cargo": "SPOT MARKET",
                        "route": "Available for market cargo",
                        "is_feasible": True,
                        "feasibility_notes": "Seeking market cargo",
                        "profit": 0,
                        "tce": 0,
                        "total_days": 0
                    })
            
            # C. Handle unassigned committed cargoes (must outsource)
            assigned_cargo_ids = [all_cargoes.iloc[idx]['cargo_id'] for idx in cargo_perm]
            
            for _, comm_cargo in cargill_cargoes.iterrows():
                if comm_cargo['cargo_id'] not in assigned_cargo_ids:
                    outsource_profit = estimate_market_charter_cost(comm_cargo)
                    current_profit += outsource_profit
                    current_allocation.append({
                        "vessel": "MARKET CHARTER",
                        "cargo": comm_cargo['cargo_id'],
                        "route": f"{comm_cargo['load_port']} -> {comm_cargo['discharge_port']}",
                        "is_feasible": True,
                        "feasibility_notes": "Outsourced to market vessel",
                        "profit": round(outsource_profit, 0),
                        "tce": 0,
                        "total_days": 0
                    })
            
            # D. Update best if this is better
            if current_profit > best_profit:
                best_profit = current_profit
                best_allocation = current_allocation
    
    # Convert to DataFrame
    results_df = pd.DataFrame(best_allocation)
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"OPTIMAL ALLOCATION - Total Profit: ${best_profit:,.0f}")
        print(f"{'='*60}")
        print(f"\n{'VESSEL':<18} | {'CARGO':<12} | {'ROUTE':<30} | {'PROFIT':>12} | {'TCE':>10}")
        print("-"*90)
        
        for _, row in results_df.iterrows():
            # Handle case where route might be NaN (float)
            route_val = row.get('route', 'N/A')
            if isinstance(route_val, float) or route_val is None:
                route = 'N/A'
            else:
                route = str(route_val)[:28]
            
            # Handle case where tce might be NaN
            tce_val = row.get('tce', 0)
            if pd.isna(tce_val):
                tce_val = 0
            
            print(f"{row['vessel']:<18} | {row['cargo']:<12} | {route:<30} | ${row['profit']:>10,.0f} | ${tce_val:>8,.0f}")
        
        print("-"*90)
        print(f"{'TOTAL':<18} | {'':<12} | {'':<30} | ${best_profit:>10,.0f} |")
    
    return results_df


# =============================================================================
# SCENARIO ANALYSIS
# =============================================================================

def bunker_sensitivity_analysis(price_range: tuple = (0.8, 1.3), steps: int = 10):
    """
    Analyze how bunker price changes affect the optimal allocation.
    """
    global VLSFO_PRICE, MGO_PRICE
    
    original_vlsfo = VLSFO_PRICE
    original_mgo = MGO_PRICE
    
    print("\n" + "="*60)
    print("BUNKER PRICE SENSITIVITY ANALYSIS")
    print("="*60)
    
    results = []
    
    for mult in np.linspace(price_range[0], price_range[1], steps):
        VLSFO_PRICE = original_vlsfo * mult
        MGO_PRICE = original_mgo * mult
        
        allocation = optimize_portfolio(verbose=False)
        total_profit = allocation['profit'].sum()
        
        results.append({
            'multiplier': mult,
            'vlsfo_price': VLSFO_PRICE,
            'total_profit': total_profit,
            'allocation': allocation['cargo'].tolist()
        })
        
        print(f"VLSFO ${VLSFO_PRICE:.0f}/MT ({mult:.0%}): Profit ${total_profit:,.0f}")
    
    # Restore original prices
    VLSFO_PRICE = original_vlsfo
    MGO_PRICE = original_mgo
    
    return pd.DataFrame(results)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Run optimization
    optimal = optimize_portfolio(include_market_cargoes=True, verbose=True)
    
    # Show detailed breakdown
    print("\n\nDETAILED VOYAGE BREAKDOWN:")
    print("="*60)
    
    for _, row in optimal.iterrows():
        if row['vessel'] != "MARKET CHARTER":
            print(f"\n{row['vessel']} -> {row['cargo']}")
            print(f"  Route: {row.get('route', 'N/A')}")
            print(f"  Feasible: {row['is_feasible']} ({row.get('feasibility_notes', '')})")
            print(f"  Distance: {row.get('dist_ballast', 0):,.0f} nm (ballast) + {row.get('dist_laden', 0):,.0f} nm (laden)")
            print(f"  Duration: {row.get('total_days', 0):.1f} days")
            print(f"  Revenue: ${row.get('revenue', 0):,.0f}")
            print(f"  Costs: ${row.get('total_cost', 0):,.0f} (fuel: ${row.get('fuel_cost', 0):,.0f}, port: ${row.get('port_cost', 0):,.0f})")
            print(f"  Profit: ${row['profit']:,.0f}")
            print(f"  TCE: ${row.get('tce', 0):,.0f}/day")
    
    # Uncomment to run sensitivity analysis
    # bunker_sensitivity_analysis()
