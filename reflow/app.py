import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import os
from typing import Optional, Dict, List, Tuple

from data_factory import (
    load_factory_data, copy_factory_data, DisruptionInput,
    minutes_to_clock, clock_to_minutes, FactoryData
)
from scheduler import schedule_baseline, schedule_recovery, ScheduleResult
from disruption import analyze_impact, ImpactAnalysisResult
from validation import validate_schedule, ValidationReport
from metrics import calculate_metrics, compare_metrics, ScheduleMetrics

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="ReFlow — Production Recovery Intelligence",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM INDUSTRIAL CSS ---
CUSTOM_CSS = """
<style>
    /* Dark Slate & Modern Industrial Styling */
    .main {
        background-color: #0F172A;
        color: #F8FAFC;
    }
    .stApp {
        background-color: #0F172A;
    }
    .reflow-header {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #334155;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    .reflow-title {
        color: #38BDF8;
        font-size: 32px;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .reflow-subtitle {
        color: #94A3B8;
        font-size: 15px;
        margin-top: 4px;
    }
    .section-card {
        background-color: #1E293B;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #334155;
        margin-bottom: 20px;
    }
    .badge-pass {
        background-color: #064E3B;
        color: #34D399;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 14px;
        border: 1px solid #059669;
    }
    .badge-warning {
        background-color: #78350F;
        color: #FBBF24;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 14px;
        border: 1px solid #D97706;
    }
    .badge-fail {
        background-color: #7F1D1D;
        color: #F87171;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 14px;
        border: 1px solid #DC2626;
    }
    .strategy-card {
        background-color: #1E293B;
        border: 2px solid #334155;
        border-radius: 12px;
        padding: 18px;
        transition: all 0.2s ease-in-out;
    }
    .strategy-card-selected {
        border: 2px solid #38BDF8;
        background-color: #0F2942;
    }
    .trace-entry {
        background-color: #0F172A;
        border-left: 4px solid #38BDF8;
        padding: 10px 14px;
        margin-bottom: 8px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 13px;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if "factory_data" not in st.session_state:
    st.session_state.factory_data = load_factory_data()

if "baseline_result" not in st.session_state:
    st.session_state.baseline_result = schedule_baseline(st.session_state.factory_data)

if "baseline_metrics" not in st.session_state:
    st.session_state.baseline_metrics = calculate_metrics(
        st.session_state.baseline_result,
        st.session_state.factory_data
    )

if "disruption_input" not in st.session_state:
    st.session_state.disruption_input = DisruptionInput()

if "impact_result" not in st.session_state:
    st.session_state.impact_result = None

if "selected_strategy" not in st.session_state:
    st.session_state.selected_strategy = "PLAN_A"

if "recovery_result" not in st.session_state:
    st.session_state.recovery_result = None

if "recovery_metrics" not in st.session_state:
    st.session_state.recovery_metrics = None

if "approved" not in st.session_state:
    st.session_state.approved = False

# --- HELPER FUNCTIONS ---
def reset_scenario():
    st.session_state.factory_data = load_factory_data()
    st.session_state.baseline_result = schedule_baseline(st.session_state.factory_data)
    st.session_state.baseline_metrics = calculate_metrics(
        st.session_state.baseline_result,
        st.session_state.factory_data
    )
    st.session_state.disruption_input = DisruptionInput()
    st.session_state.impact_result = None
    st.session_state.recovery_result = None
    st.session_state.recovery_metrics = None
    st.session_state.selected_strategy = "PLAN_A"
    st.session_state.approved = False

def create_gantt_chart(
    schedule_result: ScheduleResult,
    factory_data: FactoryData,
    title: str,
    disruption_input: Optional[DisruptionInput] = None
) -> go.Figure:
    """Creates an interactive Plotly Gantt timeline chart."""
    schedule = schedule_result.schedule
    fig = go.Figure()

    # Priority color map
    priority_colors = {
        "Critical": "#EF4444", # Red
        "High": "#F59E0B",     # Amber
        "Medium": "#3B82F6",   # Blue
        "Low": "#10B981"       # Green
    }

    machines = list(factory_data.machines.keys())

    # Add machine maintenance windows as grey background shapes
    for m_id, m in factory_data.machines.items():
        if m.maint_start >= 0 and m.maint_end > m.maint_start:
            fig.add_shape(
                type="rect",
                x0=m.maint_start,
                x1=m.maint_end,
                y0=machines.index(m_id) - 0.4,
                y1=machines.index(m_id) + 0.4,
                fillcolor="#475569",
                opacity=0.6,
                line=dict(width=0),
                layer="below"
            )
            fig.add_annotation(
                x=(m.maint_start + m.maint_end) / 2,
                y=m_id,
                text="Maintenance",
                showarrow=False,
                font=dict(color="#F8FAFC", size=10)
            )

    # Add Machine Breakdown overlay if disruption present
    if disruption_input and disruption_input.machine_id in machines:
        bd_m = disruption_input.machine_id
        bd_s = disruption_input.breakdown_start
        bd_e = disruption_input.breakdown_end
        fig.add_shape(
            type="rect",
            x0=bd_s,
            x1=bd_e,
            y0=machines.index(bd_m) - 0.45,
            y1=machines.index(bd_m) + 0.45,
            fillcolor="#DC2626",
            opacity=0.4,
            line=dict(color="#EF4444", width=2, dash="dash")
        )
        fig.add_annotation(
            x=(bd_s + bd_e) / 2,
            y=bd_m,
            text=f"⚠️ BREAKDOWN ({minutes_to_clock(bd_s)}-{minutes_to_clock(bd_e)})",
            showarrow=False,
            font=dict(color="#FFFFFF", size=11, family="sans-serif")
        )

    # Add operation bars
    for op_id, sched in schedule.items():
        op = factory_data.operations[op_id]
        wo = factory_data.work_orders[op.work_order_id]
        m_id = sched["assigned_machine"]
        
        start_t = sched["start_time"]
        finish_t = sched["finish_time"]
        
        color = priority_colors.get(wo.priority, "#3B82F6")
        
        hover_text = (
            f"<b>Op ID:</b> {op_id}<br>"
            f"<b>Work Order:</b> {op.work_order_id} ({wo.customer_name})<br>"
            f"<b>Priority:</b> {wo.priority}<br>"
            f"<b>Stage:</b> {op.stage_name}<br>"
            f"<b>Machine:</b> {m_id}<br>"
            f"<b>Time:</b> {minutes_to_clock(start_t)} - {minutes_to_clock(finish_t)} ({op.processing_duration}m)<br>"
            f"<b>Due Time:</b> {minutes_to_clock(wo.due_time)}"
        )

        fig.add_trace(go.Bar(
            name=f"{op_id} ({wo.priority})",
            y=[m_id],
            x=[finish_t - start_t],
            base=start_t,
            orientation='h',
            marker=dict(
                color=color,
                line=dict(color='#0F172A', width=1.5)
            ),
            text=f"{op_id} ({op.stage_name})",
            textposition='inside',
            insidetextanchor='middle',
            hoverinfo='text',
            hovertext=hover_text,
            showlegend=False
        ))

    # Time ticks format (every 60 minutes from 08:00 to 18:00)
    tick_vals = list(range(0, 660, 60))
    tick_texts = [minutes_to_clock(t) for t in tick_vals]

    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color="#F8FAFC")),
        xaxis=dict(
            title="Simulated Factory Time (08:00 - 18:00)",
            tickmode='array',
            tickvals=tick_vals,
            ticktext=tick_texts,
            range=[-10, 610],
            gridcolor='#334155',
            zerolinecolor='#334155'
        ),
        yaxis=dict(
            title="Machine Lanes",
            autorange="reversed",
            gridcolor='#334155'
        ),
        plot_bgcolor="#0F172A",
        paper_bgcolor="#1E293B",
        font=dict(color="#F8FAFC"),
        height=380,
        margin=dict(l=50, r=30, t=50, b=40)
    )

    return fig

# --- HEADER SECTION ---
st.markdown(
    """
    <div class="reflow-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 class="reflow-title">⚡ ReFlow — Production Recovery Intelligence</h1>
                <p class="reflow-subtitle">Real-Time Shop Floor Disruption Analysis & Constraint-Aware Rescheduling Engine</p>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Top Bar Controls
