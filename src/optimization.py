import pandas as pd
import itertools
from freight_calculator import Vessel, Cargo, calculate_voyage_profit, get_distance

# --- 1. DATA SETUP (Based on PPTX Sources 103-421) ---

# Load Distances (Assuming CSV is in same dir)
# You must ensure 'Port Distances.csv' is accessible
try:
    dist_df = pd.read_csv('Port Distances.csv')
except:
    dist_df = pd.DataFrame(columns=['PORT_NAME_FROM', 'PORT_NAME_TO', 'DISTANCE'])
    print("WARNING: Distances CSV not found. Distances will default to 0/Safety.")

# Current Market Bunker Prices (Approx from PPTX Forward Curves Source 505)
VLSFO_PRICE = 490.0
MGO_PRICE = 650.0

# CARGILL FLEET
fleet = [
    Vessel("Ann Bell", 180803, 13.5, 14.5, 60.0, 2.0, 55.0, 2.0, 2.0, 3.0, "Qingdao", "2026-02-25"),
    Vessel("Ocean Horizon", 181550, 13.8, 14.8, 61.0, 1.8, 56.5, 1.8, 1.8, 3.2, "Map Ta Phut", "2026-03-01"),
    Vessel("Pacific Glory", 182320, 13.5, 14.2, 59.0, 1.9, 54.0, 1.9, 2.0, 3.0, "Gwangyang", "2026-03-10"),
    Vessel("Golden Ascent", 179965, 13.0, 14.0, 58.0, 2.0, 53.0, 2.0, 1.9, 3.1, "Fangcheng", "2026-03-08")
]

# CARGILL COMMITTED CARGOES (Must be moved)
# Note: For optimization, we treat these as "Jobs".
committed_cargoes = [
    Cargo("EGA Bauxite", 180000, "Kamsar", "Qingdao", 30000, 25000, 23.00, 0.5, 0.5, 0, 0, 0.0125, "2026-04-02"),
    Cargo("BHP Iron Ore", 160000, "Port Hedland", "Lianyungang", 80000, 30000, 9.00, 0.5, 1.0, 260000, 120000, 0.0375, "2026-03-07"),
    Cargo("CSN Iron Ore", 180000, "Itaguai", "Qingdao", 60000, 30000, 22.30, 0.25, 1.0, 75000, 90000, 0.0375, "2026-04-01")
]

# MARKET CARGOES (Optional - Opportunity to boost profit)
market_cargoes = [
    Cargo("Rio Tinto Iron", 170000, "Dampier", "Qingdao", 80000, 30000, 10.50, 0.5, 1.0, 240000, 0, 0.0375, "2026-03-12", is_committed=False),
    Cargo("Vale Iron", 190000, "Ponta da Madeira", "Caofeidian", 60000, 30000, 21.50, 0.5, 1.0, 75000, 95000, 0.0375, "2026-04-03", is_committed=False),
    # Add more market cargoes from PPTX here...
]

# MARKET VESSELS (Can be hired to cover Committed Cargoes)
# Simplified: We treat hiring a market vessel as a "Cost" to cover a commitment.
# We estimate the cost to charter a market vessel for a specific route.
# For simplicity in this logic, we assume we can charter a market vessel at a generic daily rate + fuel 
# OR use the specific "Market Vessels" list in PPTX and calculate their specific cost.
# Here, I'll use a simplified 'Spot Charter Cost' estimator function.

