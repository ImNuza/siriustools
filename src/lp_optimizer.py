"""
Linear Programming Optimizer for Fleet Allocation
==================================================
Uses OR-Tools to find optimal vessel-cargo assignments across
ALL vessels (Cargill + Market) and ALL cargoes (Committed + Spot).

This provides:
1. Optimal assignment maximizing total profit
2. Comparison between Cargill-only vs Mixed Fleet strategies
3. Threshold analysis for decision switching points
4. Full calculation breakdown for each voyage

Author: Team Sirius
Date: January 2026
"""

from ortools.linear_solver import pywraplp
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

# Import from existing modules
from data_loader import load_all_data, get_distance
from optimization import calculate_voyage_profit, VLSFO_PRICE, MGO_PRICE


@dataclass
class VoyageResult:
    """Detailed voyage calculation result."""
    vessel: str
    cargo: str
    vessel_type: str  # 'cargill' or 'market'
    cargo_type: str   # 'cargill' (committed) or 'market' (spot)
    route: str
    load_port: str
    discharge_port: str
    distance_nm: float
    sea_days: float
    port_days: float
    total_days: float
    revenue: float
    hire_cost: float
    bunker_cost: float
    port_cost: float
    commission: float
    profit: float
    tce: float
    feasible: bool
    # Additional fields for detailed display
    hire_rate: float = 0.0
    quantity: float = 0.0
    freight_rate: float = 0.0
    infeasibility_reason: str = ""


