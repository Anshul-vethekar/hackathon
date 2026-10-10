import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from data_factory import (
    FactoryData, DisruptionInput, WorkOrder, Operation, Machine,
    copy_factory_data, minutes_to_clock
)
from disruption import apply_disruptions, get_effective_material_arrival

@dataclass
class MachineEvaluation:
    machine_id: str
    is_compatible: bool
    earliest_start: Optional[int] = None
    earliest_finish: Optional[int] = None
    status: str = "" # "FEASIBLE", "OVERLAPS_BREAKDOWN", "OVERLAPS_MAINTENANCE", "EXCEEDS_SHIFT", "INCOMPATIBLE"
    reason: str = ""

@dataclass
class DecisionTraceEntry:
    step_id: int
    operation_id: str
    work_order_id: str
    priority: str
    due_time: int
    earliest_ready_time: int
    candidate_machines: List[str]
    evaluations: List[MachineEvaluation]
    selected_machine: Optional[str]
    scheduled_start: Optional[int]
    scheduled_finish: Optional[int]
    decision_narrative: str
    rejected_reasons: List[str]

@dataclass
class ScheduleResult:
    strategy_name: str
    schedule: Dict[str, Dict]         # op_id -> {op_id, wo_id, stage_name, assigned_machine, start_time, finish_time, status}
    unscheduled_ops: Dict[str, Dict]   # op_id -> {op_id, wo_id, stage_name, reason}
    decision_trace: List[DecisionTraceEntry]
    disruption_applied: Optional[DisruptionInput] = None

def find_earliest_slot(
    machine: Machine,
    op_duration: int,
    earliest_ready: int,
    existing_intervals: List[Tuple[int, int, str]],
    breakdown_window: Optional[Tuple[int, int]] = None
) -> Tuple[Optional[int], Optional[int], str, str]:
    """
    Finds the earliest start and finish time for an operation on a machine.
    Returns (start_time, finish_time, status, reason).
    """
    current_t = max(earliest_ready, machine.shift_start)
    
    blocked: List[Tuple[int, int, str]] = []
    
    if machine.maint_start >= 0 and machine.maint_end > machine.maint_start:
        blocked.append((machine.maint_start, machine.maint_end, "Maintenance"))

    if breakdown_window and breakdown_window[1] > breakdown_window[0]:
        blocked.append((breakdown_window[0], breakdown_window[1], "Breakdown"))

    for start_t, finish_t, label in existing_intervals:
        blocked.append((start_t, finish_t, f"Scheduled Op {label}"))

    blocked.sort(key=lambda x: x[0])

    while current_t + op_duration <= machine.shift_end:
        conflict = False
        
        op_start = current_t
        op_finish = current_t + op_duration

        for b_start, b_finish, b_reason in blocked:
            if op_start < b_finish and op_finish > b_start:
                conflict = True
                current_t = b_finish
                break

        if not conflict:
            return (op_start, op_finish, "FEASIBLE", f"Available at {minutes_to_clock(op_start)}")

    return (None, None, "EXCEEDS_SHIFT", f"Cannot fit {op_duration}m duration before shift end ({minutes_to_clock(machine.shift_end)})")

def calculate_remaining_duration(factory_data: FactoryData, op_id: str, completed_ops: Set[str]) -> int:
    op = factory_data.operations[op_id]
    total = op.processing_duration
    for other_op in factory_data.operations.values():
        if other_op.work_order_id == op.work_order_id and other_op.operation_id not in completed_ops:
            if op_id in other_op.predecessors:
                total += other_op.processing_duration
    return total

