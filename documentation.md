# Cargill Voyage Assistant: Documentation

**Team:** Sirius
**Version:** 1.0
**Date:** January 31, 2026

---

## 1. Team Members & Responsibilities

| Member | Role | Responsibilities |
|--------|------|------------------|
| **Dewa** | **Team Leader** | Project coordination, strategic direction, final review |
| Matthew | Data Analyst | Data validation, scenario analysis, model testing |
| Steven | Software Engineer | Chatbot development, optimization model, AI integration |
| Chelsea | Business Analyst | Commercial insights, market analysis, presentation |
| Cindy | Financial Analyst | Cost calculations, profit analysis, report writing |

---

## 2. File Structure

```
siriustools/
├── chatbot/                  # Main Streamlit application
│   ├── app.py                # Core chatbot UI and logic
│   ├── ai_assistant.py       # Featherless.ai API integration
│   └── guardrails.py         # Security and content filters
│
├── data/raw/                 # All raw data files
│   ├── cargoes.json          # Cargo information
│   ├── vessels.json          # Vessel specifications
│   ├── Port Distances.csv    # Port-to-port distances
│   ├── ffa_rates.json        # Forward Freight Agreement rates
│   └── bunker_prices.json    # Bunker fuel prices
│
├── src/                      # Core optimization modules
│   ├── data_loader.py        # Data loading and cleaning
│   ├── lp_optimizer.py       # OR-Tools linear programming model
│   ├── optimization.py       # Voyage calculation logic
│   └── freight_calculator.py # TCE and profit calculations
│
├── notebooks/                # Jupyter notebooks
│   └── Sirius_Tools_Datathon_Submission.ipynb
│
├── requirements.txt          # Python dependencies
├── README.md                 # Project overview
└── documentation.md          # This file
```

---

## 3. How to Reproduce Results

### Prerequisites

- **Python 3.9 or higher** (3.10+ recommended)
- **pip** (Python package manager)
- **Git** (for cloning the repository)

---

### For Windows Users

#### Step 1: Clone the Repository

Open **Command Prompt** or **PowerShell** and run:

```cmd
git clone https://github.com/ImNuza/siriustools.git
cd siriustools
```

#### Step 2: Create Virtual Environment (Recommended)

```cmd
python -m venv venv
venv\Scripts\activate
```

#### Step 3: Install Dependencies

```cmd
pip install -r requirements.txt
```

#### Step 4: Run the Chatbot

```cmd
streamlit run chatbot/app.py
```

The application will open automatically at `http://localhost:8501`.

---

### For macOS/Linux Users

#### Step 1: Clone the Repository

Open **Terminal** and run:

```bash
git clone https://github.com/ImNuza/siriustools.git
cd siriustools
```

#### Step 2: Create Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate
```

#### Step 3: Install Dependencies

```bash
pip3 install -r requirements.txt
```

#### Step 4: Run the Chatbot

```bash
streamlit run chatbot/app.py
```

The application will open automatically at `http://localhost:8501`.

---

### Running the Jupyter Notebook

To run the Jupyter notebook for detailed analysis:

**Windows:**
```cmd
jupyter notebook notebooks/Sirius_Tools_Datathon_Submission.ipynb
```

**macOS/Linux:**
```bash
jupyter notebook notebooks/Sirius_Tools_Datathon_Submission.ipynb
```

---

## 4. Using the Chatbot

1. **Apply Scenario:** Click the "Apply Scenario" button in the sidebar to run the initial optimization.

2. **Ask Questions:** Use the chat input to ask questions such as:
   - "Show recommendations"
   - "Compare fleet options"
   - "What if bunker prices increase 10%?"
   - "Show TCE heatmap"
   - "What are the thresholds?"

3. **Enable AI Mode (Optional):** Toggle "Enable AI-Enhanced Mode" in the sidebar to get natural language summaries powered by Qwen-72B.

4. **Adjust Scenarios:** Use the sidebar sliders to adjust:
   - Bunker price changes (-20% to +30%)
   - Additional port delay days (0 to 14 days)

---

## 5. Key Assumptions

| Parameter | Value | Source |
|-----------|-------|--------|
| VLSFO Price | $490/MT | Singapore benchmark (Feb 2026) |
| MGO Price | $649/MT | Singapore benchmark (Feb 2026) |
| Loading Time | 2 days | Industry standard |
| Discharge Time | 2 days | Industry standard |
| Weather Margin | 5% | Conservative estimate |
| Commission Rate | 3% | Standard industry rate |
| Eco Speed | 12 knots laden, 13 knots ballast | Vessel specifications |

---

## 6. Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| Port 8501 in use | Run `streamlit run chatbot/app.py --server.port 8502` |
| Streamlit not found | Ensure virtual environment is activated |
| Data not loading | Check that `data/raw/` folder contains all JSON/CSV files |

---

## 7. Contact

For questions or issues, contact Team Sirius via the datathon communication channels.