class FleetOptimizer:
    """
    LP-based fleet optimizer for Cargill-SMU Datathon.
    
    Handles:
    - 4 Cargill vessels + 11 Market vessels = 15 total
    - 3 Committed cargoes + 8 Spot cargoes = 11 total
    - 165 possible combinations
    - Laycan constraints
    - DWT constraints
    - Scenario analysis (bunker price, port delays)
    """
    
    def __init__(self):
        """Initialize with data from data_loader."""
        data = load_all_data()
        
        # Data comes as DataFrames
        self.vessels_df = data['vessels']
        self.cargoes_df = data['cargoes']
        self.distances = data['distances']
        
        # Convert to list of dicts for easier processing
        self.all_vessels = self.vessels_df.to_dict('records')
        self.all_cargoes = self.cargoes_df.to_dict('records')
        
        # Standardize column names
        for v in self.all_vessels:
            if 'vessel_name' in v:
                v['name'] = v['vessel_name']
            if 'vessel_type' not in v:
                v['vessel_type'] = 'unknown'
                
        for c in self.all_cargoes:
            if 'cargo_type' not in c:
                c['cargo_type'] = 'unknown'
        
    def get_cargill_vessels(self) -> List[Dict]:
        """Get only Cargill vessels."""
        return [v for v in self.all_vessels if v.get('vessel_type') == 'cargill']
    
    def get_market_vessels(self) -> List[Dict]:
        """Get only Market vessels."""
        return [v for v in self.all_vessels if v.get('vessel_type') == 'market']
    
    def get_committed_cargoes(self) -> List[Dict]:
        """Get only committed (Cargill) cargoes."""
        return [c for c in self.all_cargoes if c.get('cargo_type') == 'cargill']
    
    def get_spot_cargoes(self) -> List[Dict]:
        """Get only spot (Market) cargoes."""
        return [c for c in self.all_cargoes if c.get('cargo_type') == 'market']
    
    def calculate_voyage(
        self, 
        vessel: Dict, 
        cargo: Dict,
        bunker_price_change: float = 0,
        additional_port_days: int = 0
    ) -> VoyageResult:
        """
        Calculate detailed voyage economics for a vessel-cargo pair.
        """
        vessel_name = vessel.get('name', vessel.get('vessel_name', 'Unknown'))
        cargo_id = cargo.get('cargo_id', 'Unknown')
        vessel_type = vessel.get('vessel_type', 'unknown')
        cargo_type = cargo.get('cargo_type', 'unknown')
        
        # Check basic feasibility
        feasible = True
        infeasibility_reason = ""
        
        # DWT check
        vessel_dwt = vessel.get('dwt', 180000)
        cargo_qty = cargo.get('quantity', 0)
        if vessel_dwt < cargo_qty:
            feasible = False
            infeasibility_reason = f"DWT {vessel_dwt} < Cargo {cargo_qty}"
        
        # Laycan check
        if not self._check_laycan(vessel, cargo):
            feasible = False
            infeasibility_reason = "Cannot meet laycan window"
        
        # Get distance
        load_port = cargo.get('load_port', '')
        discharge_port = cargo.get('discharge_port', '')
        
        try:
            distance = get_distance(load_port, discharge_port)
        except:
            distance = 0
            
        if distance == 0:
            distance = self._estimate_distance(load_port, discharge_port)
        
        # Calculate voyage using existing function
        adjusted_vlsfo = VLSFO_PRICE * (1 + bunker_price_change)
        adjusted_mgo = MGO_PRICE * (1 + bunker_price_change)
        
        try:
            # Convert dict to Series for calculate_voyage_profit
            vessel_series = pd.Series(vessel)
            cargo_series = pd.Series(cargo)
            
            result = calculate_voyage_profit(
                vessel=vessel_series,
                cargo=cargo_series,
                use_eco_speed=True,
                weather_margin=0.05,
                extra_port_days=additional_port_days
            )
            
            # Get additional fields for detailed display
            hire_rate = vessel.get('hire_rate', vessel.get('daily_hire', 0))
            quantity = cargo.get('quantity', 0)
            freight_rate = cargo.get('freight_rate', 0)
            
            return VoyageResult(
                vessel=vessel_name,
                cargo=cargo_id,
                vessel_type=vessel_type,
                cargo_type=cargo_type,
                route=f"{load_port} → {discharge_port}",
                load_port=load_port,
                discharge_port=discharge_port,
                distance_nm=distance,
                sea_days=result.get('sea_days', 0),
                port_days=result.get('port_days', 0),
                total_days=result.get('total_days', 0),
                revenue=result.get('revenue', 0),
                hire_cost=result.get('hire_cost', 0),
                bunker_cost=result.get('bunker_cost', 0),
                port_cost=result.get('port_cost', 0),
                commission=result.get('commission', 0),
                profit=result.get('profit', 0),
                tce=result.get('tce', 0),
                feasible=feasible,
                hire_rate=hire_rate,
                quantity=quantity,
                freight_rate=freight_rate,
                infeasibility_reason=infeasibility_reason
            )
        except Exception as e:
            # Get fields even for error case
            hire_rate = vessel.get('hire_rate', vessel.get('daily_hire', 0))
            quantity = cargo.get('quantity', 0)
            freight_rate = cargo.get('freight_rate', 0)
            
            return VoyageResult(
                vessel=vessel_name,
                cargo=cargo_id,
                vessel_type=vessel_type,
                cargo_type=cargo_type,
                route=f"{load_port} → {discharge_port}",
                load_port=load_port,
                discharge_port=discharge_port,
                distance_nm=distance,
                sea_days=0, port_days=0, total_days=0,
                revenue=0, hire_cost=0, bunker_cost=0, port_cost=0, commission=0,
                profit=0, tce=0,
                feasible=False,
                hire_rate=hire_rate,
                quantity=quantity,
                freight_rate=freight_rate,
                infeasibility_reason=str(e)
            )
    
    def _check_laycan(self, vessel: Dict, cargo: Dict) -> bool:
        """Check if vessel can meet cargo laycan window."""
        try:
            vessel_etd = vessel.get('etd')
            if isinstance(vessel_etd, str):
                vessel_etd = datetime.strptime(vessel_etd, '%Y-%m-%d')
            elif isinstance(vessel_etd, pd.Timestamp):
                vessel_etd = vessel_etd.to_pydatetime()
            
            laycan_end = cargo.get('laycan_end')
            if isinstance(laycan_end, str):
                laycan_end = datetime.strptime(laycan_end, '%Y-%m-%d')
            elif isinstance(laycan_end, pd.Timestamp):
                laycan_end = laycan_end.to_pydatetime()
            
            if vessel_etd is None or laycan_end is None:
                return True
            
            # Estimate 7 days to reach load port
            estimated_arrival = vessel_etd + timedelta(days=7)
            return estimated_arrival <= laycan_end
        except:
            return True
    
    def _estimate_distance(self, load_port: str, discharge_port: str) -> float:
        """Estimate distance based on port regions."""
        region_distances = {
            ('West Africa', 'China'): 10500,
            ('Brazil', 'China'): 11500,
            ('Australia', 'China'): 4500,
            ('SE Asia', 'China'): 2500,
            ('Middle East', 'China'): 6500,
            ('India', 'China'): 5000,
        }
        
        load_region = self._get_region(load_port)
        discharge_region = self._get_region(discharge_port)
        
        for (r1, r2), dist in region_distances.items():
            if load_region == r1 and discharge_region == r2:
                return dist
            if load_region == r2 and discharge_region == r1:
                return dist
        
        return 8000
    
    def _get_region(self, port: str) -> str:
        """Determine region from port name."""
        if not port:
            return 'Unknown'
        port_lower = port.lower()
        if any(p in port_lower for p in ['kamsar', 'guinea', 'conakry']):
            return 'West Africa'
        if any(p in port_lower for p in ['itaguai', 'tubarao', 'brazil', 'santos']):
            return 'Brazil'
        if any(p in port_lower for p in ['hedland', 'dampier', 'australia', 'newcastle']):
            return 'Australia'
        if any(p in port_lower for p in ['qingdao', 'lianyungang', 'china', 'fangcheng', 'tianjin']):
            return 'China'
        if any(p in port_lower for p in ['singapore', 'map ta phut', 'thailand', 'vietnam']):
            return 'SE Asia'
        if any(p in port_lower for p in ['fujairah', 'uae', 'middle east', 'jebel']):
            return 'Middle East'
        if any(p in port_lower for p in ['india', 'vizag', 'paradip']):
            return 'India'
        return 'Unknown'
    
    def build_profit_matrix(
        self,
        bunker_price_change: float = 0,
        additional_port_days: int = 0,
        vessels: List[Dict] = None,
        cargoes: List[Dict] = None
    ) -> Tuple[np.ndarray, List[List[VoyageResult]]]:
        """Build profit matrix for all vessel-cargo combinations."""
        if vessels is None:
            vessels = self.all_vessels
        if cargoes is None:
            cargoes = self.all_cargoes
            
        n_vessels = len(vessels)
        n_cargoes = len(cargoes)
        
        profit_matrix = np.zeros((n_vessels, n_cargoes))
        voyage_results = [[None for _ in range(n_cargoes)] for _ in range(n_vessels)]
        
        for i, vessel in enumerate(vessels):
            for j, cargo in enumerate(cargoes):
                result = self.calculate_voyage(
                    vessel, cargo, bunker_price_change, additional_port_days
                )
                voyage_results[i][j] = result
                
                if result.feasible and result.tce > 0:
                    profit_matrix[i, j] = result.profit
                else:
                    profit_matrix[i, j] = -1e9
        
        return profit_matrix, voyage_results
    
    def optimize_lp(
        self,
        bunker_price_change: float = 0,
        additional_port_days: int = 0,
        cargill_only: bool = False,
        committed_only: bool = False,
        must_cover_committed: bool = True
    ) -> Dict[str, Any]:
        """
        Solve optimal fleet allocation using Linear Programming.
        """
        # Select vessels and cargoes
        if cargill_only:
            vessels = self.get_cargill_vessels()
        else:
            vessels = self.all_vessels
            
        if committed_only:
            cargoes = self.get_committed_cargoes()
        else:
            cargoes = self.all_cargoes
        
        n_vessels = len(vessels)
        n_cargoes = len(cargoes)
        
        if n_vessels == 0 or n_cargoes == 0:
            return {'status': 'error', 'error': 'No vessels or cargoes available'}
        
        # Build profit matrix
        profit_matrix, voyage_results = self.build_profit_matrix(
            bunker_price_change, additional_port_days, vessels, cargoes
        )
        
        # Create solver
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            return {'error': 'Could not create solver'}
        
        # Decision variables
        assign = {}
        for i in range(n_vessels):
            for j in range(n_cargoes):
                assign[i, j] = solver.BoolVar(f'assign_{i}_{j}')
        
        # Constraint 1: Each cargo assigned to at most 1 vessel
        for j in range(n_cargoes):
            solver.Add(sum(assign[i, j] for i in range(n_vessels)) <= 1)
        
        # Constraint 2: Each vessel assigned to at most 1 cargo
        for i in range(n_vessels):
            solver.Add(sum(assign[i, j] for j in range(n_cargoes)) <= 1)
        
        # Constraint 3: Committed cargoes MUST be assigned
        if must_cover_committed:
            for j, cargo in enumerate(cargoes):
                if cargo.get('cargo_type') == 'cargill':
                    feasible_vessels = [
                        i for i in range(n_vessels) 
                        if profit_matrix[i, j] > -1e8
                    ]
                    if feasible_vessels:
                        solver.Add(sum(assign[i, j] for i in range(n_vessels)) == 1)
        
        # Constraint 4: Infeasible assignments not allowed
        for i in range(n_vessels):
            for j in range(n_cargoes):
                if profit_matrix[i, j] < -1e8:
                    solver.Add(assign[i, j] == 0)
        
        # Objective: Maximize total profit
        objective = solver.Sum(
            profit_matrix[i, j] * assign[i, j]
            for i in range(n_vessels)
            for j in range(n_cargoes)
        )
        solver.Maximize(objective)
        
        # Solve
        status = solver.Solve()
        
        if status == pywraplp.Solver.OPTIMAL:
            assignments = []
            total_profit = 0
            total_tce = 0
            assigned_count = 0
            
            for i in range(n_vessels):
                for j in range(n_cargoes):
                    if assign[i, j].solution_value() > 0.5:
                        voyage = voyage_results[i][j]
                        assignments.append(voyage)
                        total_profit += voyage.profit
                        total_tce += voyage.tce
                        assigned_count += 1
            
            avg_tce = total_tce / assigned_count if assigned_count > 0 else 0
            
            assigned_vessels = {a.vessel for a in assignments}
            assigned_cargoes = {a.cargo for a in assignments}
            
            unassigned_vessels = [
                v.get('name', v.get('vessel_name')) for v in vessels 
                if v.get('name', v.get('vessel_name')) not in assigned_vessels
            ]
            unassigned_cargoes = [
                c['cargo_id'] for c in cargoes if c['cargo_id'] not in assigned_cargoes
            ]
            
            return {
                'status': 'optimal',
                'assignments': assignments,
                'total_profit': total_profit,
                'avg_tce': avg_tce,
                'vessels_assigned': assigned_count,
                'unassigned_vessels': unassigned_vessels,
                'unassigned_cargoes': unassigned_cargoes,
                'bunker_price_change': bunker_price_change,
                'additional_port_days': additional_port_days,
                'strategy': 'cargill_only' if cargill_only else 'mixed_fleet'
            }
        else:
            return {
                'status': 'infeasible',
                'error': 'No feasible solution found',
                'assignments': [],
                'total_profit': 0
            }
    
    def compare_strategies(
        self,
        bunker_price_change: float = 0,
        additional_port_days: int = 0
    ) -> Dict[str, Any]:
        """Compare Cargill-only vs Mixed Fleet strategies."""
        
        # Strategy 1: Cargill vessels only, committed cargoes only
        cargill_only = self.optimize_lp(
            bunker_price_change=bunker_price_change,
            additional_port_days=additional_port_days,
            cargill_only=True,
            committed_only=True
        )
        
        # Strategy 2: Mixed fleet, committed cargoes only
        mixed_committed = self.optimize_lp(
            bunker_price_change=bunker_price_change,
            additional_port_days=additional_port_days,
            cargill_only=False,
            committed_only=True
        )
        
        # Strategy 3: Mixed fleet, all cargoes
        mixed_all = self.optimize_lp(
            bunker_price_change=bunker_price_change,
            additional_port_days=additional_port_days,
            cargill_only=False,
            committed_only=False,
            must_cover_committed=True
        )
        
        strategies = {
            'cargill_only': cargill_only,
            'mixed_committed': mixed_committed,
            'mixed_all': mixed_all
        }
        
        best_strategy = max(
            strategies.items(),
            key=lambda x: x[1].get('total_profit', -1e9)
        )
        
        baseline_profit = cargill_only.get('total_profit', 0)
        best_profit = best_strategy[1].get('total_profit', 0)
        improvement = best_profit - baseline_profit
        improvement_pct = (improvement / baseline_profit * 100) if baseline_profit > 0 else 0
        
        return {
            'strategies': strategies,
            'best_strategy': best_strategy[0],
            'best_result': best_strategy[1],
            'baseline_profit': baseline_profit,
            'best_profit': best_profit,
            'improvement': improvement,
            'improvement_pct': improvement_pct,
            'recommendation': self._generate_recommendation(
                cargill_only, mixed_all, bunker_price_change
            )
        }
    
    def _generate_recommendation(
        self,
        cargill_only: Dict,
        mixed_all: Dict,
        bunker_price_change: float
    ) -> str:
        """Generate natural language recommendation."""
        cargill_profit = cargill_only.get('total_profit', 0)
        mixed_profit = mixed_all.get('total_profit', 0)
        
        if mixed_profit > cargill_profit * 1.1:
            return (
                f"STRONG RECOMMENDATION: Use Mixed Fleet strategy. "
                f"Potential additional profit of ${mixed_profit - cargill_profit:,.0f} "
                f"({(mixed_profit/cargill_profit - 1)*100:.1f}% improvement)."
            )
        elif mixed_profit > cargill_profit * 1.02:
            return (
                f"MODERATE RECOMMENDATION: Consider Mixed Fleet strategy. "
                f"Potential additional profit of ${mixed_profit - cargill_profit:,.0f}."
            )
        else:
            return (
                f"RECOMMENDATION: Cargill-only strategy is optimal. "
                f"Mixed fleet offers minimal improvement."
            )
    
    def calculate_thresholds(
        self,
        vessel: Dict,
        cargo: Dict,
        base_bunker_change: float = 0,
        base_port_days: int = 0
    ) -> Dict[str, Any]:
        """Calculate threshold points where decisions should change."""
        base_result = self.calculate_voyage(vessel, cargo, base_bunker_change, base_port_days)
        
        # Find bunker threshold (where TCE drops below $15,000)
        bunker_threshold_pct = None
        for pct in range(0, 100, 5):
            result = self.calculate_voyage(vessel, cargo, pct/100, base_port_days)
            if result.tce < 15000:
                bunker_threshold_pct = pct
                break
        
        # Find port delay threshold (where profit becomes negative)
        port_threshold = None
        for days in range(0, 20):
            result = self.calculate_voyage(vessel, cargo, base_bunker_change, days)
            if result.profit < 0:
                port_threshold = days
                break
        
        # Find breakeven bunker price
        breakeven_bunker = None
        for pct in range(-50, 100, 2):
            result = self.calculate_voyage(vessel, cargo, pct/100, base_port_days)
            if result.profit < 0:
                breakeven_bunker = VLSFO_PRICE * (1 + pct/100)
                break
        
        return {
            'base_tce': base_result.tce,
            'base_profit': base_result.profit,
            'bunker_threshold_pct': bunker_threshold_pct,
            'bunker_threshold_price': VLSFO_PRICE * (1 + bunker_threshold_pct/100) if bunker_threshold_pct else None,
            'port_delay_threshold_days': port_threshold,
            'breakeven_bunker_price': breakeven_bunker
        }
    
    def find_better_options(
        self,
        bunker_price_change: float = 0,
        additional_port_days: int = 0
    ) -> Dict[str, Any]:
        """
        Answer: "Given Cargill with Cargill cargo, is there a better option?"
        
        Compares current Cargill-only allocation with all possible alternatives.
        """
        # Get baseline (Cargill only)
        baseline = self.optimize_lp(
            bunker_price_change=bunker_price_change,
            additional_port_days=additional_port_days,
            cargill_only=True,
            committed_only=True
        )
        
        # Get best mixed strategy
        mixed = self.optimize_lp(
            bunker_price_change=bunker_price_change,
            additional_port_days=additional_port_days,
            cargill_only=False,
            committed_only=False,
            must_cover_committed=True
        )
        
        # Find specific improvements
        improvements = []
        
        baseline_assignments = {a.cargo: a for a in baseline.get('assignments', [])}
        mixed_assignments = {a.cargo: a for a in mixed.get('assignments', [])}
        
        for cargo_id, mixed_voyage in mixed_assignments.items():
            baseline_voyage = baseline_assignments.get(cargo_id)
            
            if baseline_voyage:
                if mixed_voyage.vessel != baseline_voyage.vessel:
                    profit_diff = mixed_voyage.profit - baseline_voyage.profit
                    if profit_diff > 0:
                        improvements.append({
                            'cargo': cargo_id,
                            'current_vessel': baseline_voyage.vessel,
                            'current_tce': baseline_voyage.tce,
                            'better_vessel': mixed_voyage.vessel,
                            'better_tce': mixed_voyage.tce,
                            'profit_improvement': profit_diff
                        })
        
        # Find additional opportunities (market cargoes for Cargill vessels)
        additional_opportunities = []
        for voyage in mixed.get('assignments', []):
            if voyage.cargo_type == 'market' and voyage.vessel_type == 'cargill':
                additional_opportunities.append({
                    'vessel': voyage.vessel,
                    'cargo': voyage.cargo,
                    'tce': voyage.tce,
                    'profit': voyage.profit
                })
        
        return {
            'baseline': baseline,
            'optimized': mixed,
            'baseline_profit': baseline.get('total_profit', 0),
            'optimized_profit': mixed.get('total_profit', 0),
            'total_improvement': mixed.get('total_profit', 0) - baseline.get('total_profit', 0),
            'specific_improvements': improvements,
            'additional_opportunities': additional_opportunities,
            'has_better_option': mixed.get('total_profit', 0) > baseline.get('total_profit', 0) * 1.01
        }