def estimate_market_charter_cost(cargo, distance_df):
    """
    Estimates cost to outsource a cargo to a third-party market vessel.
    This is effectively Negative Profit (Cost).
    """
    # Use an average Market Vessel profile (Reference PPTX "Atlantic Fortune")
    avg_speed = 13.0
    avg_cons = 45.0 # Eco speed cons
    market_daily_hire = 18000 # Market Rate Assumption (from FFA or context)
    
    dist = get_distance("Singapore", cargo.load_port, distance_df) # Ballast from Hub
    dist_laden = get_distance(cargo.load_port, cargo.disch_port, distance_df)
    
    days = ((dist + dist_laden) / (avg_speed * 24)) + 5 # +5 port days
    
    fuel_cost = days * avg_cons * VLSFO_PRICE
    hire_cost = days * market_daily_hire
    
    total_outsource_cost = fuel_cost + hire_cost + cargo.port_cost_load + cargo.port_cost_disch
    
    # Revenue is still ours, but we pay the ship. 
    # Profit = Revenue - Outsource_Cost
    revenue = cargo.quantity * cargo.freight_rate
    return revenue - total_outsource_cost

# --- 2. OPTIMIZATION ENGINE ---

def optimize_portfolio():
    print("Starting Portfolio Optimization...")
    
    # We have 4 Vessels. They need 4 Jobs.
    # Jobs pool = 3 Committed Cargoes + Market Cargoes.
    # BUT: If a Committed Cargo is NOT picked by a Cargill Vessel, we MUST pay for a Market Vessel.
    
    # Strategy:
    # 1. Generate all permutations of 4 cargoes from the (Committed + Market) pool.
    # 2. Assign them to the 4 vessels.
    # 3. Calculate P&L for these 4 assignments.
    # 4. Check which Committed Cargoes were LEFT OUT.
    # 5. Subtract the cost of outsourcing those left-out committed cargoes.
    # 6. Result = Net Portfolio Profit.
    
    all_potential_cargoes = committed_cargoes + market_cargoes
    
    # Generate all combinations of 4 cargoes to assign to our 4 ships
    # (Note: Permutations because which ship takes which cargo matters due to position/speed)
    
    # Limit for performance: If lists are huge, use linear_sum_assignment. 
    # Since n=4 vessels and m~6 cargoes, permutations is fine (~360 combos).
    import itertools
    
    best_profit = -float('inf')
    best_allocation = []
    
    # Permutations of length 4 from the cargo pool
    for cargo_subset in itertools.permutations(all_potential_cargoes, 4):
        
        current_run_profit = 0
        current_allocation_details = []
        
        # A. Calculate Profit for Own Fleet
        for i, vessel in enumerate(fleet):
            cargo = cargo_subset[i]
            res = calculate_voyage_profit(vessel, cargo, dist_df, VLSFO_PRICE, MGO_PRICE)
            current_run_profit += res['profit']
            current_allocation_details.append(res)
            
        # B. Handle Unassigned Committed Cargoes
        # Identify which committed cargoes are NOT in the current cargo_subset
        assigned_names = [c.name for c in cargo_subset]
        
        for comm_c in committed_cargoes:
            if comm_c.name not in assigned_names:
                # We failed to carry this ourselves. We must outsource it.
                outsource_pnl = estimate_market_charter_cost(comm_c, dist_df)
                current_run_profit += outsource_pnl # Add the (likely small or negative) profit from outsourcing
                current_allocation_details.append({
                    "vessel": "MARKET CHARTER",
                    "cargo": comm_c.name,
                    "profit": outsource_pnl,
                    "tce": 0,
                    "notes": "Outsourced"
                })
        
        # C. Update Maximum
        if current_run_profit > best_profit:
            best_profit = current_run_profit
            best_allocation = current_allocation_details

    # --- 3. OUTPUT RESULTS ---
    print(f"\nOptimization Complete. Max Portfolio Profit: ${best_profit:,.2f}")
    print("-" * 60)
    print(f"{'VESSEL':<20} | {'CARGO':<20} | {'PROFIT':<15} | {'TCE':<10}")
    print("-" * 60)
    for row in best_allocation:
        print(f"{row['vessel']:<20} | {row['cargo']:<20} | ${row['profit']:,.0f} | ${row['tce']:,.0f}")

if __name__ == "__main__":
    optimize_portfolio()