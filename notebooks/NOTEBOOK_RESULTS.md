# Notebook Execution Results

## Optimization Results

**Optimal Allocation (2 Vessels, 2 Cargoes):**

| Vessel | Cargo | Commodity | TCE | Profit |
|--------|-------|-----------|-----|--------|
| OCEAN HORIZON | CARGILL_1 | Bauxite | $32,151/day | $1,358,354 |
| ANN BELL | CARGILL_3 | Iron Ore | $22,846/day | $1,012,536 |

**Total Portfolio Profit:** $2,370,890

## Key Findings

1. **Laycan Constraints:** Only 2 of 4 vessels (ANN BELL and OCEAN HORIZON) can meet the laycan windows
2. **Unassigned Cargo:** CARGILL_2 (Port Hedland Iron Ore) - recommend sublet to market
3. **Unassigned Vessels:** PACIFIC GLORY, GOLDEN ASCENT - seek spot market cargoes

## Charts Generated

1. `optimal_allocation.png` - Bar chart showing profit by vessel
2. `bunker_sensitivity.png` - Line chart showing profit vs bunker price

## Notebook Status

✅ Runs end-to-end without errors
✅ All visualizations generated
✅ Chatbot demo included
