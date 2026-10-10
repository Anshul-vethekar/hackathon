import os
import sys
import io

# Add reflow package directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from data_factory import (
    load_factory_data, copy_factory_data, DisruptionInput,
    minutes_to_clock, clock_to_minutes
)
from scheduler import schedule_baseline, schedule_recovery
from disruption import analyze_impact
from metrics import calculate_metrics, compare_metrics
from validation import validate_schedule

app = Flask(__name__)
CORS(app)

# Global State Container
state = {
    "factory_data": load_factory_data(),
    "baseline_result": None,
    "baseline_metrics": None,
}

def init_baseline():
    state["factory_data"] = load_factory_data()
    state["baseline_result"] = schedule_baseline(state["factory_data"])
    state["baseline_metrics"] = calculate_metrics(state["baseline_result"], state["factory_data"])

init_baseline()

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "app": "ReFlow Engine API"})

@app.route("/api/baseline", methods=["GET"])
def get_baseline():
    fdata = state["factory_data"]
    b_res = state["baseline_result"]
    b_met = state["baseline_metrics"]

    # Serialize machines
    machines = [
        {
            "id": m.machine_id,
            "name": m.name,
            "supported_operations": m.supported_operations,
            "shift_start": m.shift_start,
            "shift_end": m.shift_end,
            "maint_start": m.maint_start,
            "maint_end": m.maint_end,
            "maint_start_clock": minutes_to_clock(m.maint_start) if m.maint_start >= 0 else None,
            "maint_end_clock": minutes_to_clock(m.maint_end) if m.maint_end >= 0 else None
        }
        for m in fdata.machines.values()
    ]

    # Serialize work orders
    work_orders = [
        {
            "id": wo.work_order_id,
            "customer": wo.customer_name,
            "priority": wo.priority,
            "priority_level": wo.priority_level,
            "release_time": wo.release_time,
            "due_time": wo.due_time,
            "release_clock": minutes_to_clock(wo.release_time),
            "due_clock": minutes_to_clock(wo.due_time)
        }
        for wo in fdata.work_orders.values()
    ]

    # Serialize operations
    operations = [
        {
            "id": op.operation_id,
            "work_order_id": op.work_order_id,
            "stage_name": op.stage_name,
            "processing_duration": op.processing_duration,
            "compatible_machines": op.compatible_machines,
            "required_material_id": op.required_material_id,
            "required_material_qty": op.required_material_qty,
            "predecessors": op.predecessors
        }
        for op in fdata.operations.values()
    ]

    # Serialize baseline schedule
    schedule_items = []
    for op_id, sched in b_res.schedule.items():
        op = fdata.operations[op_id]
        wo = fdata.work_orders[op.work_order_id]
        schedule_items.append({
            "operation_id": op_id,
            "work_order_id": op.work_order_id,
            "customer": wo.customer_name,
            "priority": wo.priority,
            "stage_name": op.stage_name,
            "assigned_machine": sched["assigned_machine"],
            "start_time": sched["start_time"],
            "finish_time": sched["finish_time"],
            "start_clock": minutes_to_clock(sched["start_time"]),
            "finish_clock": minutes_to_clock(sched["finish_time"]),
            "duration": op.processing_duration,
            "due_clock": minutes_to_clock(wo.due_time)
        })

    metrics_data = {
        "total_work_orders": b_met.total_work_orders,
        "completed_work_orders": b_met.completed_work_orders,
        "late_work_orders": b_met.late_work_orders,
        "total_tardiness_minutes": b_met.total_tardiness_minutes,
        "total_tardiness_hours": b_met.total_tardiness_hours,
        "critical_orders_late": b_met.critical_orders_late,
        "critical_orders_at_risk": b_met.critical_orders_at_risk,
        "machine_utilization_pct": b_met.machine_utilization_pct,
        "machine_idle_hours": b_met.machine_idle_hours,
        "number_of_changeovers": b_met.number_of_changeovers,
        "moved_operations": b_met.moved_operations,
        "delayed_operations": b_met.delayed_operations,
        "unscheduled_operations": b_met.unscheduled_operations,
        "validation_status": b_met.validation_status
    }

    return jsonify({
        "machines": machines,
        "work_orders": work_orders,
        "operations": operations,
        "schedule": schedule_items,
        "metrics": metrics_data
    })

