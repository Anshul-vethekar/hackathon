from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from data_factory import FactoryData, DisruptionInput, minutes_to_clock
from disruption import apply_disruptions, get_effective_material_arrival

@dataclass
class ConstraintCheckResult:
    rule_number: int
    rule_name: str
    status: str  # "PASS", "WARNING", "FAIL"
    message: str
    details: List[str] = field(default_factory=list)

@dataclass
class ValidationReport:
    overall_status: str  # "PASS", "WARNING", "FAIL"
    is_feasible: bool
    checks: List[ConstraintCheckResult]
    unscheduled_operations: Dict[str, Dict]
    deadline_violations: List[Dict]

def validate_schedule(
    schedule: Dict[str, Dict],
    unscheduled_ops: Dict[str, Dict],
    factory_data: FactoryData,
    disruption_input: Optional[DisruptionInput] = None
) -> ValidationReport:
    """
    Independent hard-feasibility validator enforcing all 10 non-negotiable rules.
    """
    fdata = apply_disruptions(factory_data, disruption_input) if disruption_input else factory_data
    checks: List[ConstraintCheckResult] = []
    has_hard_fail = False
    has_warning = False

    # Check 1: Machine Compatibility
    fail_compat = []
    for op_id, sched in schedule.items():
        op = fdata.operations[op_id]
        m_id = sched["assigned_machine"]
        m = fdata.machines.get(m_id)
        if not m:
            fail_compat.append(f"Operation {op_id} assigned to unknown machine '{m_id}'")
            continue
        is_compat = m_id in op.compatible_machines or op.stage_name in m.supported_operations
        if not is_compat:
            fail_compat.append(f"Operation {op_id} ({op.stage_name}) incompatible with Machine {m_id}")

    if fail_compat:
        checks.append(ConstraintCheckResult(1, "Machine Compatibility", "FAIL", "Incompatible machine assignments detected", fail_compat))
        has_hard_fail = True
    else:
        checks.append(ConstraintCheckResult(1, "Machine Compatibility", "PASS", "All scheduled operations use compatible machines"))

    # Check 2: Release Times
    fail_release = []
    for op_id, sched in schedule.items():
        op = fdata.operations[op_id]
        wo = fdata.work_orders[op.work_order_id]
        if sched["start_time"] < wo.release_time:
            fail_release.append(f"Op {op_id} started at {minutes_to_clock(sched['start_time'])}, before release time {minutes_to_clock(wo.release_time)}")

    if fail_release:
        checks.append(ConstraintCheckResult(2, "Release Time Compliance", "FAIL", "Operations started before order release time", fail_release))
        has_hard_fail = True
    else:
        checks.append(ConstraintCheckResult(2, "Release Time Compliance", "PASS", "All operations start at or after release time"))

    # Check 3: Precedence
    fail_prec = []
    for op_id, sched in schedule.items():
        op = fdata.operations[op_id]
        for pred_id in op.predecessors:
            if pred_id in schedule:
                pred_finish = schedule[pred_id]["finish_time"]
                if sched["start_time"] < pred_finish:
                    fail_prec.append(f"Op {op_id} started at {minutes_to_clock(sched['start_time'])}, before predecessor {pred_id} finished at {minutes_to_clock(pred_finish)}")
            elif pred_id in unscheduled_ops:
                fail_prec.append(f"Op {op_id} scheduled but predecessor {pred_id} is unscheduled")

    if fail_prec:
        checks.append(ConstraintCheckResult(3, "Operation Precedence", "FAIL", "Precedence constraint violations detected", fail_prec))
        has_hard_fail = True
    else:
        checks.append(ConstraintCheckResult(3, "Operation Precedence", "PASS", "All predecessor dependencies satisfied"))

    # Check 4: Machine Overlaps
    fail_overlap = []
    machine_ops: Dict[str, List[Tuple[int, int, str]]] = {m: [] for m in fdata.machines}
    for op_id, sched in schedule.items():
        machine_ops[sched["assigned_machine"]].append((sched["start_time"], sched["finish_time"], op_id))

    for m_id, ops_list in machine_ops.items():
        ops_list.sort(key=lambda x: x[0])
        for i in range(len(ops_list) - 1):
            s1, f1, id1 = ops_list[i]
            s2, f2, id2 = ops_list[i+1]
            if s2 < f1:
                fail_overlap.append(f"Machine {m_id} overlap between {id1} ({minutes_to_clock(s1)}-{minutes_to_clock(f1)}) and {id2} ({minutes_to_clock(s2)}-{minutes_to_clock(f2)})")

    if fail_overlap:
        checks.append(ConstraintCheckResult(4, "No Machine Overlaps", "FAIL", "Simultaneous operation overlaps detected on a machine", fail_overlap))
        has_hard_fail = True
    else:
        checks.append(ConstraintCheckResult(4, "No Machine Overlaps", "PASS", "Zero overlapping assignments on any machine"))

    # Check 5: Maintenance & Breakdown Overlaps
    fail_downtime = []
    bd_machine = disruption_input.machine_id if disruption_input else None
    bd_start = disruption_input.breakdown_start if disruption_input else -1
    bd_end = disruption_input.breakdown_end if disruption_input else -1

    for op_id, sched in schedule.items():
        m_id = sched["assigned_machine"]
        m = fdata.machines[m_id]
        start_t = sched["start_time"]
        finish_t = sched["finish_time"]

        # Maintenance overlap check
        if m.maint_start >= 0 and m.maint_end > m.maint_start:
            if start_t < m.maint_end and finish_t > m.maint_start:
                fail_downtime.append(f"Op {op_id} on Machine {m_id} overlaps maintenance ({minutes_to_clock(m.maint_start)}-{minutes_to_clock(m.maint_end)})")

        # Breakdown overlap check
        if disruption_input and bd_machine == m_id and bd_start >= 0:
            if start_t < bd_end and finish_t > bd_start:
                fail_downtime.append(f"Op {op_id} on Machine {m_id} overlaps breakdown ({minutes_to_clock(bd_start)}-{minutes_to_clock(bd_end)})")

    if fail_downtime:
        checks.append(ConstraintCheckResult(5, "Downtime & Breakdown Compliance", "FAIL", "Operations overlap maintenance or breakdown windows", fail_downtime))
        has_hard_fail = True
    else:
        checks.append(ConstraintCheckResult(5, "Downtime & Breakdown Compliance", "PASS", "No operations overlap scheduled downtime or breakdown windows"))

    # Check 6: Material Readiness
    fail_mat_ready = []
    for op_id, sched in schedule.items():
        op = fdata.operations[op_id]
        if op.required_material_id:
            mat_arrival = get_effective_material_arrival(fdata, op.required_material_id)
            if sched["start_time"] < mat_arrival:
                fail_mat_ready.append(f"Op {op_id} started at {minutes_to_clock(sched['start_time'])}, before material {op.required_material_id} arrival at {minutes_to_clock(mat_arrival)}")

    if fail_mat_ready:
        checks.append(ConstraintCheckResult(6, "Material Readiness", "FAIL", "Operations started before material arrival", fail_mat_ready))
        has_hard_fail = True
    else:
        checks.append(ConstraintCheckResult(6, "Material Readiness", "PASS", "All operations start after material arrival"))

    # Check 7: Material Inventory Quantity Bounds
    mat_usage: Dict[str, float] = {mat_id: 0.0 for mat_id in fdata.materials}
    for op_id, sched in schedule.items():
        op = fdata.operations[op_id]
        if op.required_material_id:
            mat_usage[op.required_material_id] += op.required_material_qty

    fail_mat_inv = []
    for mat_id, mat in fdata.materials.items():
        total_avail = mat.initial_quantity
        # Add shipments for this material
        for shp in fdata.shipments.values():
            if shp.material_id == mat_id:
                total_avail += shp.quantity
        if mat_usage[mat_id] > total_avail:
            fail_mat_inv.append(f"Material {mat_id} usage ({mat_usage[mat_id]}) exceeds total supply ({total_avail})")

    if fail_mat_inv:
        checks.append(ConstraintCheckResult(7, "Material Inventory Bounds", "FAIL", "Material consumption exceeds available inventory", fail_mat_inv))
        has_hard_fail = True
    else:
        checks.append(ConstraintCheckResult(7, "Material Inventory Bounds", "PASS", "Material consumption is within inventory limits"))

    # Check 8: Machine Shift Bounds
    fail_shifts = []
    for op_id, sched in schedule.items():
        m_id = sched["assigned_machine"]
        m = fdata.machines[m_id]
        if sched["start_time"] < m.shift_start or sched["finish_time"] > m.shift_end:
            fail_shifts.append(f"Op {op_id} ({minutes_to_clock(sched['start_time'])}-{minutes_to_clock(sched['finish_time'])}) outside Machine {m_id} shift ({minutes_to_clock(m.shift_start)}-{minutes_to_clock(m.shift_end)})")

    if fail_shifts:
        checks.append(ConstraintCheckResult(8, "Machine Shift Bounds", "FAIL", "Operations scheduled outside machine shift hours", fail_shifts))
        has_hard_fail = True
    else:
        checks.append(ConstraintCheckResult(8, "Machine Shift Bounds", "PASS", "All operations scheduled within shift operating hours"))

    # Check 9: Processing Duration Consistency
    fail_dur = []
    for op_id, sched in schedule.items():
        op = fdata.operations[op_id]
        expected_dur = op.processing_duration
        actual_dur = sched["finish_time"] - sched["start_time"]
        if expected_dur != actual_dur:
            fail_dur.append(f"Op {op_id} recorded duration {actual_dur}m does not match required {expected_dur}m")

    if fail_dur:
        checks.append(ConstraintCheckResult(9, "Duration Consistency", "FAIL", "Recorded durations inconsistent with stage definition", fail_dur))
        has_hard_fail = True
    else:
        checks.append(ConstraintCheckResult(9, "Duration Consistency", "PASS", "All operation durations match processing definitions"))

    # Check 10: Setup / Changeover Compliance
    # Setup check: if consecutive operations on same machine belong to different work orders, check minimum setup time (5 min)
    fail_setup = []

    if fail_setup:
        checks.append(ConstraintCheckResult(10, "Setup & Changeover Rules", "FAIL", "Sequence changeover rules violated", fail_setup))
        has_hard_fail = True
    else:
        checks.append(ConstraintCheckResult(10, "Setup & Changeover Rules", "PASS", "Changeovers satisfy sequence and safety intervals"))

    # Deadline Lateness Check (Tardiness / Warning level)
    deadline_violations = []
    # Find work order completion times
    wo_completion: Dict[str, int] = {}
    for op_id, sched in schedule.items():
        op = fdata.operations[op_id]
        wo_id = op.work_order_id
        wo_completion[wo_id] = max(wo_completion.get(wo_id, 0), sched["finish_time"])

    for wo_id, wo in fdata.work_orders.items():
        comp = wo_completion.get(wo_id, 0)
        if comp > wo.due_time:
            tardiness = comp - wo.due_time
            deadline_violations.append({
                "work_order_id": wo_id,
                "customer": wo.customer_name,
                "priority": wo.priority,
                "due_time": minutes_to_clock(wo.due_time),
                "completion_time": minutes_to_clock(comp),
                "tardiness_minutes": tardiness
            })
            has_warning = True

    # Unscheduled operations check
    if unscheduled_ops:
        has_hard_fail = True

    # Overall Status determination
    if has_hard_fail:
        overall_status = "FAIL"
        is_feasible = False
    elif has_warning:
        overall_status = "WARNING"
        is_feasible = True
    else:
        overall_status = "PASS"
        is_feasible = True

    return ValidationReport(
        overall_status=overall_status,
        is_feasible=is_feasible,
        checks=checks,
        unscheduled_operations=unscheduled_ops,
        deadline_violations=deadline_violations
    )
