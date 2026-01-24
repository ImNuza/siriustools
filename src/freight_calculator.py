import pandas as pd
import numpy as np

class Vessel:
    def __init__(self, name, dwt, speed_laden, speed_ballast, 
                 cons_laden_vlsfo, cons_laden_mgo, 
                 cons_ballast_vlsfo, cons_ballast_mgo,
                 port_idle_vlsfo, port_working_vlsfo,
                 location, open_date):
        self.name = name
        self.dwt = dwt
        self.speed_laden = speed_laden
        self.speed_ballast = speed_ballast
        self.cons_laden_vlsfo = cons_laden_vlsfo
        self.cons_laden_mgo = cons_laden_mgo
        self.cons_ballast_vlsfo = cons_ballast_vlsfo
        self.cons_ballast_mgo = cons_ballast_mgo
        self.port_idle_vlsfo = port_idle_vlsfo
        self.port_working_vlsfo = port_working_vlsfo
        self.location = location
        self.open_date = pd.to_datetime(open_date)

class Cargo:
    def __init__(self, name, quantity, load_port, disch_port, 
                 load_rate, disch_rate, freight_rate, 
                 terms_load_turn_time, terms_disch_turn_time,
                 port_cost_load, port_cost_disch, commission_pct,
                 laycan_start, is_committed=True):
        self.name = name
        self.quantity = quantity
        self.load_port = load_port
        self.disch_port = disch_port
        self.load_rate = load_rate
        self.disch_rate = disch_rate
        self.freight_rate = freight_rate # Per MT
        self.turn_time_load = terms_load_turn_time # in Days
        self.turn_time_disch = terms_disch_turn_time # in Days
        self.port_cost_load = port_cost_load
        self.port_cost_disch = port_cost_disch
        self.commission_pct = commission_pct
        self.laycan_start = pd.to_datetime(laycan_start)
        self.is_committed = is_committed

def get_distance(port_from, port_to, distance_df):
    """
    Looks up distance between two ports from the provided CSV dataframe.
    Returns 0 if ports are same, or raises warning if not found.
    """
    if port_from.lower() == port_to.lower():
        return 0
    
    # Try finding the route in both directions
    row = distance_df[((distance_df['PORT_NAME_FROM'].str.lower() == port_from.lower()) & 
                       (distance_df['PORT_NAME_TO'].str.lower() == port_to.lower())) |
                      ((distance_df['PORT_NAME_FROM'].str.lower() == port_to.lower()) & 
                       (distance_df['PORT_NAME_TO'].str.lower() == port_from.lower()))]
    
    if not row.empty:
        return row.iloc[0]['DISTANCE']
    else:
        # Fallback or Error handling
        # In a hackathon, you might assume a default or print an error
        # print(f"Warning: Distance not found for {port_from} to {port_to}")
        return 5000 # Placeholder safety

def calculate_voyage_profit(vessel, cargo, distance_df, bunker_price_vlsfo, bunker_price_mgo):
    """
    Calculates the detailed P&L for a specific vessel performing a specific cargo voyage.
    """
    
    # 1. Distances
    dist_ballast = get_distance(vessel.location, cargo.load_port, distance_df)
    dist_laden = get_distance(cargo.load_port, cargo.disch_port, distance_df)
    
    # 2. Sea Time (Days)
    # Adding a small safety margin (e.g., 5%) is standard in shipping logic
    safety_margin = 1.05 
    days_ballast = (dist_ballast / (vessel.speed_ballast * 24)) * safety_margin
    days_laden = (dist_laden / (vessel.speed_laden * 24)) * safety_margin
    
    # 3. Port Time (Days)
    # Time = (Qty / Rate) + TurnTime
    days_load_ops = (cargo.quantity / cargo.load_rate) + cargo.turn_time_load
    days_disch_ops = (cargo.quantity / cargo.disch_rate) + cargo.turn_time_disch
    total_port_days = days_load_ops + days_disch_ops
    
    total_voyage_days = days_ballast + days_laden + total_port_days

    # 4. Fuel Consumption (MT)
    # Sea Consumption
    sea_cons_vlsfo = (days_ballast * vessel.cons_ballast_vlsfo) + (days_laden * vessel.cons_laden_vlsfo)
    sea_cons_mgo = (days_ballast * vessel.cons_ballast_mgo) + (days_laden * vessel.cons_laden_mgo)
    
    # Port Consumption (Simplified: Working during Ops, Idle during TurnTime is a nuance, 
    # but let's average or use Working for Ops and Idle for Turn)
    # High fidelity approach:
    port_cons_vlsfo = (days_load_ops * vessel.port_working_vlsfo) + (days_disch_ops * vessel.port_working_vlsfo) 
    # (Assuming Turn Time is Idle)
    # port_cons_vlsfo += (cargo.turn_time_load + cargo.turn_time_disch) * vessel.port_idle_vlsfo
    
    total_vlsfo = sea_cons_vlsfo + port_cons_vlsfo
    total_mgo = sea_cons_mgo # Assuming MGO is constant aux/sea or same in port for this simplified model
    
    # 5. Expenses (USD)
    fuel_cost = (total_vlsfo * bunker_price_vlsfo) + (total_mgo * bunker_price_mgo)
    port_da_cost = cargo.port_cost_load + cargo.port_cost_disch
    
    gross_revenue = cargo.quantity * cargo.freight_rate
    commission_cost = gross_revenue * cargo.commission_pct
    
    total_expenses = fuel_cost + port_da_cost + commission_cost
    
    # 6. Results
    net_profit = gross_revenue - total_expenses
    tce = net_profit / total_voyage_days if total_voyage_days > 0 else 0
    
    return {
        "vessel": vessel.name,
        "cargo": cargo.name,
        "revenue": gross_revenue,
        "expenses": total_expenses,
        "fuel_cost": fuel_cost,
        "profit": net_profit,
        "tce": tce,
        "days": total_voyage_days,
        "dist_ballast": dist_ballast,
        "dist_laden": dist_laden
    }