col_h1, col_h2 = st.columns([4, 1])
with col_h1:
    if st.session_state.recovery_result:
        st.markdown(f"**Current Status:** <span class='badge-pass'>Recovery Plan Generated ({st.session_state.selected_strategy})</span>", unsafe_allow_html=True)
    elif st.session_state.impact_result:
        st.markdown("**Current Status:** <span class='badge-warning'>Disruption Impact Analyzed</span>", unsafe_allow_html=True)
    else:
        st.markdown("**Current Status:** <span class='badge-pass'>Original Baseline Schedule (Immutable)</span>", unsafe_allow_html=True)

with col_h2:
    if st.button("⏪ Reset Scenario", key="top_reset_btn", use_container_width=True):
        reset_scenario()
        st.rerun()

st.divider()

# --- FACTORY OVERVIEW KPI CARDS ---
st.subheader("📊 Factory Operational Overview")
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

b_metrics = st.session_state.baseline_metrics
col_kpi1.metric("Work Orders", b_metrics.total_work_orders, help="Total active production work orders")
col_kpi2.metric("Active Machines", len(st.session_state.factory_data.machines), help="Shop floor machines")
col_kpi3.metric("Baseline Late Orders", b_metrics.late_work_orders, delta=0, delta_color="normal")
col_kpi4.metric("Baseline Total Tardiness", f"{b_metrics.total_tardiness_hours} hrs", delta="0.0 hrs", delta_color="normal")