def format_voyage_detail(voyage: VoyageResult, thresholds: Dict = None) -> str:
    """Format a voyage result as detailed text output."""
    output = []
    
    vessel_emoji = "🚢" if voyage.vessel_type == 'cargill' else "🏪"
    cargo_emoji = "📦" if voyage.cargo_type == 'cargill' else "📋"
    
    output.append(f"\n{vessel_emoji} {voyage.vessel} → {cargo_emoji} {voyage.cargo}")
    output.append("=" * 60)
    
    output.append(f"Route: {voyage.route} ({voyage.distance_nm:,.0f} NM)")
    output.append(f"Sea Days: {voyage.sea_days:.1f} | Port Days: {voyage.port_days:.1f} | Total: {voyage.total_days:.1f} days")
    output.append("")
    
    output.append("FINANCIAL BREAKDOWN:")
    output.append(f"  Revenue:      ${voyage.revenue:>12,.0f}")
    output.append(f"  Hire Cost:    ${voyage.hire_cost:>12,.0f}")
    output.append(f"  Bunker Cost:  ${voyage.bunker_cost:>12,.0f}")
    output.append(f"  Port Cost:    ${voyage.port_cost:>12,.0f}")
    output.append(f"  Commission:   ${voyage.commission:>12,.0f}")
    output.append(f"  {'─' * 30}")
    output.append(f"  PROFIT:       ${voyage.profit:>12,.0f}")
    output.append(f"  TCE:          ${voyage.tce:>12,.0f}/day")
    
    if thresholds:
        output.append("")
        output.append("⚠️ THRESHOLD ALERTS:")
        if thresholds.get('bunker_threshold_price'):
            output.append(f"  • If bunker rises above ${thresholds['bunker_threshold_price']:,.0f}/MT, TCE drops below $15,000/day")
        if thresholds.get('port_delay_threshold_days'):
            output.append(f"  • If port delays exceed {thresholds['port_delay_threshold_days']} days, profit becomes negative")
        if thresholds.get('breakeven_bunker_price'):
            output.append(f"  • Breakeven bunker price: ${thresholds['breakeven_bunker_price']:,.0f}/MT")
    
    return "\n".join(output)


