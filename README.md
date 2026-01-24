# Sirius Tools - Cargill-SMU Datathon 2026

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)

## Team Sirius

| Name | Role | School |
|------|------|--------|
| Xxdsanctuary | Lead Developer | Software Engineering |
| Nuza | Team Leader / Data Integrator | Information Systems |
| Member 3 | Data Integrator | Information Systems |
| Member 4 | Commercial Analyst | Business |
| Member 5 | Commercial Analyst | Accountancy |

---

## Project Overview

As **Dry Bulk Traders** at Cargill Ocean Transportation Singapore, we optimize the employment of **4 Capesize vessels** and allocate **3 committed cargoes** to maximize portfolio profit.

### Deliverables

1. **Freight Calculator** - Evaluates voyage profitability (TCE, profit)
2. **Voyage Optimization** - Optimal vessel-cargo allocation
3. **Scenario Analysis** - Bunker price & port delay sensitivity
4. **AI Chatbot** - Interactive assistant for voyage queries

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/ImNuza/siriustools.git
cd siriustools

# Install dependencies
pip install -r requirements.txt

# Run the optimization
cd src
python optimization.py

# Or run the full notebook
jupyter notebook notebooks/01_freight_calculator_and_optimization.ipynb

# Launch the chatbot
streamlit run chatbot/app.py
```

---

## Repository Structure

```
siriustools/
├── data/
│   ├── raw/                    # Original data files
│   │   ├── Port Distances.csv
│   │   └── Simple calculator.xlsx
│   └── processed/
├── notebooks/
│   └── 01_freight_calculator_and_optimization.ipynb
├── src/
│   ├── freight_calculator.py   # Core calculation (OOP classes)
│   ├── optimization.py         # Portfolio optimization engine
│   └── data_loader.py          # Data loading utilities
├── chatbot/
│   └── app.py                  # Streamlit chatbot
├── CODE_REVIEW.md              # Code review & improvements
├── requirements.txt
└── README.md
```

---

## Key Assumptions

| # | Assumption | Value | Source |
|---|------------|-------|--------|
| 1 | Vessel Speed | Economical | PPTX Slide 5-8 |
| 2 | Weather Margin | 5% | Industry standard |
| 3 | Bunker Price (VLSFO) | $490/MT | PPTX Slide 15 |
| 4 | Bunker Price (MGO) | $650/MT | PPTX Slide 15 |

---

## Timeline

| Date | Milestone |
|------|-----------|
| Jan 24 | Problem statement released |
| Jan 31 | Phase 1 submission |
| Feb 4 | Top 10 finalists announced |
| Feb 6 | Final presentations @ SMU |

---

## License

MIT License - Cargill-SMU BIA Datathon 2026
