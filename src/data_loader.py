"""
Data Loader Module for Cargill-SMU Datathon 2026
================================================
This module provides functions to load and preprocess all data files
required for the freight calculator and voyage optimization model.

Author: Team [Your Team Name]
Date: January 2026
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple

# Define the base path for data files
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Default bunker prices (Singapore, March 2026)
VLSFO_PRICE = 490  # $/MT
MGO_PRICE = 649    # $/MT


# =============================================================================
# PORT DISTANCES
# =============================================================================

def load_port_distances(filepath: Optional[str] = None) -> pd.DataFrame:
    """
    Load the port distances CSV file into a DataFrame.
    
    Args:
        filepath: Optional custom path to the CSV file.
        
    Returns:
        DataFrame with columns: PORT_NAME_FROM, PORT_NAME_TO, DISTANCE
    """
    if filepath is None:
        filepath = RAW_DATA_DIR / "Port Distances.csv"
    
    df = pd.read_csv(filepath)
    # Standardize port names to uppercase for consistent lookups
    df['PORT_NAME_FROM'] = df['PORT_NAME_FROM'].str.upper().str.strip()
    df['PORT_NAME_TO'] = df['PORT_NAME_TO'].str.upper().str.strip()
    return df


def create_distance_lookup(distances_df: pd.DataFrame) -> Dict[Tuple[str, str], float]:
    """
    Create a dictionary for O(1) distance lookups.
    
    Args:
        distances_df: DataFrame from load_port_distances()
        
    Returns:
        Dictionary mapping (port_from, port_to) -> distance in nautical miles
    """
    lookup = {}
    for _, row in distances_df.iterrows():
        port_from = row['PORT_NAME_FROM']
        port_to = row['PORT_NAME_TO']
        distance = row['DISTANCE']
        # Store both directions for bidirectional lookup
        lookup[(port_from, port_to)] = distance
        lookup[(port_to, port_from)] = distance
    return lookup


# Port name aliases for common variations
PORT_ALIASES = {
    'KAMSAR': ['KAMSAR ANCHORAGE', 'PORT KAMSAR'],
    'PORT HEDLAND': ['PORT HEDLAND'],
    'ITAGUAI': ['ITAGUAI', 'SEPETIBA'],  # Itaguai is near Sepetiba Bay
    'PONTA DA MADEIRA': ['PONTA DA MADEIRA', 'TUBARAO'],
    'MAP TA PHUT': ['MAP TA PHUT', 'MAPTAPHUT'],
    'VIZAG': ['VIZAG', 'VISAKHAPATNAM', 'VISHAKHAPATNAM'],
    'MANGALORE': ['MANGALORE', 'NEW MANGALORE'],
    'GWANGYANG': ['GWANGYANG', 'KWANGYANG', 'GWANGYANG LNG TERMINAL'],
    'FANGCHENG': ['FANGCHENG'],
}


# Hardcoded distance estimates for routes missing from the CSV
# These are reasonable estimates based on geography and typical shipping routes
# Source: Estimated from similar routes in the database and maritime geography
HARDCODED_DISTANCES = {
    # MAP TA PHUT (Thailand) routes
    ('MAP TA PHUT', 'KAMSAR ANCHORAGE'): 8500,  # Via Suez Canal
    ('MAP TA PHUT', 'PORT HEDLAND'): 2800,  # Direct via Indonesia
    ('MAP TA PHUT', 'ITAGUAI'): 11000,  # Via Cape of Good Hope
    # GWANGYANG/KWANGYANG (South Korea) routes  
    ('GWANGYANG', 'KAMSAR ANCHORAGE'): 11500,  # Via Suez Canal
    ('GWANGYANG', 'ITAGUAI'): 11800,  # Via Cape of Good Hope
    ('KWANGYANG', 'KAMSAR ANCHORAGE'): 11500,
    ('KWANGYANG', 'ITAGUAI'): 11800,
}


def get_distance(port_from: str, port_to: str, lookup: Dict) -> Optional[float]:
    """
    Get the distance between two ports.
    Handles port name variations using aliases and hardcoded estimates.
    
    Args:
        port_from: Origin port name
        port_to: Destination port name
        lookup: Distance lookup dictionary from create_distance_lookup()
        
    Returns:
        Distance in nautical miles, or None if not found
    """
    port_from = port_from.upper().strip()
    port_to = port_to.upper().strip()
    
    # Direct lookup first
    result = lookup.get((port_from, port_to))
    if result is not None:
        return result
    
    # Try aliases for port_from and port_to
    from_aliases = PORT_ALIASES.get(port_from, [port_from])
    to_aliases = PORT_ALIASES.get(port_to, [port_to])
    
    for from_alias in from_aliases:
        for to_alias in to_aliases:
            result = lookup.get((from_alias, to_alias))
            if result is not None:
                return result
    
    # Check hardcoded distances for missing routes
    for from_alias in [port_from] + from_aliases:
        for to_alias in [port_to] + to_aliases:
            result = HARDCODED_DISTANCES.get((from_alias, to_alias))
            if result is not None:
                return result
            # Try reverse direction
            result = HARDCODED_DISTANCES.get((to_alias, from_alias))
            if result is not None:
                return result
    
    return None


# =============================================================================
# VESSEL DATA
# =============================================================================

def load_cargill_vessels() -> pd.DataFrame:
    """
    Load Cargill's 4 Capesize vessels data.
    Data source: Problem Statement PPTX Slide 10
    
    Returns:
        DataFrame with vessel specifications
    """
    vessels = pd.DataFrame([
        {
            'vessel_name': 'ANN BELL',
            'dwt': 180803,
            'hire_rate': 11750,
            'speed_laden_warranted': 13.5,
            'speed_ballast_warranted': 14.5,
            'speed_laden_eco': 12.0,
            'speed_ballast_eco': 12.5,
            'consumption_laden_warranted_vlsf': 60,
            'consumption_ballast_warranted_vlsf': 55,
            'consumption_laden_eco_vlsf': 42,
            'consumption_ballast_eco_vlsf': 38,
            'consumption_mgo_sea': 2.0,
            'consumption_port_idle_vlsf': 2.0,
            'consumption_port_working_vlsf': 3.0,
            'current_port': 'QINGDAO',
            'etd': '2026-02-25',
            'bunker_rob_vlsf': 401.3,
            'bunker_rob_mgo': 45.1,
            'vessel_type': 'cargill'
        },
        {
            'vessel_name': 'OCEAN HORIZON',
            'dwt': 181550,
            'hire_rate': 15750,
            'speed_laden_warranted': 13.8,
            'speed_ballast_warranted': 14.8,
            'speed_laden_eco': 12.3,
            'speed_ballast_eco': 12.8,
            'consumption_laden_warranted_vlsf': 61,
            'consumption_ballast_warranted_vlsf': 56.5,
            'consumption_laden_eco_vlsf': 43,
            'consumption_ballast_eco_vlsf': 39.5,
            'consumption_mgo_sea': 1.8,
            'consumption_port_idle_vlsf': 1.8,
            'consumption_port_working_vlsf': 3.2,
            'current_port': 'MAP TA PHUT',
            'etd': '2026-03-01',
            'bunker_rob_vlsf': 265.8,
            'bunker_rob_mgo': 64.3,
            'vessel_type': 'cargill'
        },
        {
            'vessel_name': 'PACIFIC GLORY',
            'dwt': 182320,
            'hire_rate': 14800,
            'speed_laden_warranted': 13.5,
            'speed_ballast_warranted': 14.2,
            'speed_laden_eco': 12.2,
            'speed_ballast_eco': 12.7,
            'consumption_laden_warranted_vlsf': 59,
            'consumption_ballast_warranted_vlsf': 54,
            'consumption_laden_eco_vlsf': 44,
            'consumption_ballast_eco_vlsf': 40,
            'consumption_mgo_sea': 1.9,
            'consumption_port_idle_vlsf': 2.0,
            'consumption_port_working_vlsf': 3.0,
            'current_port': 'GWANGYANG',
            'etd': '2026-03-10',
            'bunker_rob_vlsf': 601.9,
            'bunker_rob_mgo': 98.1,
            'vessel_type': 'cargill'
        },
        {
            'vessel_name': 'GOLDEN ASCENT',
            'dwt': 179965,
            'hire_rate': 13950,
            'speed_laden_warranted': 13.0,
            'speed_ballast_warranted': 14.0,
            'speed_laden_eco': 11.8,
            'speed_ballast_eco': 12.3,
            'consumption_laden_warranted_vlsf': 58,
            'consumption_ballast_warranted_vlsf': 53,
            'consumption_laden_eco_vlsf': 41,
            'consumption_ballast_eco_vlsf': 37,
            'consumption_mgo_sea': 2.0,
            'consumption_port_idle_vlsf': 1.9,
            'consumption_port_working_vlsf': 3.1,
            'current_port': 'FANGCHENG',
            'etd': '2026-03-08',
            'bunker_rob_vlsf': 793.3,
            'bunker_rob_mgo': 17.1,
            'vessel_type': 'cargill'
        }
    ])
    vessels['etd'] = pd.to_datetime(vessels['etd'])
    return vessels


def load_market_vessels() -> pd.DataFrame:
    """
    Load market vessels available for hire.
    Data source: Problem Statement PPTX Slide 12
    
    Returns:
        DataFrame with market vessel specifications
    """
    vessels = pd.DataFrame([
        {
            'vessel_name': 'ATLANTIC FORTUNE',
            'dwt': 181200,
            'speed_laden_warranted': 13.8,
            'speed_ballast_warranted': 14.6,
            'speed_laden_eco': 12.3,
            'speed_ballast_eco': 12.9,
            'consumption_laden_warranted_vlsf': 60,
            'consumption_ballast_warranted_vlsf': 56,
            'consumption_laden_eco_vlsf': 43,
            'consumption_ballast_eco_vlsf': 39.5,
            'consumption_mgo_sea': 2.0,
            'consumption_port_idle_vlsf': 2.0,
            'consumption_port_working_vlsf': 3.0,
            'current_port': 'PARADIP',
            'etd': '2026-03-02',
            'bunker_rob_vlsf': 512.4,
            'bunker_rob_mgo': 38.9,
            'vessel_type': 'market'
        },
        {
            'vessel_name': 'PACIFIC VANGUARD',
            'dwt': 182050,
            'speed_laden_warranted': 13.6,
            'speed_ballast_warranted': 14.3,
            'speed_laden_eco': 12.0,
            'speed_ballast_eco': 12.5,
            'consumption_laden_warranted_vlsf': 59,
            'consumption_ballast_warranted_vlsf': 54,
            'consumption_laden_eco_vlsf': 42,
            'consumption_ballast_eco_vlsf': 38,
            'consumption_mgo_sea': 1.9,
            'consumption_port_idle_vlsf': 1.9,
            'consumption_port_working_vlsf': 3.0,
            'current_port': 'CAOFEIDIAN',
            'etd': '2026-02-26',
            'bunker_rob_vlsf': 420.3,
            'bunker_rob_mgo': 51.0,
            'vessel_type': 'market'
        },
        {
            'vessel_name': 'CORAL EMPEROR',
            'dwt': 180450,
            'speed_laden_warranted': 13.4,
            'speed_ballast_warranted': 14.1,
            'speed_laden_eco': 11.9,
            'speed_ballast_eco': 12.3,
            'consumption_laden_warranted_vlsf': 58,
            'consumption_ballast_warranted_vlsf': 53,
            'consumption_laden_eco_vlsf': 40,
            'consumption_ballast_eco_vlsf': 36.5,
            'consumption_mgo_sea': 2.0,
            'consumption_port_idle_vlsf': 2.0,
            'consumption_port_working_vlsf': 3.1,
            'current_port': 'ROTTERDAM',
            'etd': '2026-03-05',
            'bunker_rob_vlsf': 601.7,
            'bunker_rob_mgo': 42.3,
            'vessel_type': 'market'
        },
        {
            'vessel_name': 'EVEREST OCEAN',
            'dwt': 179950,
            'speed_laden_warranted': 13.7,
            'speed_ballast_warranted': 14.5,
            'speed_laden_eco': 12.4,
            'speed_ballast_eco': 12.8,
            'consumption_laden_warranted_vlsf': 61,
            'consumption_ballast_warranted_vlsf': 56.5,
            'consumption_laden_eco_vlsf': 43.5,
            'consumption_ballast_eco_vlsf': 39,
            'consumption_mgo_sea': 1.8,
            'consumption_port_idle_vlsf': 1.8,
            'consumption_port_working_vlsf': 3.0,
            'current_port': 'XIAMEN',
            'etd': '2026-03-03',
            'bunker_rob_vlsf': 478.2,
            'bunker_rob_mgo': 56.4,
            'vessel_type': 'market'
        },
        {
            'vessel_name': 'POLARIS SPIRIT',
            'dwt': 181600,
            'speed_laden_warranted': 13.9,
            'speed_ballast_warranted': 14.7,
            'speed_laden_eco': 12.5,
            'speed_ballast_eco': 13.0,
            'consumption_laden_warranted_vlsf': 62,
            'consumption_ballast_warranted_vlsf': 57,
            'consumption_laden_eco_vlsf': 44,
            'consumption_ballast_eco_vlsf': 40,
            'consumption_mgo_sea': 1.9,
            'consumption_port_idle_vlsf': 2.0,
            'consumption_port_working_vlsf': 3.1,
            'current_port': 'KANDLA',
            'etd': '2026-02-28',
            'bunker_rob_vlsf': 529.8,
            'bunker_rob_mgo': 47.1,
            'vessel_type': 'market'
        },
        {
            'vessel_name': 'IRON CENTURY',
            'dwt': 182100,
            'speed_laden_warranted': 13.5,
            'speed_ballast_warranted': 14.2,
            'speed_laden_eco': 12.0,
            'speed_ballast_eco': 12.5,
            'consumption_laden_warranted_vlsf': 59,
            'consumption_ballast_warranted_vlsf': 54,
            'consumption_laden_eco_vlsf': 41,
            'consumption_ballast_eco_vlsf': 37.5,
            'consumption_mgo_sea': 2.1,
            'consumption_port_idle_vlsf': 2.1,
            'consumption_port_working_vlsf': 3.2,
            'current_port': 'PORT TALBOT',
            'etd': '2026-03-09',
            'bunker_rob_vlsf': 365.6,
            'bunker_rob_mgo': 60.7,
            'vessel_type': 'market'
        },
        {
            'vessel_name': 'MOUNTAIN TRADER',
            'dwt': 180890,
            'speed_laden_warranted': 13.3,
            'speed_ballast_warranted': 14.0,
            'speed_laden_eco': 12.1,
            'speed_ballast_eco': 12.6,
            'consumption_laden_warranted_vlsf': 58,
            'consumption_ballast_warranted_vlsf': 53,
            'consumption_laden_eco_vlsf': 42,
            'consumption_ballast_eco_vlsf': 38,
            'consumption_mgo_sea': 2.0,
            'consumption_port_idle_vlsf': 2.0,
            'consumption_port_working_vlsf': 3.1,
            'current_port': 'GWANGYANG',
            'etd': '2026-03-06',
            'bunker_rob_vlsf': 547.1,
            'bunker_rob_mgo': 32.4,
            'vessel_type': 'market'
        },
        {
            'vessel_name': 'NAVIS PRIDE',
            'dwt': 181400,
            'speed_laden_warranted': 13.8,
            'speed_ballast_warranted': 14.5,
            'speed_laden_eco': 12.6,
            'speed_ballast_eco': 13.0,
            'consumption_laden_warranted_vlsf': 61,
            'consumption_ballast_warranted_vlsf': 56,
            'consumption_laden_eco_vlsf': 44,
            'consumption_ballast_eco_vlsf': 39,
            'consumption_mgo_sea': 1.8,
            'consumption_port_idle_vlsf': 1.8,
            'consumption_port_working_vlsf': 3.0,
            'current_port': 'MUNDRA',
            'etd': '2026-02-27',
            'bunker_rob_vlsf': 493.8,
            'bunker_rob_mgo': 45.2,
            'vessel_type': 'market'
        },
        {
            'vessel_name': 'AURORA SKY',
            'dwt': 179880,
            'speed_laden_warranted': 13.4,
            'speed_ballast_warranted': 14.1,
            'speed_laden_eco': 12.0,
            'speed_ballast_eco': 12.5,
            'consumption_laden_warranted_vlsf': 58,
            'consumption_ballast_warranted_vlsf': 53,
            'consumption_laden_eco_vlsf': 41,
            'consumption_ballast_eco_vlsf': 37.5,
            'consumption_mgo_sea': 2.0,
            'consumption_port_idle_vlsf': 2.0,
            'consumption_port_working_vlsf': 3.1,
            'current_port': 'JINGTANG',
            'etd': '2026-03-04',
            'bunker_rob_vlsf': 422.7,
            'bunker_rob_mgo': 29.8,
            'vessel_type': 'market'
        },
        {
            'vessel_name': 'ZENITH GLORY',
            'dwt': 182500,
            'speed_laden_warranted': 13.9,
            'speed_ballast_warranted': 14.6,
            'speed_laden_eco': 12.4,
            'speed_ballast_eco': 12.9,
            'consumption_laden_warranted_vlsf': 61,
            'consumption_ballast_warranted_vlsf': 56.5,
            'consumption_laden_eco_vlsf': 43.5,
            'consumption_ballast_eco_vlsf': 39,
            'consumption_mgo_sea': 1.9,
            'consumption_port_idle_vlsf': 1.9,
            'consumption_port_working_vlsf': 3.1,
            'current_port': 'VIZAG',
            'etd': '2026-03-07',
            'bunker_rob_vlsf': 502.3,
            'bunker_rob_mgo': 44.6,
            'vessel_type': 'market'
        },
        {
            'vessel_name': 'TITAN LEGACY',
            'dwt': 180650,
            'speed_laden_warranted': 13.5,
            'speed_ballast_warranted': 14.2,
            'speed_laden_eco': 12.2,
            'speed_ballast_eco': 12.7,
            'consumption_laden_warranted_vlsf': 59,
            'consumption_ballast_warranted_vlsf': 54,
            'consumption_laden_eco_vlsf': 42,
            'consumption_ballast_eco_vlsf': 38,
            'consumption_mgo_sea': 2.0,
            'consumption_port_idle_vlsf': 2.0,
            'consumption_port_working_vlsf': 3.0,
            'current_port': 'JUBAIL',
            'etd': '2026-03-01',
            'bunker_rob_vlsf': 388.5,
            'bunker_rob_mgo': 53.1,
            'vessel_type': 'market'
        }
    ])
    vessels['etd'] = pd.to_datetime(vessels['etd'])
    return vessels


def load_all_vessels() -> pd.DataFrame:
    """
    Load both Cargill and market vessels into a single DataFrame.
    
    Returns:
        Combined DataFrame of all vessels
    """
    cargill = load_cargill_vessels()
    market = load_market_vessels()
    return pd.concat([cargill, market], ignore_index=True)


# =============================================================================
# CARGO DATA
# =============================================================================

def load_cargill_cargoes() -> pd.DataFrame:
    """
    Load Cargill's 3 committed cargoes.
    Data source: Problem Statement PPTX Slide 11
    
    Returns:
        DataFrame with cargo specifications
    """
    cargoes = pd.DataFrame([
        {
            'cargo_id': 'CARGILL_1',
            'route': 'West Africa - China',
            'customer': 'EGA',
            'commodity': 'Bauxite',
            'quantity': 180000,
            'quantity_tolerance': 0.10,
            'quantity_option': 'owners',
            'laycan_start': '2026-04-02',
            'laycan_end': '2026-04-10',
            'freight_rate': 23.0,
            'load_port': 'KAMSAR',
            'load_rate': 30000,
            'load_terms': 'PWWD SHINC',
            'load_turn_time': 12,
            'discharge_port': 'QINGDAO',
            'discharge_rate': 25000,
            'discharge_terms': 'PWWD SHINC',
            'discharge_turn_time': 12,
            'port_cost_load': 0,
            'port_cost_discharge': 0,
            'commission_pct': 1.25,
            'commission_to': 'broker',
            'cargo_type': 'cargill'
        },
        {
            'cargo_id': 'CARGILL_2',
            'route': 'Australia - China',
            'customer': 'BHP',
            'commodity': 'Iron Ore',
            'quantity': 160000,
            'quantity_tolerance': 0.10,
            'quantity_option': 'owners',
            'laycan_start': '2026-03-07',
            'laycan_end': '2026-03-11',
            'freight_rate': 9.0,
            'load_port': 'PORT HEDLAND',
            'load_rate': 80000,
            'load_terms': 'PWWD SHINC',
            'load_turn_time': 12,
            'discharge_port': 'LIANYUNGANG',
            'discharge_rate': 30000,
            'discharge_terms': 'PWWD SHINC',
            'discharge_turn_time': 24,
            'port_cost_load': 260000,
            'port_cost_discharge': 120000,
            'commission_pct': 3.75,
            'commission_to': 'charterer',
            'cargo_type': 'cargill',
            'special_terms': 'Half freight for cargo >176,000 MT'
        },
        {
            'cargo_id': 'CARGILL_3',
            'route': 'Brazil - China',
            'customer': 'CSN',
            'commodity': 'Iron Ore',
            'quantity': 180000,
            'quantity_tolerance': 0.10,
            'quantity_option': 'MOLOO',
            'laycan_start': '2026-04-01',
            'laycan_end': '2026-04-08',
            'freight_rate': 22.30,
            'load_port': 'ITAGUAI',
            'load_rate': 60000,
            'load_terms': 'PWWD SHINC',
            'load_turn_time': 6,
            'discharge_port': 'QINGDAO',
            'discharge_rate': 30000,
            'discharge_terms': 'PWWD SHINC',
            'discharge_turn_time': 24,
            'port_cost_load': 75000,
            'port_cost_discharge': 90000,
            'commission_pct': 3.75,
            'commission_to': 'charterer',
            'cargo_type': 'cargill'
        }
    ])
    cargoes['laycan_start'] = pd.to_datetime(cargoes['laycan_start'])
    cargoes['laycan_end'] = pd.to_datetime(cargoes['laycan_end'])
    return cargoes


def load_market_cargoes() -> pd.DataFrame:
    """
    Load market cargoes available for bidding.
    Data source: Problem Statement PPTX Slides 13-14
    
    Returns:
        DataFrame with market cargo specifications
    """
    cargoes = pd.DataFrame([
        {
            'cargo_id': 'MARKET_1',
            'route': 'Australia - China',
            'customer': 'Rio Tinto',
            'commodity': 'Iron Ore',
            'quantity': 170000,
            'quantity_tolerance': 0.10,
            'quantity_option': 'MOLOO',
            'laycan_start': '2026-03-12',
            'laycan_end': '2026-03-18',
            'freight_rate': None,  # To be quoted
            'load_port': 'DAMPIER',
            'load_rate': 80000,
            'load_terms': 'PWWD SHINC',
            'load_turn_time': 12,
            'discharge_port': 'QINGDAO',
            'discharge_rate': 30000,
            'discharge_terms': 'PWWD SHINC',
            'discharge_turn_time': 24,
            'port_cost_load': 120000,
            'port_cost_discharge': 120000,
            'commission_pct': 3.75,
            'commission_to': 'charterer',
            'cargo_type': 'market'
        },
        {
            'cargo_id': 'MARKET_2',
            'route': 'Brazil - China',
            'customer': 'Vale',
            'commodity': 'Iron Ore',
            'quantity': 190000,
            'quantity_tolerance': 0.10,
            'quantity_option': 'MOLOO',
            'laycan_start': '2026-04-03',
            'laycan_end': '2026-04-10',
            'freight_rate': None,
            'load_port': 'PONTA DA MADEIRA',
            'load_rate': 60000,
            'load_terms': 'PWWD SHINC',
            'load_turn_time': 12,
            'discharge_port': 'CAOFEIDIAN',
            'discharge_rate': 30000,
            'discharge_terms': 'PWWD SHINC',
            'discharge_turn_time': 24,
            'port_cost_load': 75000,
            'port_cost_discharge': 95000,
            'commission_pct': 3.75,
            'commission_to': 'charterer',
            'cargo_type': 'market'
        },
        {
            'cargo_id': 'MARKET_3',
            'route': 'South Africa - China',
            'customer': 'Anglo American',
            'commodity': 'Iron Ore',
            'quantity': 180000,
            'quantity_tolerance': 0.10,
            'quantity_option': 'MOLOO',
            'laycan_start': '2026-03-15',
            'laycan_end': '2026-03-22',
            'freight_rate': None,
            'load_port': 'SALDANHA BAY',
            'load_rate': 55000,
            'load_terms': 'PWWD SHINC',
            'load_turn_time': 6,
            'discharge_port': 'TIANJIN',
            'discharge_rate': 25000,
            'discharge_terms': 'PWWD SHINC',
            'discharge_turn_time': 24,
            'port_cost_load': 90000,
            'port_cost_discharge': 90000,
            'commission_pct': 3.75,
            'commission_to': 'charterer',
            'cargo_type': 'market'
        },
        {
            'cargo_id': 'MARKET_4',
            'route': 'Indonesia - India',
            'customer': 'Adaro',
            'commodity': 'Thermal Coal',
            'quantity': 150000,
            'quantity_tolerance': 0.10,
            'quantity_option': 'MOLOO',
            'laycan_start': '2026-04-10',
            'laycan_end': '2026-04-15',
            'freight_rate': None,
            'load_port': 'TABONEO',
            'load_rate': 35000,
            'load_terms': 'PWWD SHINC',
            'load_turn_time': 12,
            'discharge_port': 'KRISHNAPATNAM',
            'discharge_rate': 25000,
            'discharge_terms': 'PWWD SHINC',
            'discharge_turn_time': 24,
            'port_cost_load': 45000,
            'port_cost_discharge': 45000,
            'commission_pct': 2.50,
            'commission_to': 'broker',
            'cargo_type': 'market'
        },
        {
            'cargo_id': 'MARKET_5',
            'route': 'Canada - China',
            'customer': 'Teck Resources',
            'commodity': 'Coking Coal',
            'quantity': 160000,
            'quantity_tolerance': 0.10,
            'quantity_option': 'MOLOO',
            'laycan_start': '2026-03-18',
            'laycan_end': '2026-03-26',
            'freight_rate': None,
            'load_port': 'VANCOUVER',
            'load_rate': 45000,
            'load_terms': 'PWWD SHINC',
            'load_turn_time': 12,
            'discharge_port': 'FANGCHENG',
            'discharge_rate': 25000,
            'discharge_terms': 'PWWD SHINC',
            'discharge_turn_time': 24,
            'port_cost_load': 180000,
            'port_cost_discharge': 110000,
            'commission_pct': 3.75,
            'commission_to': 'charterer',
            'cargo_type': 'market'
        },
        {
            'cargo_id': 'MARKET_6',
            'route': 'West Africa - India',
            'customer': 'Guinea Alumina Corp',
            'commodity': 'Bauxite',
            'quantity': 175000,
            'quantity_tolerance': 0.10,
            'quantity_option': 'MOLOO',
            'laycan_start': '2026-04-10',
            'laycan_end': '2026-04-18',
            'freight_rate': None,
            'load_port': 'KAMSAR',
            'load_rate': 30000,
            'load_terms': 'PWWD SHINC',
            'load_turn_time': 0,  # Anchorage loading
            'discharge_port': 'MANGALORE',
            'discharge_rate': 25000,
            'discharge_terms': 'PWWD SHINC',
            'discharge_turn_time': 12,
            'port_cost_load': 75000,
            'port_cost_discharge': 75000,
            'commission_pct': 2.50,
            'commission_to': 'broker',
            'cargo_type': 'market'
        },
        {
            'cargo_id': 'MARKET_7',
            'route': 'Australia - South Korea',
            'customer': 'BHP',
            'commodity': 'Iron Ore',
            'quantity': 165000,
            'quantity_tolerance': 0.10,
            'quantity_option': 'MOLOO',
            'laycan_start': '2026-03-09',
            'laycan_end': '2026-03-15',
            'freight_rate': None,
            'load_port': 'PORT HEDLAND',
            'load_rate': 80000,
            'load_terms': 'PWWD SHINC',
            'load_turn_time': 12,
            'discharge_port': 'GWANGYANG',
            'discharge_rate': 30000,
            'discharge_terms': 'PWWD SHINC',
            'discharge_turn_time': 24,
            'port_cost_load': 115000,
            'port_cost_discharge': 115000,
            'commission_pct': 3.75,
            'commission_to': 'charterer',
            'cargo_type': 'market'
        },
        {
            'cargo_id': 'MARKET_8',
            'route': 'Brazil - Malaysia',
            'customer': 'Vale Malaysia',
            'commodity': 'Iron Ore',
            'quantity': 180000,
            'quantity_tolerance': 0.10,
            'quantity_option': 'MO',
            'laycan_start': '2026-03-25',
            'laycan_end': '2026-04-02',
            'freight_rate': None,
            'load_port': 'TUBARAO',
            'load_rate': 60000,
            'load_terms': 'PWWD SHINC',
            'load_turn_time': 6,
            'discharge_port': 'TELUK RUBIAH',
            'discharge_rate': 25000,
            'discharge_terms': 'PWWD SHINC',
            'discharge_turn_time': 24,
            'port_cost_load': 85000,
            'port_cost_discharge': 80000,
            'commission_pct': 3.75,
            'commission_to': 'charterer',
            'cargo_type': 'market'
        }
    ])
    cargoes['laycan_start'] = pd.to_datetime(cargoes['laycan_start'])
    cargoes['laycan_end'] = pd.to_datetime(cargoes['laycan_end'])
    return cargoes


def load_all_cargoes() -> pd.DataFrame:
    """
    Load both Cargill committed and market cargoes.
    
    Returns:
        Combined DataFrame of all cargoes
    """
    cargill = load_cargill_cargoes()
    market = load_market_cargoes()
    return pd.concat([cargill, market], ignore_index=True)


# =============================================================================
# BUNKER PRICES
# =============================================================================

def load_bunker_prices() -> pd.DataFrame:
    """
    Load bunker forward curve prices.
    Data source: Problem Statement PPTX Slide 16
    Using March 2026 prices as the baseline.
    
    Returns:
        DataFrame with bunker prices by location
    """
    prices = pd.DataFrame([
        {'location': 'SINGAPORE', 'vlsfo': 490, 'mgo': 649},
        {'location': 'FUJAIRAH', 'vlsfo': 478, 'mgo': 638},
        {'location': 'DURBAN', 'vlsfo': 437, 'mgo': 510},
        {'location': 'ROTTERDAM', 'vlsfo': 467, 'mgo': 613},
        {'location': 'GIBRALTAR', 'vlsfo': 474, 'mgo': 623},
        {'location': 'PORT LOUIS', 'vlsfo': 454, 'mgo': 583},
        {'location': 'QINGDAO', 'vlsfo': 643, 'mgo': 833},
        {'location': 'SHANGHAI', 'vlsfo': 645, 'mgo': 836},
        {'location': 'RICHARDS BAY', 'vlsfo': 441, 'mgo': 519},
    ])
    return prices


def get_bunker_price(location: str, fuel_type: str, prices_df: pd.DataFrame) -> float:
    """
    Get the bunker price for a specific location and fuel type.
    Falls back to Singapore price if location not found.
    
    Args:
        location: Port/location name
        fuel_type: 'vlsfo' or 'mgo'
        prices_df: DataFrame from load_bunker_prices()
        
    Returns:
        Price in USD per metric ton
    """
    location = location.upper().strip()
    row = prices_df[prices_df['location'] == location]
    
    if len(row) == 0:
        # Default to Singapore if location not found
        row = prices_df[prices_df['location'] == 'SINGAPORE']
    
    return row[fuel_type].values[0]


# =============================================================================
# FFA RATES (Forward Freight Agreements)
# =============================================================================

def load_ffa_rates() -> pd.DataFrame:
    """
    Load Baltic Exchange Capesize FFA rates.
    Data source: Problem Statement PPTX Slide 15
    Using March 2026 rates.
    
    Returns:
        DataFrame with FFA rates by route
    """
    rates = pd.DataFrame([
        {'route': '5TC', 'description': 'Avg. of 5 Capesize T/C routes', 'rate': 18454, 'unit': 'USD/day'},
        {'route': 'C3', 'description': 'Tubarao-Qingdao', 'rate': 20.908, 'unit': 'USD/MT'},
        {'route': 'C5', 'description': 'West Australia-Qingdao', 'rate': 8.717, 'unit': 'USD/MT'},
        {'route': 'C7', 'description': 'Bolivar-Rotterdam', 'rate': 11.821, 'unit': 'USD/MT'},
    ])
    return rates


# =============================================================================
# MAIN DATA LOADING FUNCTION
# =============================================================================

def load_all_data() -> Dict:
    """
    Load all data required for the freight calculator.
    
    Returns:
        Dictionary containing all DataFrames and lookup tables
    """
    print("Loading port distances...")
    distances_df = load_port_distances()
    distance_lookup = create_distance_lookup(distances_df)
    
    print("Loading vessel data...")
    vessels_df = load_all_vessels()
    
    print("Loading cargo data...")
    cargoes_df = load_all_cargoes()
    
    print("Loading bunker prices...")
    bunker_df = load_bunker_prices()
    
    print("Loading FFA rates...")
    ffa_df = load_ffa_rates()
    
    print("All data loaded successfully!")
    
    return {
        'distances': distances_df,
        'distance_lookup': distance_lookup,
        'vessels': vessels_df,
        'cargoes': cargoes_df,
        'bunker_prices': bunker_df,
        'ffa_rates': ffa_df
    }


# =============================================================================
# TEST / DEMO
# =============================================================================

if __name__ == "__main__":
    # Quick test of data loading
    data = load_all_data()
    
    print("\n--- Data Summary ---")
    print(f"Port pairs loaded: {len(data['distances']):,}")
    print(f"Vessels loaded: {len(data['vessels'])}")
    print(f"  - Cargill vessels: {len(data['vessels'][data['vessels']['vessel_type'] == 'cargill'])}")
    print(f"  - Market vessels: {len(data['vessels'][data['vessels']['vessel_type'] == 'market'])}")
    print(f"Cargoes loaded: {len(data['cargoes'])}")
    print(f"  - Cargill cargoes: {len(data['cargoes'][data['cargoes']['cargo_type'] == 'cargill'])}")
    print(f"  - Market cargoes: {len(data['cargoes'][data['cargoes']['cargo_type'] == 'market'])}")
    print(f"Bunker locations: {len(data['bunker_prices'])}")
    
    # Test distance lookup
    test_distance = get_distance('QINGDAO', 'PORT HEDLAND', data['distance_lookup'])
    print(f"\nTest distance (Qingdao -> Port Hedland): {test_distance} nm")