def format_comparison_result(comparison: Dict[str, Any]) -> str:
    """Format strategy comparison as detailed text output."""
    output = []
    
    output.append("\n" + "=" * 70)
    output.append("📊 STRATEGY COMPARISON ANALYSIS")
    output.append("=" * 70)
    
    output.append("\n┌─────────────────────┬──────────────┬──────────────┬─────────┐")
    output.append("│ Strategy            │ Total Profit │ Avg TCE      │ Vessels │")
    output.append("├─────────────────────┼──────────────┼──────────────┼─────────┤")
    
    for name, result in comparison['strategies'].items():
        if result.get('status') == 'optimal':
            profit = result.get('total_profit', 0)
            tce = result.get('avg_tce', 0)
            vessels = result.get('vessels_assigned', 0)
            label = name.replace('_', ' ').title()
            marker = " ✅" if name == comparison['best_strategy'] else ""
            output.append(f"│ {label:<19} │ ${profit:>10,.0f} │ ${tce:>10,.0f} │ {vessels:>7} │{marker}")
    
    output.append("└─────────────────────┴──────────────┴──────────────┴─────────┘")
    
    output.append(f"\n💰 IMPROVEMENT POTENTIAL:")
    output.append(f"   Baseline (Cargill-only): ${comparison['baseline_profit']:,.0f}")
    output.append(f"   Best Strategy:           ${comparison['best_profit']:,.0f}")
    output.append(f"   Additional Profit:       ${comparison['improvement']:,.0f} (+{comparison['improvement_pct']:.1f}%)")
    
    output.append(f"\n📋 {comparison['recommendation']}")
    
    return "\n".join(output)


