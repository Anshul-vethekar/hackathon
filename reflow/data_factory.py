import os
import copy
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

START_HOUR = 8  # 08:00 AM represents minute 0

def minutes_to_clock(minutes: int) -> str:
    """Converts minutes from start of day (08:00) to HH:MM format."""
    total_minutes = START_HOUR * 60 + int(minutes)
    hours = (total_minutes // 60) % 24
    mins = total_minutes % 60
    return f"{hours:02d}:{mins:02d}"

def clock_to_minutes(clock_str: str) -> int:
    """Converts HH:MM clock format back to minutes relative to 08:00 AM."""
    parts = clock_str.split(":")
    hours = int(parts[0])
    mins = int(parts[1])
    total_minutes = hours * 60 + mins
    return total_minutes - (START_HOUR * 60)

@dataclass
class Machine:
    machine_id: str
    name: str
    supported_operations: List[str]
    shift_start: int = 0
    shift_end: int = 600
    maint_start: int = -1
    maint_end: int = -1

@dataclass
class Material:
    material_id: str
    name: str
    initial_quantity: float
    unit: str

@dataclass
class Shipment:
    shipment_id: str
    material_id: str
    quantity: float
    expected_arrival_time: int
    revised_arrival_time: Optional[int] = None

@dataclass
class WorkOrder:
    work_order_id: str
    customer_name: str
    priority: str  # Critical, High, Medium, Low
    release_time: int
    due_time: int

    @property
    def priority_level(self) -> int:
        priority_map = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
        return priority_map.get(self.priority, 1)

@dataclass
class Operation:
    operation_id: str
    work_order_id: str
    stage_name: str
    processing_duration: int
    compatible_machines: List[str]
    required_material_id: Optional[str] = None
    required_material_qty: float = 0.0
    predecessors: List[str] = field(default_factory=list)

@dataclass
class DisruptionInput:
    machine_id: Optional[str] = "M1"
    breakdown_start: int = 60       # 09:00 AM (60 min)
    breakdown_duration: int = 240   # 4 hours (240 min)
    shipment_id: Optional[str] = "SHP-01"
    shipment_delay_duration: int = 180 # Delayed by 3 hours -> arrival 240 (12:00)

    @property
    def breakdown_end(self) -> int:
        return self.breakdown_start + self.breakdown_duration

@dataclass
class FactoryData:
    machines: Dict[str, Machine]
    materials: Dict[str, Material]
    shipments: Dict[str, Shipment]
    work_orders: Dict[str, WorkOrder]
    operations: Dict[str, Operation]
    data_dir: str = ""

def load_factory_data(data_dir: Optional[str] = None) -> FactoryData:
    if data_dir is None:
        base_path = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_path, "data")

    # Machines
    machines_df = pd.read_csv(os.path.join(data_dir, "machines.csv"))
    machines = {}
    for _, r in machines_df.iterrows():
        ops = [op.strip() for op in str(r["supported_operations"]).split(";") if op.strip()]
        machines[r["machine_id"]] = Machine(
            machine_id=str(r["machine_id"]),
            name=str(r["name"]),
            supported_operations=ops,
            shift_start=int(r["shift_start"]),
            shift_end=int(r["shift_end"]),
            maint_start=int(r["maint_start"]),
            maint_end=int(r["maint_end"])
        )

    # Materials
    materials_df = pd.read_csv(os.path.join(data_dir, "materials.csv"))
    materials = {}
    for _, r in materials_df.iterrows():
        materials[r["material_id"]] = Material(
            material_id=str(r["material_id"]),
            name=str(r["name"]),
            initial_quantity=float(r["initial_quantity"]),
            unit=str(r["unit"])
        )

    # Shipments
    shipments_df = pd.read_csv(os.path.join(data_dir, "shipments.csv"))
    shipments = {}
    for _, r in shipments_df.iterrows():
        shipments[r["shipment_id"]] = Shipment(
            shipment_id=str(r["shipment_id"]),
            material_id=str(r["material_id"]),
            quantity=float(r["quantity"]),
            expected_arrival_time=int(r["expected_arrival_time"])
        )

    # Work Orders
    wo_df = pd.read_csv(os.path.join(data_dir, "work_orders.csv"))
    work_orders = {}
    for _, r in wo_df.iterrows():
        work_orders[r["work_order_id"]] = WorkOrder(
            work_order_id=str(r["work_order_id"]),
            customer_name=str(r["customer_name"]),
            priority=str(r["priority"]),
            release_time=int(r["release_time"]),
            due_time=int(r["due_time"])
        )

    # Operations
    ops_df = pd.read_csv(os.path.join(data_dir, "operations.csv"))
    operations = {}
    for _, r in ops_df.iterrows():
        macs = [m.strip() for m in str(r["compatible_machines"]).split(";") if m.strip()]
        preds = [p.strip() for p in str(r["predecessors"]).split(";") if p.strip() and str(p).lower() != "nan"]
        mat_id = str(r["required_material_id"]) if pd.notna(r["required_material_id"]) and str(r["required_material_id"]).strip() else None
        mat_qty = float(r["required_material_qty"]) if pd.notna(r["required_material_qty"]) else 0.0

        operations[r["operation_id"]] = Operation(
            operation_id=str(r["operation_id"]),
            work_order_id=str(r["work_order_id"]),
            stage_name=str(r["stage_name"]),
            processing_duration=int(r["processing_duration"]),
            compatible_machines=macs,
            required_material_id=mat_id,
            required_material_qty=mat_qty,
            predecessors=preds
        )

    return FactoryData(
        machines=machines,
        materials=materials,
        shipments=shipments,
        work_orders=work_orders,
        operations=operations,
        data_dir=data_dir
    )

def copy_factory_data(factory_data: FactoryData) -> FactoryData:
    """Returns a deep copy of factory data."""
    return copy.deepcopy(factory_data)
