# ReFlow — Production Recovery Intelligence

**ReFlow** is a production recovery intelligence application designed for manufacturing managers to analyze shop-floor disruptions (machine breakdowns and material shipment delays) and execute constraint-aware recovery strategies.

---

## 🚀 Quick Start Instructions

### 1. Prerequisites
- Python 3.10 or compatible installed Python version.

### 2. Installation
Open a terminal in the root folder (`c:\hachX`) and install required dependencies:
```bash
pip install -r reflow/requirements.txt
```

### 3. Launching the Dashboard
Run the Streamlit application:
```bash
streamlit run reflow/app.py
```
The interactive application will automatically open in your default browser at `http://localhost:8501`.

### 4. Running Automated Unit Tests
To execute the comprehensive 16-test suite verifying hard constraint compliance, scheduling logic, disruption analysis, and strategy differentiation:
```bash
python reflow/test_reflow.py
```
or using pytest:
```bash
python -m pytest reflow/test_reflow.py
```

---

## 🏗️ Project Architecture & File Structure

```
reflow/
├── app.py              # Streamlit dashboard layout, Plotly Gantt charts, user workflow
├── data_factory.py     # Seeded factory data models, CSV loaders, clock conversions
├── scheduler.py        # Baseline scheduler, Plan A & Plan B recovery list engine, decision trace
├── disruption.py       # Breakdown & delay evaluation, direct & downstream impact analysis
├── validation.py       # Independent validator enforcing 10 hard feasibility rules
├── metrics.py          # Production KPI calculations, baseline vs recovery metric deltas
├── test_reflow.py      # Automated unit test suite (16 tests + edge cases)
├── requirements.txt    # Python package dependencies
├── README.md           # Application documentation and operational guide
└── data/               # Seeded factory data CSV files
    ├── machines.csv
    ├── materials.csv
    ├── shipments.csv
    ├── work_orders.csv
    └── operations.csv
```

---

## 🏭 Operational Scenario & Time Model

- **Simulated Factory Day**: 08:00 AM to 06:00 PM (10 hours = 600 minutes).
- **Internal Time Unit**: Integer minutes relative to 08:00 AM (e.g., `0` = 08:00, `60` = 09:00, `240` = 12:00, `600` = 18:00).
- **Factory Scale**:
  - **4 Machines**: M1 (CNC Milling), M2 (CNC Lathe), M3 (Multi-Axis Machining Center with 10:00-10:30 maintenance window), M4 (Quality & Assembly Station).
  - **8 Work Orders**: Total 16 sequential operations spanning Critical, High, Medium, and Low priorities.
  - **Materials & Shipments**: `MAT-02` (Precision Bearings) arrives via Shipment `SHP-01` at 09:00 (minute 60).
- **Demonstration Disruption Event**:
  1. Machine `M1` breakdown at 09:00 (minute 60) for 4 hours (downtime window: 09:00 - 13:00 / min 60-300).
  2. Shipment `SHP-01` delayed by 3 hours (revised arrival: 12:00 / min 240).

---

## ⚙️ Scheduling Logic & Recovery Strategies

ReFlow uses a deterministic, constraint-aware heuristic list scheduler:

### 1. Hard Feasibility Validation Rules (10 Points)
1. **Machine Compatibility**: Operations assigned only to compatible machine types.
2. **Release Time Compliance**: Operations start at or after order release time.
3. **Precedence Satisfaction**: Dependent operations start after predecessor finish times.
4. **No Machine Overlaps**: Machine processes at most one operation at a time.
5. **Downtime Compliance**: Zero overlap with machine maintenance or breakdown windows.
6. **Material Readiness**: Operations start after required materials arrive.
7. **Inventory Bounds**: Material usage stays within available quantity.
8. **Shift Bounds**: All operations scheduled within 08:00-18:00 shift hours.
9. **Duration Consistency**: Operation start and finish match exact stage duration.
10. **Changeover Rules**: Safety intervals respected between work order transitions.

### 2. Recovery Strategies
- **PLAN A: Critical-Order Protection**:
  Prioritizes Critical work orders (`WO-01`, `WO-02`, `WO-08`) first. Reassigns alternative machines (e.g. M3) aggressively to minimize critical customer lateness.
- **PLAN B: Total Tardiness Reduction**:
  Prioritizes work orders by Apparent Tardiness / Slack (`due_time - remaining_duration`) to minimize cumulative global delay minutes across all orders.

---

## 📜 Decision Trace & Transparency

Every scheduling step records:
- Evaluated candidate machines and compatibility results.
- Shift, breakdown, maintenance, and machine overlap checks.
- Specific rejection reasons for unsuitable machine choices.
- Final placement rationale.

---

## 🏆 Demonstration Journey Summary

1. Launch application -> Inspect **Baseline Production Plan**.
2. Configure Breakdown (`M1`, 4 hours) and Material Delay (`SHP-01`, 3 hours).
3. Click **Analyze Disruption** -> Review direct vs downstream impact analysis.
4. Select **Plan A** or **Plan B** -> Click **Generate Recovery Schedule**.
5. Inspect revised Gantt chart, baseline delta metrics, and 10-point feasibility report.
6. Click **Approve Recovery Plan** or **Export Schedule CSV**.
