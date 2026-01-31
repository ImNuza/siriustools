# Cargill Voyage Assistant: Documentation

**Version:** 1.0
**Date:** January 31, 2026

---

## 1. Team Members & Responsibilities

| Member | Role | Responsibilities |
|---|---|---|
| Cindy | Project Manager | Project planning, coordination, final report |
| Chelsea | Data Scientist | Data cleaning, feature engineering, model validation |
| **Nuza** | **Lead Developer** | **Chatbot UI, optimization model, AI integration** |
| John | Business Analyst | Commercial insights, scenario analysis, presentation |
| Jane | UX/UI Designer | Chatbot design, user experience, visualizations |

---

## 2. File Structure

The project is organized into the following structure:

```
/siriustools
├── chatbot/              # Main Streamlit application
│   ├── app.py            # Core chatbot UI and logic
│   ├── ai_assistant.py   # Featherless.ai integration
│   └── guardrails.py     # Security and content filters
│
├── data/                 # All raw data files
│   ├── cargoes.json
│   ├── vessels.json
│   ├── port_distances.csv
│   ├── ffa_rates.csv
│   └── bunker_prices.csv
│
├── src/                  # Core optimization and data modules
│   ├── data_loader.py    # Loads and cleans all data
│   ├── lp_optimizer.py   # OR-Tools linear programming model
│   └── optimization.py   # Business logic and calculations
│
├── notebooks/            # Jupyter notebooks for exploration
│   └── 1_Data_Exploration.ipynb
│
├── requirements.txt      # Python dependencies
└── README.md             # Project overview
```

---

## 3. How to Reproduce Results

To set up the environment and run the chatbot, follow these steps:

### Step 1: Clone the Repository

```bash
git clone https://github.com/ImNuza/siriustools.git
cd siriustools
```

### Step 2: Install Dependencies

Make sure you have Python 3.9+ installed. Then, run:

```bash
pip install -r requirements.txt
```

### Step 3: Run the Chatbot

To start the Streamlit application, run the following command from the `siriustools` root directory:

```bash
streamlit run chatbot/app.py
```

The application will be available at `http://localhost:8501`.

### Step 4: Using the Chatbot

1. **Apply Scenario:** Click the "Active: Base Scenario" button to run the initial optimization.
2. **Ask Questions:** Use the chat input to ask questions like:
   - "Show recommendations"
   - "Compare fleet options"
   - "What if bunker prices increase 10%?"
3. **Enable AI Mode:** Toggle the "Enable AI-Enhanced Mode" switch in the sidebar to get natural language summaries with your responses.

---

## 4. Key Assumptions

- **Bunker Prices:** Based on the provided forward curve for February 2026.
- **Port Times:** Assumes a standard of 2 days for loading and 2 days for discharging, plus any additional scenario delays.
- **Vessel Speeds:** Assumes a standard laden speed of 12 knots and ballast speed of 13 knots.
- **Commissions:** A standard 3.75% commission is applied to all voyage revenues.
