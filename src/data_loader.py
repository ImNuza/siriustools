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
import json
from pathlib import Path
from typing import Dict, Optional, Tuple, List

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

def load_all_vessels(filepath: Optional[str] = None) -> pd.DataFrame:
    """
    Load all vessels (Cargill + Market) from JSON.
    
    Args:
        filepath: Optional path to vessels.json
        
    Returns:
        DataFrame with vessel specifications
    """
    if filepath is None:
        filepath = RAW_DATA_DIR / "vessels.json"
    
    vessels = pd.read_json(filepath)
    # Ensure dates are datetime objects
    if 'etd' in vessels.columns:
        vessels['etd'] = pd.to_datetime(vessels['etd'])
        
    return vessels


def load_cargill_vessels() -> pd.DataFrame:
    """Helper to get only Cargill vessels"""
    df = load_all_vessels()
    return df[df['vessel_type'] == 'cargill'].copy()


def load_market_vessels() -> pd.DataFrame:
    """Helper to get only Market vessels"""
    df = load_all_vessels()
    return df[df['vessel_type'] == 'market'].copy()


# =============================================================================
# CARGO DATA
# =============================================================================

def load_all_cargoes(filepath: Optional[str] = None) -> pd.DataFrame:
    """
    Load all cargoes (Cargill + Market) from JSON.
    
    Args:
        filepath: Optional path to cargoes.json
        
    Returns:
        DataFrame with cargo specifications
    """
    if filepath is None:
        filepath = RAW_DATA_DIR / "cargoes.json"
    
    cargoes = pd.read_json(filepath)
    
    # Ensure dates are datetime objects
    date_cols = ['laycan_start', 'laycan_end']
    for col in date_cols:
        if col in cargoes.columns:
            cargoes[col] = pd.to_datetime(cargoes[col])
            
    return cargoes


def load_cargill_cargoes() -> pd.DataFrame:
    """Helper to get only Cargill cargoes"""
    df = load_all_cargoes()
    return df[df['cargo_type'] == 'cargill'].copy()


def load_market_cargoes() -> pd.DataFrame:
    """Helper to get only Market cargoes"""
    df = load_all_cargoes()
    return df[df['cargo_type'] == 'market'].copy()


# =============================================================================
# BUNKER PRICES
# =============================================================================

def load_bunker_prices(filepath: Optional[str] = None) -> pd.DataFrame:
    """
    Load bunker forward curve prices from JSON.
    
    Args:
        filepath: Optional path to bunker_prices.json
        
    Returns:
        DataFrame with bunker prices by location
    """
    if filepath is None:
        filepath = RAW_DATA_DIR / "bunker_prices.json"
        
    return pd.read_json(filepath)


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

def load_ffa_rates(filepath: Optional[str] = None) -> pd.DataFrame:
    """
    Load Baltic Exchange Capesize FFA rates from JSON.
    
    Args:
        filepath: Optional path to ffa_rates.json
        
    Returns:
        DataFrame with FFA rates by route
    """
    if filepath is None:
        filepath = RAW_DATA_DIR / "ffa_rates.json"
        
    return pd.read_json(filepath)


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
    try:
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
        
        # Test distance lookup (using internal aliases/hardcoded logic)
        test_distance = get_distance('QINGDAO', 'PORT HEDLAND', data['distance_lookup'])
        print(f"\nTest distance (Qingdao -> Port Hedland): {test_distance} nm")
        
    except Exception as e:
        print(f"\nError loading data. Ensure JSON files are in {RAW_DATA_DIR}")
        print(f"Details: {e}")