def format_better_options(result: Dict[str, Any]) -> str:
    """Format the 'is there a better option' analysis."""
    output = []
    
    output.append("\n" + "=" * 70)
    output.append("🔄 ALTERNATIVE OPTIONS ANALYSIS")
    output.append("=" * 70)
    
    output.append(f"\nCurrent Allocation (Cargill Fleet → Cargill Cargoes):")
    output.append(f"  Total Profit: ${result['baseline_profit']:,.0f}")
    
    if result['has_better_option']:
        output.append(f"\n✅ BETTER OPTIONS FOUND!")
        output.append(f"\nOptimized Allocation (Mixed Fleet Strategy):")
        output.append(f"  Total Profit: ${result['optimized_profit']:,.0f}")
        output.append(f"  Improvement:  ${result['total_improvement']:,.0f} (+{result['total_improvement']/result['baseline_profit']*100:.1f}%)")
        
        if result['specific_improvements']:
            output.append(f"\n📈 SPECIFIC IMPROVEMENTS:")
            for imp in result['specific_improvements']:
                output.append(f"  • {imp['cargo']}: Switch from {imp['current_vessel']} to {imp['better_vessel']}")
                output.append(f"    TCE: ${imp['current_tce']:,.0f} → ${imp['better_tce']:,.0f} (+${imp['profit_improvement']:,.0f})")
        
        if result['additional_opportunities']:
            output.append(f"\n🎯 ADDITIONAL OPPORTUNITIES (Market Cargoes for Cargill Vessels):")
            for opp in result['additional_opportunities']:
                output.append(f"  • {opp['vessel']} → {opp['cargo']}: TCE ${opp['tce']:,.0f}/day, Profit ${opp['profit']:,.0f}")
    else:
        output.append(f"\n✅ Current Cargill-only allocation is optimal or near-optimal.")
        output.append(f"   Mixed fleet offers minimal improvement.")
    
    return "\n".join(output)


