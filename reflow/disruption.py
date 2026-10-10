from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from data_factory import FactoryData, DisruptionInput, copy_factory_data, minutes_to_clock

@dataclass
class OperationImpact:
    operation_id: str
    work_order_id: str
    stage_name: str
    assigned_machine: str
    baseline_start: int
    baseline_finish: int
    cause: str  # "Machine Breakdown", "Material Delay", "Downstream Precedence", "Multiple", "Unaffected"
    is_directly_affected: bool
    is_downstream_affected: bool
    detail: str
    deadline_risk: bool

@dataclass
class ImpactAnalysisResult:
    disruption_input: DisruptionInput
    operation_impacts: Dict[str, OperationImpact]
    directly_affected_op_ids: List[str]
    downstream_affected_op_ids: List[str]
    unaffected_op_ids: List[str]
    affected_work_order_ids: List[str]
    work_orders_at_deadline_risk: List[str]
    summary_narrative: str

def apply_disruptions(factory_data: FactoryData, disruption_input: DisruptionInput) -> FactoryData:
    """Returns a deep copy of factory data with disruption inputs applied."""
    disrupted_data = copy_factory_data(factory_data)
    
    if disruption_input.shipment_id and disruption_input.shipment_id in disrupted_data.shipments:
        shp = disrupted_data.shipments[disruption_input.shipment_id]
        shp.revised_arrival_time = shp.expected_arrival_time + disruption_input.shipment_delay_duration

    return disrupted_data

def get_effective_material_arrival(factory_data: FactoryData, material_id: str) -> int:
    """Returns the effective arrival time of a material based on shipments."""
    if not material_id:
        return 0
    mat = factory_data.materials.get(material_id)
    if not mat:
        return 0
    if mat.initial_quantity > 0:
        return 0
    
    # Check shipments for this material
    arrival = 0
    for shp in factory_data.shipments.values():
        if shp.material_id == material_id:
            arr = shp.revised_arrival_time if shp.revised_arrival_time is not None else shp.expected_arrival_time
            arrival = max(arrival, arr)
    return arrival

def analyze_impact(
    baseline_schedule: Dict[str, Dict],
    factory_data: FactoryData,
    disruption_input: DisruptionInput
) -> ImpactAnalysisResult:
    """
    Analyzes baseline schedule against disruption parameters.
    Identifies direct conflicts (breakdown overlap, material delay)
    and propagates downstream delays.
    """
    disrupted_data = apply_disruptions(factory_data, disruption_input)
    
    bd_machine = disruption_input.machine_id
    bd_start = disruption_input.breakdown_start
    bd_end = disruption_input.breakdown_end

    directly_affected: Set[str] = set()
    downstream_affected: Set[str] = set()
    unaffected: Set[str] = set()
    
    op_causes: Dict[str, List[str]] = {}

    # Step 1: Direct machine breakdown conflicts & material arrival conflicts
    for op_id, sched in baseline_schedule.items():
        op = disrupted_data.operations[op_id]
        causes = []
        
        # Check machine breakdown overlap
        if bd_machine and sched["assigned_machine"] == bd_machine:
            # Overlap check: start < bd_end and finish > bd_start
            if sched["start_time"] < bd_end and sched["finish_time"] > bd_start:
                causes.append(f"Machine {bd_machine} breakdown ({minutes_to_clock(bd_start)}-{minutes_to_clock(bd_end)})")

        # Check material delay conflict
        if op.required_material_id:
            mat_arrival = get_effective_material_arrival(disrupted_data, op.required_material_id)
            if sched["start_time"] < mat_arrival:
                causes.append(f"Material {op.required_material_id} delayed to {minutes_to_clock(mat_arrival)}")

        if causes:
            directly_affected.add(op_id)
            op_causes[op_id] = causes

    # Step 2: Propagate downstream precedence impacts
    # Loop until no new downstream affected operations are found
    changed = True
    while changed:
        changed = False
        for op_id, op in disrupted_data.operations.items():
            if op_id in directly_affected or op_id in downstream_affected:
                continue
            
            # Check if any predecessor is directly or downstream affected
            for pred_id in op.predecessors:
                if pred_id in directly_affected or pred_id in downstream_affected:
                    downstream_affected.add(op_id)
                    op_causes[op_id] = [f"Predecessor {pred_id} impacted by disruption"]
                    changed = True
                    break

    # Unaffected operations
    for op_id in baseline_schedule:
        if op_id not in directly_affected and op_id not in downstream_affected:
            unaffected.add(op_id)
            op_causes[op_id] = []

    # Build operation impact structures
    operation_impacts = {}
    affected_wos: Set[str] = set()
    deadline_risk_wos: Set[str] = set()

    for op_id, sched in baseline_schedule.items():
        op = disrupted_data.operations[op_id]
        wo = disrupted_data.work_orders[op.work_order_id]
        
        is_direct = op_id in directly_affected
        is_downstream = op_id in downstream_affected
        
        if is_direct or is_downstream:
            affected_wos.add(op.work_order_id)
        
        causes = op_causes.get(op_id, [])
        cause_str = "Unaffected"
        if is_direct and is_downstream:
            cause_str = "Multiple (Direct & Predecessor)"
        elif is_direct:
            cause_str = "Direct Conflict"
        elif is_downstream:
            cause_str = "Downstream Precedence"

        detail_str = "; ".join(causes) if causes else "Scheduled as planned."

        # Estimate deadline risk based on baseline finish vs due time
        risk = False
        if is_direct or is_downstream:
            # If op baseline finish was close to due time or delayed, flag risk
            if sched["finish_time"] >= wo.due_time - 30:
                risk = True
                deadline_risk_wos.add(wo.work_order_id)

        operation_impacts[op_id] = OperationImpact(
            operation_id=op_id,
            work_order_id=op.work_order_id,
            stage_name=op.stage_name,
            assigned_machine=sched["assigned_machine"],
            baseline_start=sched["start_time"],
            baseline_finish=sched["finish_time"],
            cause=cause_str,
            is_directly_affected=is_direct,
            is_downstream_affected=is_downstream,
            detail=detail_str,
            deadline_risk=risk
        )

    narrative = (
        f"Disruption analysis complete: {len(directly_affected)} operations directly disrupted "
        f"({', '.join(sorted(directly_affected)) or 'None'}), causing downstream delays for "
        f"{len(downstream_affected)} operations ({', '.join(sorted(downstream_affected)) or 'None'}). "
        f"A total of {len(affected_wos)} work orders are impacted."
    )

    return ImpactAnalysisResult(
        disruption_input=disruption_input,
        operation_impacts=operation_impacts,
        directly_affected_op_ids=sorted(list(directly_affected)),
        downstream_affected_op_ids=sorted(list(downstream_affected)),
        unaffected_op_ids=sorted(list(unaffected)),
        affected_work_order_ids=sorted(list(affected_wos)),
        work_orders_at_deadline_risk=sorted(list(deadline_risk_wos)),
        summary_narrative=narrative
    )