st.divider()

# --- SECTION 1: ORIGINAL PRODUCTION PLAN ---
st.subheader("1. Original Production Schedule (Baseline)")
st.markdown("Immutable reference baseline schedule generated before any shop-floor disruption events.")

fig_baseline = create_gantt_chart(
    st.session_state.baseline_result,
    st.session_state.factory_data,
    "Baseline Schedule Timeline (08:00 - 18:00)"
)
st.plotly_chart(fig_baseline, use_container_width=True)

with st.expander("📋 View Baseline Work Orders & Operations Data Table"):
    b_table_data = []
    for op_id, sched in st.session_state.baseline_result.schedule.items():
        op = st.session_state.factory_data.operations[op_id]
        wo = st.session_state.factory_data.work_orders[op.work_order_id]
        b_table_data.append({
            "Op ID": op_id,
            "Work Order": op.work_order_id,
            "Customer": wo.customer_name,
            "Priority": wo.priority,
            "Stage": op.stage_name,
            "Machine": sched["assigned_machine"],
            "Start Time": minutes_to_clock(sched["start_time"]),
            "Finish Time": minutes_to_clock(sched["finish_time"]),
            "Duration (m)": op.processing_duration,
            "Due Time": minutes_to_clock(wo.due_time),
            "Material Required": op.required_material_id or "None"
        })
    st.dataframe(pd.DataFrame(b_table_data), use_container_width=True)

st.divider()

# --- SECTION 2: DISRUPTION EVENT CONFIGURATION ---
st.subheader("2. Disruption Event Configuration")
st.markdown("Configure simulated shop-floor disruptions to analyze direct and downstream impacts.")

with st.form("disruption_form"):
    col_d1, col_d2 = st.columns(2)
    
    with col_d1:
        st.markdown("### 🛠️ Machine Breakdown")
        m_options = list(st.session_state.factory_data.machines.keys())
        selected_m = st.selectbox("Affected Machine", options=m_options, index=0)
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            bd_start_str = st.text_input("Breakdown Start Time (HH:MM)", value="09:00")
        with col_m2:
            bd_dur_hrs = st.number_input("Downtime Duration (Hours)", min_value=1.0, max_value=8.0, value=4.0, step=0.5)

    with col_d2:
        st.markdown("### 📦 Material Shipment Delay")
        shp_options = list(st.session_state.factory_data.shipments.keys())
        selected_shp = st.selectbox("Delayed Shipment", options=shp_options, index=0)
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.text_input("Original Expected Arrival", value="09:00 (SHP-01)", disabled=True)
        with col_s2:
            shp_delay_hrs = st.number_input("Shipment Delay (Hours)", min_value=0.5, max_value=8.0, value=3.0, step=0.5)

    analyze_submitted = st.form_submit_button("⚡ Analyze Disruption", use_container_width=True)