# Test function
if __name__ == "__main__":
    print("Testing LP Optimizer...")
    
    optimizer = FleetOptimizer()
    
    print(f"\nData loaded:")
    print(f"  Vessels: {len(optimizer.all_vessels)} ({len(optimizer.get_cargill_vessels())} Cargill, {len(optimizer.get_market_vessels())} Market)")
    print(f"  Cargoes: {len(optimizer.all_cargoes)} ({len(optimizer.get_committed_cargoes())} Committed, {len(optimizer.get_spot_cargoes())} Spot)")
    
    print("\n1. Testing Cargill-only optimization...")
    result = optimizer.optimize_lp(cargill_only=True, committed_only=True)
    print(f"   Status: {result['status']}")
    print(f"   Total Profit: ${result.get('total_profit', 0):,.0f}")
    print(f"   Assignments: {len(result.get('assignments', []))}")
    
    print("\n2. Testing strategy comparison...")
    comparison = optimizer.compare_strategies()
    print(f"   Best Strategy: {comparison['best_strategy']}")
    print(f"   Improvement: ${comparison['improvement']:,.0f}")
    
    print("\n3. Testing 'better options' analysis...")
    better = optimizer.find_better_options()
    print(f"   Has better option: {better['has_better_option']}")
    print(f"   Potential improvement: ${better['total_improvement']:,.0f}")
    
    print("\n4. Full comparison output:")
    print(format_comparison_result(comparison))
    
    print("\n5. Better options output:")
    print(format_better_options(better))
    
    print("\nLP Optimizer test complete!")