@app.route("/api/disruption/analyze", methods=["POST"])
def analyze_disruption_endpoint():
    data = request.get_json() or {}
    m_id = data.get("machine_id", "M1")
    bd_start = int(data.get("breakdown_start", 60))
    bd_dur = int(data.get("breakdown_duration", 240))
    shp_id = data.get("shipment_id", "SHP-01")
    shp_delay = int(data.get("shipment_delay_duration", 180))

    disruption = DisruptionInput(
        machine_id=m_id,
        breakdown_start=bd_start,
        breakdown_duration=bd_dur,
        shipment_id=shp_id,
        shipment_delay_duration=shp_delay
    )

    impact_res = analyze_impact(state["baseline_result"].schedule, state["factory_data"], disruption)

    op_impacts = []
    for op_id, imp in impact_res.operation_impacts.items():
        op_impacts.append({
            "operation_id": op_id,
            "work_order_id": imp.work_order_id,
            "stage_name": imp.stage_name,
            "assigned_machine": imp.assigned_machine,
            "baseline_start": imp.baseline_start,
            "baseline_finish": imp.baseline_finish,
            "baseline_start_clock": minutes_to_clock(imp.baseline_start),
            "baseline_finish_clock": minutes_to_clock(imp.baseline_finish),
            "cause": imp.cause,
            "is_directly_affected": imp.is_directly_affected,
            "is_downstream_affected": imp.is_downstream_affected,
            "detail": imp.detail,
            "deadline_risk": imp.deadline_risk
        })

    return jsonify({
        "summary_narrative": impact_res.summary_narrative,
        "directly_affected_op_ids": impact_res.directly_affected_op_ids,
        "downstream_affected_op_ids": impact_res.downstream_affected_op_ids,
        "unaffected_op_ids": impact_res.unaffected_op_ids,
        "affected_work_order_ids": impact_res.affected_work_order_ids,
        "work_orders_at_deadline_risk": impact_res.work_orders_at_deadline_risk,
        "operation_impacts": op_impacts
    })