def run_scheduler_engine(
    factory_data: FactoryData,
    strategy_name: str,
    disruption_input: Optional[DisruptionInput] = None
) -> ScheduleResult:
    fdata = copy_factory_data(factory_data)
    if disruption_input:
        fdata = apply_disruptions(fdata, disruption_input)

    bd_machine = disruption_input.machine_id if disruption_input else None
    bd_window = (disruption_input.breakdown_start, disruption_input.breakdown_end) if (disruption_input and bd_machine) else None

    machine_intervals: Dict[str, List[Tuple[int, int, str]]] = {m_id: [] for m_id in fdata.machines}
    completed_ops: Dict[str, int] = {}
    schedule: Dict[str, Dict] = {}
    unscheduled: Dict[str, Dict] = {}
    decision_trace: List[DecisionTraceEntry] = []

    remaining_ops = set(fdata.operations.keys())
    step_counter = 1

    while remaining_ops:
        ready_ops: List[str] = []
        for op_id in remaining_ops:
            op = fdata.operations[op_id]
            all_preds_done = all(p in completed_ops for p in op.predecessors)
            if all_preds_done:
                ready_ops.append(op_id)

        if not ready_ops:
            for op_id in remaining_ops:
                op = fdata.operations[op_id]
                unscheduled[op_id] = {
                    "operation_id": op_id,
                    "work_order_id": op.work_order_id,
                    "stage_name": op.stage_name,
                    "reason": "Unresolved predecessor dependencies"
                }
            break

        def get_op_sort_key(op_id: str):
            op = fdata.operations[op_id]
            wo = fdata.work_orders[op.work_order_id]
            
            pred_finish = max([completed_ops[p] for p in op.predecessors], default=0)
            mat_arrival = get_effective_material_arrival(fdata, op.required_material_id)
            earliest_ready = max(wo.release_time, pred_finish, mat_arrival)

            if strategy_name in ["BASELINE", "PLAN_A"]:
                return (
                    -wo.priority_level,
                    wo.due_time,
                    earliest_ready,
                    wo.work_order_id,
                    op.operation_id
                )
            else:
                rem_dur = calculate_remaining_duration(fdata, op_id, set(completed_ops.keys()))
                slack = wo.due_time - (earliest_ready + rem_dur)
                return (
                    slack,
                    wo.due_time,
                    -wo.priority_level,
                    wo.work_order_id,
                    op.operation_id
                )

        ready_ops.sort(key=get_op_sort_key)
        
        next_op_id = ready_ops[0]
        op = fdata.operations[next_op_id]
        wo = fdata.work_orders[op.work_order_id]

        pred_finish = max([completed_ops[p] for p in op.predecessors], default=0)
        mat_arrival = get_effective_material_arrival(fdata, op.required_material_id)
        earliest_ready = max(wo.release_time, pred_finish, mat_arrival)

        evaluations: List[MachineEvaluation] = []
        feasible_options: List[Tuple[int, int, str, str]] = []
        rejected_reasons: List[str] = []

        for m_id in fdata.machines:
            m = fdata.machines[m_id]
            
            is_compat = m_id in op.compatible_machines or op.stage_name in m.supported_operations
            if not is_compat:
                evals = MachineEvaluation(
                    machine_id=m_id,
                    is_compatible=False,
                    status="INCOMPATIBLE",
                    reason=f"Machine {m_id} does not support stage '{op.stage_name}'"
                )
                evaluations.append(evals)
                rejected_reasons.append(f"{m_id}: Incompatible operation type")
                continue

            m_bd_window = bd_window if (bd_machine == m_id) else None
            start_t, finish_t, status, reason = find_earliest_slot(
                machine=m,
                op_duration=op.processing_duration,
                earliest_ready=earliest_ready,
                existing_intervals=machine_intervals[m_id],
                breakdown_window=m_bd_window
            )

            evals = MachineEvaluation(
                machine_id=m_id,
                is_compatible=True,
                earliest_start=start_t,
                earliest_finish=finish_t,
                status=status,
                reason=reason
            )
            evaluations.append(evals)

            if status == "FEASIBLE" and start_t is not None and finish_t is not None:
                feasible_options.append((start_t, finish_t, m_id, status))
            else:
                rejected_reasons.append(f"{m_id}: {reason}")

        selected_machine = None
        scheduled_start = None
        scheduled_finish = None
        narrative = ""

        if feasible_options:
            if strategy_name == "PLAN_A" and wo.priority == "Critical":
                feasible_options.sort(key=lambda x: (x[1], x[0], x[2]))
            else:
                primary_m = op.compatible_machines[0] if op.compatible_machines else ""
                feasible_options.sort(key=lambda x: (x[0], x[1], 0 if x[2] == primary_m else 1, x[2]))

            best_start, best_finish, best_m, _ = feasible_options[0]
            selected_machine = best_m
            scheduled_start = best_start
            scheduled_finish = best_finish

            machine_intervals[best_m].append((best_start, best_finish, op.operation_id))
            machine_intervals[best_m].sort(key=lambda x: x[0])
            completed_ops[next_op_id] = best_finish

            schedule[next_op_id] = {
                "operation_id": next_op_id,
                "work_order_id": op.work_order_id,
                "stage_name": op.stage_name,
                "assigned_machine": best_m,
                "start_time": best_start,
                "finish_time": best_finish,
                "status": "SCHEDULED"
            }

            narrative = (
                f"Assigned {next_op_id} ({op.stage_name}) to Machine {best_m} from "
                f"{minutes_to_clock(best_start)} to {minutes_to_clock(best_finish)}. "
                f"Material readiness: {minutes_to_clock(mat_arrival)}, Predecessors finished: {minutes_to_clock(pred_finish)}."
            )
        else:
            unscheduled[next_op_id] = {
                "operation_id": next_op_id,
                "work_order_id": op.work_order_id,
                "stage_name": op.stage_name,
                "reason": f"No feasible machine slot available within operating shift (08:00-18:00). {'; '.join(rejected_reasons)}"
            }
            narrative = f"FAILED to schedule {next_op_id}: No compatible machine could fit processing duration ({op.processing_duration}m) within shift bounds."

        decision_trace.append(DecisionTraceEntry(
            step_id=step_counter,
            operation_id=next_op_id,
            work_order_id=op.work_order_id,
            priority=wo.priority,
            due_time=wo.due_time,
            earliest_ready_time=earliest_ready,
            candidate_machines=op.compatible_machines,
            evaluations=evaluations,
            selected_machine=selected_machine,
            scheduled_start=scheduled_start,
            scheduled_finish=scheduled_finish,
            decision_narrative=narrative,
            rejected_reasons=rejected_reasons
        ))

        step_counter += 1
        remaining_ops.remove(next_op_id)

    return ScheduleResult(
        strategy_name=strategy_name,
        schedule=schedule,
        unscheduled_ops=unscheduled,
        decision_trace=decision_trace,
        disruption_applied=disruption_input
    )

def schedule_baseline(factory_data: FactoryData) -> ScheduleResult:
    return run_scheduler_engine(factory_data, strategy_name="BASELINE")

def schedule_recovery(
    factory_data: FactoryData,
    disruption_input: DisruptionInput,
    strategy: str = "PLAN_A"
) -> ScheduleResult:
    return run_scheduler_engine(factory_data, strategy_name=strategy, disruption_input=disruption_input)
