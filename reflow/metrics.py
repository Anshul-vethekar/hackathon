from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from data_factory import FactoryData, DisruptionInput, minutes_to_clock
from scheduler import ScheduleResult
from validation import validate_schedule, ValidationReport

@dataclass
class ScheduleMetrics:
    total_work_orders: int
    completed_work_orders: int
    late_work_orders: int
    total_tardiness_minutes: int
    total_tardiness_hours: float
    critical_orders_late: int
    critical_orders_at_risk: int
    machine_utilization_pct: float
    machine_idle_hours: float
    number_of_changeovers: int
    moved_operations: int
    delayed_operations: int
    unscheduled_operations: int
    validation_status: str  # "PASS", "WARNING", "FAIL"
    validation_report: ValidationReport

@dataclass
class MetricComparison:
    baseline: ScheduleMetrics
    recovery: ScheduleMetrics
    tardiness_delta_minutes: int
    tardiness_delta_hours: float
    late_orders_delta: int
    critical_late_delta: int
    moved_ops_count: int
    delayed_ops_count: int
    utilization_delta_pct: float
    idle_hours_delta: float
    tradeoff_summary: str

def calculate_metrics(
    schedule_result: ScheduleResult,
    factory_data: FactoryData,
    baseline_result: Optional[ScheduleResult] = None
) -> ScheduleMetrics:
    schedule = schedule_result.schedule
    unscheduled = schedule_result.unscheduled_ops
    disruption = schedule_result.disruption_applied

    val_report = validate_schedule(schedule, unscheduled, factory_data, disruption)

    wo_completions: Dict[str, int] = {}
    wo_op_counts: Dict[str, int] = {wo_id: 0 for wo_id in factory_data.work_orders}
    scheduled_wo_op_counts: Dict[str, int] = {wo_id: 0 for wo_id in factory_data.work_orders}

    for op_id, op in factory_data.operations.items():
        wo_op_counts[op.work_order_id] += 1

    for op_id, sched in schedule.items():
        wo_id = sched["work_order_id"]
        scheduled_wo_op_counts[wo_id] += 1
        wo_completions[wo_id] = max(wo_completions.get(wo_id, 0), sched["finish_time"])

    total_wos = len(factory_data.work_orders)
    completed_wos = sum(1 for wo_id in factory_data.work_orders if scheduled_wo_op_counts[wo_id] == wo_op_counts[wo_id])

    late_wos = 0
    total_tardiness = 0
    critical_late = 0
    critical_at_risk = 0

    for wo_id, wo in factory_data.work_orders.items():
        if scheduled_wo_op_counts[wo_id] == wo_op_counts[wo_id]:
            comp = wo_completions[wo_id]
            if comp > wo.due_time:
                late_wos += 1
                tardiness = comp - wo.due_time
                total_tardiness += tardiness
                if wo.priority == "Critical":
                    critical_late += 1
                    critical_at_risk += 1
            elif comp >= wo.due_time - 30 and wo.priority == "Critical":
                critical_at_risk += 1
        else:
            if wo.priority == "Critical":
                critical_at_risk += 1

    total_processing_time = sum(sched["finish_time"] - sched["start_time"] for sched in schedule.values())

    total_avail_time = 0
    bd_machine = disruption.machine_id if disruption else None
    bd_dur = disruption.breakdown_duration if disruption else 0

    for m_id, m in factory_data.machines.items():
        avail = m.shift_end - m.shift_start
        if m.maint_start >= 0:
            avail -= (m.maint_end - m.maint_start)
        if bd_machine == m_id:
            avail -= bd_dur
        total_avail_time += max(0, avail)

    utilization_pct = (total_processing_time / total_avail_time * 100.0) if total_avail_time > 0 else 0.0
    idle_minutes = max(0, total_avail_time - total_processing_time)
    idle_hours = round(idle_minutes / 60.0, 2)

    changeovers = 0
    machine_ops: Dict[str, List[Tuple[int, str]]] = {m: [] for m in factory_data.machines}
    for op_id, sched in schedule.items():
        machine_ops[sched["assigned_machine"]].append((sched["start_time"], sched["work_order_id"]))

    for m_id, ops_list in machine_ops.items():
        ops_list.sort(key=lambda x: x[0])
        for i in range(len(ops_list) - 1):
            if ops_list[i][1] != ops_list[i+1][1]:
                changeovers += 1

    moved_ops = 0
    delayed_ops = 0

    if baseline_result:
        b_sched = baseline_result.schedule
        for op_id, sched in schedule.items():
            if op_id in b_sched:
                b_op = b_sched[op_id]
                if sched["start_time"] != b_op["start_time"] or sched["assigned_machine"] != b_op["assigned_machine"]:
                    moved_ops += 1
                if sched["finish_time"] > b_op["finish_time"]:
                    delayed_ops += 1

    return ScheduleMetrics(
        total_work_orders=total_wos,
        completed_work_orders=completed_wos,
        late_work_orders=late_wos,
        total_tardiness_minutes=total_tardiness,
        total_tardiness_hours=round(total_tardiness / 60.0, 2),
        critical_orders_late=critical_late,
        critical_orders_at_risk=critical_at_risk,
        machine_utilization_pct=round(utilization_pct, 1),
        machine_idle_hours=idle_hours,
        number_of_changeovers=changeovers,
        moved_operations=moved_ops,
        delayed_operations=delayed_ops,
        unscheduled_operations=len(unscheduled),
        validation_status=val_report.overall_status,
        validation_report=val_report
    )

def compare_metrics(baseline: ScheduleMetrics, recovery: ScheduleMetrics) -> MetricComparison:
    tard_delta_min = recovery.total_tardiness_minutes - baseline.total_tardiness_minutes
    tard_delta_hr = round(tard_delta_min / 60.0, 2)
    late_delta = recovery.late_work_orders - baseline.late_work_orders
    crit_delta = recovery.critical_orders_late - baseline.critical_orders_late
    util_delta = round(recovery.machine_utilization_pct - baseline.machine_utilization_pct, 1)
    idle_delta = round(recovery.machine_idle_hours - baseline.machine_idle_hours, 2)

    summary_parts = []
    if crit_delta < 0:
        summary_parts.append(f"Reduced critical order lateness by {abs(crit_delta)} orders.")
    elif crit_delta > 0:
        summary_parts.append(f"Critical order lateness increased by {crit_delta} orders.")
    else:
        summary_parts.append("Protected critical order delivery deadlines.")

    if tard_delta_min > 0:
        summary_parts.append(f"Total tardiness increased by {tard_delta_min}m ({tard_delta_hr}h) due to disruption impact.")
    elif tard_delta_min < 0:
        summary_parts.append(f"Reduced total tardiness by {abs(tard_delta_min)}m ({abs(tard_delta_hr)}h).")
    else:
        summary_parts.append("Maintained baseline tardiness level.")

    summary_parts.append(f"Rescheduled {recovery.moved_operations} operations across available machines.")

    return MetricComparison(
        baseline=baseline,
        recovery=recovery,
        tardiness_delta_minutes=tard_delta_min,
        tardiness_delta_hours=tard_delta_hr,
        late_orders_delta=late_delta,
        critical_late_delta=crit_delta,
        moved_ops_count=recovery.moved_operations,
        delayed_ops_count=recovery.delayed_operations,
        utilization_delta_pct=util_delta,
        idle_hours_delta=idle_delta,
        tradeoff_summary=" ".join(summary_parts)
    )