@app.route("/api/recovery/schedule", methods=["POST"])
def schedule_recovery_endpoint():
    data = request.get_json() or {}
    strategy = data.get("strategy", "PLAN_A")
    disruption_data = data.get("disruption", {})
    
    m_id = disruption_data.get("machine_id", "M1")
    bd_start = int(disruption_data.get("breakdown_start", 60))
    bd_dur = int(disruption_data.get("breakdown_duration", 240))
    shp_id = disruption_data.get("shipment_id", "SHP-01")
    shp_delay = int(disruption_data.get("shipment_delay_duration", 180))

    disruption = DisruptionInput(
        machine_id=m_id,
        breakdown_start=bd_start,
        breakdown_duration=bd_dur,
        shipment_id=shp_id,
        shipment_delay_duration=shp_delay
    )

    rec_result = schedule_recovery(state["factory_data"], disruption, strategy=strategy)
    rec_metrics = calculate_metrics(rec_result, state["factory_data"], baseline_result=state["baseline_result"])
    comp = compare_metrics(state["baseline_metrics"], rec_metrics)

    fdata = state["factory_data"]
    b_sched = state["baseline_result"].schedule

    # Serialize recovery schedule
    rec_schedule_items = []
    for op_id, sched in rec_result.schedule.items():
        op = fdata.operations[op_id]
        wo = fdata.work_orders[op.work_order_id]
        b_op = b_sched.get(op_id, {})
        
        orig_m = b_op.get("assigned_machine", "N/A")
        orig_start = b_op.get("start_time", 0)
        orig_finish = b_op.get("finish_time", 0)
        
        moved = (sched["assigned_machine"] != orig_m or sched["start_time"] != orig_start)
        delayed = (sched["finish_time"] > orig_finish)
        
        status_label = "MOVED & DELAYED" if (moved and delayed) else ("MOVED" if moved else ("DELAYED" if delayed else "UNAFFECTED"))

        rec_schedule_items.append({
            "operation_id": op_id,
            "work_order_id": op.work_order_id,
            "customer": wo.customer_name,
            "priority": wo.priority,
            "stage_name": op.stage_name,
            "original_machine": orig_m,
            "assigned_machine": sched["assigned_machine"],
            "original_start": orig_start,
            "original_finish": orig_finish,
            "original_start_clock": minutes_to_clock(orig_start),
            "original_finish_clock": minutes_to_clock(orig_finish),
            "start_time": sched["start_time"],
            "finish_time": sched["finish_time"],
            "start_clock": minutes_to_clock(sched["start_time"]),
            "finish_clock": minutes_to_clock(sched["finish_time"]),
            "duration": op.processing_duration,
            "due_clock": minutes_to_clock(wo.due_time),
            "status_label": status_label
        })

    # Serialize validation checks
    val_report = rec_metrics.validation_report
    checks_data = [
        {
            "rule_number": c.rule_number,
            "rule_name": c.rule_name,
            "status": c.status,
            "message": c.message,
            "details": c.details
        }
        for c in val_report.checks
    ]

    # Serialize decision trace
    trace_data = [
        {
            "step_id": t.step_id,
            "operation_id": t.operation_id,
            "work_order_id": t.work_order_id,
            "priority": t.priority,
            "due_time": t.due_time,
            "due_clock": minutes_to_clock(t.due_time),
            "earliest_ready_time": t.earliest_ready_time,
            "earliest_ready_clock": minutes_to_clock(t.earliest_ready_time),
            "candidate_machines": t.candidate_machines,
            "selected_machine": t.selected_machine,
            "scheduled_start": t.scheduled_start,
            "scheduled_finish": t.scheduled_finish,
            "scheduled_start_clock": minutes_to_clock(t.scheduled_start) if t.scheduled_start is not None else None,
            "scheduled_finish_clock": minutes_to_clock(t.scheduled_finish) if t.scheduled_finish is not None else None,
            "decision_narrative": t.decision_narrative,
            "rejected_reasons": t.rejected_reasons
        }
        for t in rec_result.decision_trace
    ]

    return jsonify({
        "strategy_name": strategy,
        "schedule": rec_schedule_items,
        "unscheduled_ops": rec_result.unscheduled_ops,
        "metrics": {
            "total_work_orders": rec_metrics.total_work_orders,
            "completed_work_orders": rec_metrics.completed_work_orders,
            "late_work_orders": rec_metrics.late_work_orders,
            "total_tardiness_minutes": rec_metrics.total_tardiness_minutes,
            "total_tardiness_hours": rec_metrics.total_tardiness_hours,
            "critical_orders_late": rec_metrics.critical_orders_late,
            "critical_orders_at_risk": rec_metrics.critical_orders_at_risk,
            "machine_utilization_pct": rec_metrics.machine_utilization_pct,
            "machine_idle_hours": rec_metrics.machine_idle_hours,
            "number_of_changeovers": rec_metrics.number_of_changeovers,
            "moved_operations": rec_metrics.moved_operations,
            "delayed_operations": rec_metrics.delayed_operations,
            "unscheduled_operations": rec_metrics.unscheduled_operations,
            "validation_status": rec_metrics.validation_status
        },
        "comparison": {
            "tardiness_delta_minutes": comp.tardiness_delta_minutes,
            "tardiness_delta_hours": comp.tardiness_delta_hours,
            "late_orders_delta": comp.late_orders_delta,
            "critical_late_delta": comp.critical_late_delta,
            "moved_ops_count": comp.moved_ops_count,
            "delayed_ops_count": comp.delayed_ops_count,
            "utilization_delta_pct": comp.utilization_delta_pct,
            "idle_hours_delta": comp.idle_hours_delta,
            "tradeoff_summary": comp.tradeoff_summary
        },
        "validation": {
            "overall_status": val_report.overall_status,
            "is_feasible": val_report.is_feasible,
            "checks": checks_data
        },
        "decision_trace": trace_data
    })

@app.route("/api/export", methods=["GET"])
def export_csv_endpoint():
    strategy = request.args.get("strategy", "PLAN_A")
    m_id = request.args.get("machine_id", "M1")
    bd_start = int(request.args.get("breakdown_start", 60))
    bd_dur = int(request.args.get("breakdown_duration", 240))
    shp_id = request.args.get("shipment_id", "SHP-01")
    shp_delay = int(request.args.get("shipment_delay_duration", 180))

    disruption = DisruptionInput(
        machine_id=m_id,
        breakdown_start=bd_start,
        breakdown_duration=bd_dur,
        shipment_id=shp_id,
        shipment_delay_duration=shp_delay
    )

    rec_result = schedule_recovery(state["factory_data"], disruption, strategy=strategy)
    val_report = validate_schedule(rec_result.schedule, rec_result.unscheduled_ops, state["factory_data"], disruption)
    b_sched = state["baseline_result"].schedule

    rows = []
    for op_id, sched in rec_result.schedule.items():
        op = state["factory_data"].operations[op_id]
        wo = state["factory_data"].work_orders[op.work_order_id]
        b_op = b_sched.get(op_id, {})
        rows.append({
            "Scenario": "DISRUPTED_RECOVERY",
            "Strategy": strategy,
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
            "Feasibility_Status": val_report.overall_status
        })

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"reflow_recovery_schedule_{strategy}.csv"
    )

@app.route("/api/reset", methods=["POST"])
def reset_endpoint():
    init_baseline()
    return jsonify({"status": "reset", "message": "Baseline scenario reloaded successfully"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