if analyze_submitted:
    bd_start_min = clock_to_minutes(bd_start_str)
    bd_dur_min = int(bd_dur_hrs * 60)
    shp_delay_min = int(shp_delay_hrs * 60)

    st.session_state.disruption_input = DisruptionInput(
        machine_id=selected_m,
        breakdown_start=bd_start_min,
        breakdown_duration=bd_dur_min,
        shipment_id=selected_shp,
        shipment_delay_duration=shp_delay_min
    )

    st.session_state.impact_result = analyze_impact(
        st.session_state.baseline_result.schedule,
        st.session_state.factory_data,
        st.session_state.disruption_input
    )
    st.session_state.recovery_result = None
    st.session_state.recovery_metrics = None
    st.session_state.approved = False
    st.rerun()

st.divider()

# --- SECTION 3: DISRUPTION IMPACT ANALYSIS ---
if st.session_state.impact_result:
    impact: ImpactAnalysisResult = st.session_state.impact_result
    st.subheader("3. Disruption Impact Analysis")
    
    st.info(f"**Impact Summary:** {impact.summary_narrative}")

    col_imp1, col_imp2, col_imp3, col_imp4 = st.columns(4)
    col_imp1.metric("Directly Affected Ops", len(impact.directly_affected_op_ids), delta="Direct Conflict", delta_color="inverse")
    col_imp2.metric("Downstream Affected Ops", len(impact.downstream_affected_op_ids), delta="Precedence Delay", delta_color="inverse")
    col_imp3.metric("Impacted Work Orders", len(impact.affected_work_order_ids))
    col_imp4.metric("Orders at Deadline Risk", len(impact.work_orders_at_deadline_risk), delta="Risk Flag", delta_color="inverse")

    st.markdown("#### Affected Operations Impact Table")
    imp_table = []
    for op_id, op_imp in impact.operation_impacts.items():
        if op_imp.is_directly_affected or op_imp.is_downstream_affected:
            imp_table.append({
                "Op ID": op_id,
                "Work Order": op_imp.work_order_id,
                "Stage": op_imp.stage_name,
                "Assigned Machine": op_imp.assigned_machine,
                "Baseline Start": minutes_to_clock(op_imp.baseline_start),
                "Baseline Finish": minutes_to_clock(op_imp.baseline_finish),
                "Disruption Cause": op_imp.cause,
                "Cause Detail": op_imp.detail,
                "Deadline Risk": "⚠️ High Risk" if op_imp.deadline_risk else "Normal"
            })
    st.dataframe(pd.DataFrame(imp_table), use_container_width=True)

    st.divider()

    # --- SECTION 4: RECOVERY STRATEGY SELECTION ---
    st.subheader("4. Recovery Strategy Selection")
    st.markdown("Select a recovery strategy for the scheduling engine. The manager must explicitly trigger plan generation.")

    col_strat1, col_strat2 = st.columns(2)
    with col_strat1:
        st.markdown(
            """
            <div class="strategy-card">
                <h3 style="color:#38BDF8; margin-top:0;">PLAN A: Critical-Order Protection</h3>
                <p><b>Primary Objective:</b> Prioritize Critical customer work orders (AeroSpace, Medical, Precision Defense) and minimize their lateness.</p>
                <ul>
                    <li>Aggressively reassigns alternative machines (e.g. M3 Machining Center) for critical orders.</li>
                    <li>Accepts secondary delays on Low/Medium priority orders to protect critical deadlines.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col_strat2:
        st.markdown(
            """
            <div class="strategy-card">
                <h3 style="color:#FBBF24; margin-top:0;">PLAN B: Total Tardiness Reduction</h3>
                <p><b>Primary Objective:</b> Minimize total cumulative tardiness across all 8 shop-floor work orders globally.</p>
                <ul>
                    <li>Uses Apparent Tardiness / Slack scoring (due date vs remaining processing time).</li>
                    <li>Optimizes shop-floor throughput and minimizes global customer delay minutes.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True
        )

    col_sel1, col_sel2 = st.columns([2, 1])
    with col_sel1:
        selected_strat = st.radio(
            "Select Operational Strategy:",
            options=["PLAN_A", "PLAN_B"],
            format_func=lambda x: "PLAN A: Protect Critical Orders First" if x == "PLAN_A" else "PLAN B: Reduce Total Tardiness",
            horizontal=True
        )
        st.session_state.selected_strategy = selected_strat

    with col_sel2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 Generate Recovery Schedule", use_container_width=True, type="primary"):
            st.session_state.recovery_result = schedule_recovery(
                st.session_state.factory_data,
                st.session_state.disruption_input,
                strategy=st.session_state.selected_strategy
            )
            st.session_state.recovery_metrics = calculate_metrics(
                st.session_state.recovery_result,
                st.session_state.factory_data,
                baseline_result=st.session_state.baseline_result
            )
            st.rerun()

st.divider()

# --- SECTION 5: SELECTED RECOVERY SCHEDULE & RESULTS ---
if st.session_state.recovery_result:
    rec_res: ScheduleResult = st.session_state.recovery_result
    rec_metrics: ScheduleMetrics = st.session_state.recovery_metrics
    b_metrics: ScheduleMetrics = st.session_state.baseline_metrics
    comp = compare_metrics(b_metrics, rec_metrics)

    st.subheader(f"5. Rescheduled Recovery Production Plan ({rec_res.strategy_name})")

    fig_recovery = create_gantt_chart(
        rec_res,
        st.session_state.factory_data,
        f"Rescheduled Timeline — {rec_res.strategy_name}",
        disruption_input=st.session_state.disruption_input
    )
    st.plotly_chart(fig_recovery, use_container_width=True)

    with st.expander("📋 View Rescheduled Operations Detail Table"):
        r_table_data = []
        b_sched = st.session_state.baseline_result.schedule
        for op_id, sched in rec_res.schedule.items():
            op = st.session_state.factory_data.operations[op_id]
            wo = st.session_state.factory_data.work_orders[op.work_order_id]
            b_op = b_sched.get(op_id, {})
            
            orig_m = b_op.get("assigned_machine", "N/A")
            orig_start = minutes_to_clock(b_op.get("start_time", 0))
            
            moved = (sched["assigned_machine"] != orig_m or sched["start_time"] != b_op.get("start_time", 0))
            delayed = (sched["finish_time"] > b_op.get("finish_time", 0))

            status_label = "MOVED & DELAYED" if (moved and delayed) else ("MOVED" if moved else ("DELAYED" if delayed else "UNAFFECTED"))

            r_table_data.append({
                "Op ID": op_id,
                "Work Order": op.work_order_id,
                "Priority": wo.priority,
                "Stage": op.stage_name,
                "Original Machine": orig_m,
                "Revised Machine": sched["assigned_machine"],
                "Original Start": orig_start,
                "Revised Start": minutes_to_clock(sched["start_time"]),
                "Revised Finish": minutes_to_clock(sched["finish_time"]),
                "Status": status_label
            })
        st.dataframe(pd.DataFrame(r_table_data), use_container_width=True)

    st.divider()

    # --- SECTION 6: RESULTS COMPARISON & TRADE-OFFS ---
    st.subheader("6. Recovery Performance & Trade-Off Analysis")
    
    st.info(f"💡 **Trade-Off Assessment:** {comp.tradeoff_summary}")

    col_cmp1, col_cmp2, col_cmp3, col_cmp4, col_cmp5 = st.columns(5)
    
    col_cmp1.metric(
        "Total Tardiness",
        f"{rec_metrics.total_tardiness_hours} hrs",
        delta=f"{comp.tardiness_delta_hours} hrs",
        delta_color="inverse"
    )
    col_cmp2.metric(
        "Late Work Orders",
        rec_metrics.late_work_orders,
        delta=comp.late_orders_delta,
        delta_color="inverse"
    )
    col_cmp3.metric(
        "Critical Orders Late",
        rec_metrics.critical_orders_late,
        delta=comp.critical_late_delta,
        delta_color="inverse"
    )
    col_cmp4.metric(
        "Machine Utilization",
        f"{rec_metrics.machine_utilization_pct}%",
        delta=f"{comp.utilization_delta_pct}%"
    )
    col_cmp5.metric(
        "Moved Operations",
        rec_metrics.moved_operations,
        delta=f"{rec_metrics.delayed_operations} delayed",
        delta_color="off"
    )

    st.divider()

    # --- SECTION 7: DECISION SUPPORT & VALIDATION ---
    st.subheader("7. Hard Feasibility Validation & Decision Trace")

    val_rep: ValidationReport = rec_metrics.validation_report

    col_val1, col_val2 = st.columns([1, 2])
    with col_val1:
        if val_rep.overall_status == "PASS":
            st.markdown("<div class='badge-pass'>✅ FEASIBILITY STATUS: PASS</div><br>", unsafe_allow_html=True)
            st.success("All 10 non-negotiable hard constraints are fully satisfied.")
        elif val_rep.overall_status == "WARNING":
            st.markdown("<div class='badge-warning'>⚠️ FEASIBILITY STATUS: WARNING</div><br>", unsafe_allow_html=True)
            st.warning("Schedule is physically feasible, but order delivery deadlines are exceeded.")
        else:
            st.markdown("<div class='badge-fail'>❌ FEASIBILITY STATUS: FAIL</div><br>", unsafe_allow_html=True)
            st.error("Hard constraint violations detected! Schedule cannot be executed.")

    with col_val2:
        val_df = pd.DataFrame([
            {"Rule #": c.rule_number, "Constraint Check": c.rule_name, "Status": c.status, "Details": c.message}
            for c in val_rep.checks
        ])
        st.dataframe(val_df, use_container_width=True)

    with st.expander("🔍 Interactive Step-by-Step Decision Trace Log"):
        st.markdown("Detailed audit log explaining every machine placement choice and rejected candidate reasons:")
        for t in rec_res.decision_trace:
            st.markdown(
                f"""
                <div class="trace-entry">
                    <b>Step {t.step_id}:</b> Op <b>{t.operation_id}</b> ({t.work_order_id} - {t.priority}) | Ready Time: {minutes_to_clock(t.earliest_ready_time)}<br>
                    <b>Decision:</b> {t.decision_narrative}<br>
                    <span style="color:#94A3B8;">Candidate Rejections: {'; '.join(t.rejected_reasons) or 'None'}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.divider()

    # --- SECTION 8: MANAGER ACTIONS & EXPORT ---
    st.subheader("8. Manager Action & Schedule Export")

    col_act1, col_act2, col_act3, col_act4 = st.columns(4)

    with col_act1:
        if st.button("✅ Approve Recovery Plan", use_container_width=True, type="primary"):
            st.session_state.approved = True

    with col_act2:
        # Prepare CSV export
        export_rows = []
        b_sched = st.session_state.baseline_result.schedule
        for op_id, sched in rec_res.schedule.items():
            op = st.session_state.factory_data.operations[op_id]
            wo = st.session_state.factory_data.work_orders[op.work_order_id]
            b_op = b_sched.get(op_id, {})
            export_rows.append({
                "Scenario": "DISRUPTED_RECOVERY",
                "Strategy": rec_res.strategy_name,
                "Work_Order_ID": op.work_order_id,
                "Customer": wo.customer_name,
                "Priority": wo.priority,
                "Operation_ID": op_id,
                "Stage": op.stage_name,
                "Assigned_Machine": sched["assigned_machine"],
                "Original_Start": minutes_to_clock(b_op.get("start_time", 0)),
                "Original_Finish": minutes_to_clock(b_op.get("finish_time", 0)),
                "Revised_Start": minutes_to_clock(sched["start_time"]),
                "Revised_Finish": minutes_to_clock(sched["finish_time"]),
                "Delay_Minutes": sched["finish_time"] - b_op.get("finish_time", sched["finish_time"]),
                "Feasibility_Status": val_rep.overall_status
            })
        csv_buffer = io.StringIO()
        pd.DataFrame(export_rows).to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 Export Schedule CSV",
            data=csv_buffer.getvalue(),
            file_name=f"reflow_recovery_schedule_{rec_res.strategy_name}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col_act3:
        if st.button("🔄 Switch Strategy", use_container_width=True):
            st.session_state.selected_strategy = "PLAN_B" if rec_res.strategy_name == "PLAN_A" else "PLAN_A"
            st.session_state.recovery_result = schedule_recovery(
                st.session_state.factory_data,
                st.session_state.disruption_input,
                strategy=st.session_state.selected_strategy
            )
            st.session_state.recovery_metrics = calculate_metrics(
                st.session_state.recovery_result,
                st.session_state.factory_data,
                baseline_result=st.session_state.baseline_result
            )
            st.rerun()

    with col_act4:
        if st.button("⏪ Reset Scenario", key="bottom_reset_btn", use_container_width=True):
            reset_scenario()
            st.rerun()

    if st.session_state.approved:
        st.success("✅ **Plan Approved in Prototype:** Rescheduled recovery plan has been validated and dispatched to simulated shop-floor controllers.")
