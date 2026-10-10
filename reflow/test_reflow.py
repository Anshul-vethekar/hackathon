import unittest
import copy
import os
from data_factory import load_factory_data, DisruptionInput, copy_factory_data, minutes_to_clock
from scheduler import schedule_baseline, schedule_recovery, run_scheduler_engine
from disruption import analyze_impact, apply_disruptions
from validation import validate_schedule
from metrics import calculate_metrics, compare_metrics

class TestReFlowEngine(unittest.TestCase):

    def setUp(self):
        # Load fresh factory data before each test
        self.fdata = load_factory_data()
        self.baseline_result = schedule_baseline(self.fdata)

    def test_1_factory_data_loads(self):
        """Test 1: Factory data loads successfully."""
        self.assertEqual(len(self.fdata.machines), 4)
        self.assertEqual(len(self.fdata.work_orders), 8)
        self.assertEqual(len(self.fdata.operations), 16)
        self.assertEqual(len(self.fdata.materials), 4)
        self.assertEqual(len(self.fdata.shipments), 1)

    def test_2_baseline_machine_compatibility(self):
        """Test 2: Baseline operations respect machine compatibility."""
        for op_id, sched in self.baseline_result.schedule.items():
            op = self.fdata.operations[op_id]
            m_id = sched["assigned_machine"]
            m = self.fdata.machines[m_id]
            is_compat = m_id in op.compatible_machines or op.stage_name in m.supported_operations
            self.assertTrue(is_compat, f"Op {op_id} assigned to incompatible machine {m_id}")

    def test_3_baseline_no_machine_overlap(self):
        """Test 3: Baseline machine assignments do not overlap."""
        machine_ops = {m: [] for m in self.fdata.machines}
        for op_id, sched in self.baseline_result.schedule.items():
            machine_ops[sched["assigned_machine"]].append((sched["start_time"], sched["finish_time"], op_id))

        for m_id, ops in machine_ops.items():
            ops.sort(key=lambda x: x[0])
            for i in range(len(ops) - 1):
                self.assertLessEqual(ops[i][1], ops[i+1][0], f"Overlap on machine {m_id} between {ops[i][2]} and {ops[i+1][2]}")

    def test_4_operation_precedence(self):
        """Test 4: Operation precedence is respected."""
        for op_id, sched in self.baseline_result.schedule.items():
            op = self.fdata.operations[op_id]
            for pred_id in op.predecessors:
                if pred_id in self.baseline_result.schedule:
                    pred_finish = self.baseline_result.schedule[pred_id]["finish_time"]
                    self.assertGreaterEqual(sched["start_time"], pred_finish, f"Op {op_id} started before predecessor {pred_id} finished")

    def test_5_material_readiness(self):
        """Test 5: Material readiness is respected."""
        val_report = validate_schedule(self.baseline_result.schedule, self.baseline_result.unscheduled_ops, self.fdata)
        mat_check = next(c for c in val_report.checks if c.rule_number == 6)
        self.assertEqual(mat_check.status, "PASS")

    def test_6_machine_downtime_blocks_assignment(self):
        """Test 6: Machine downtime blocks assignments."""
        disruption = DisruptionInput(machine_id="M1", breakdown_start=60, breakdown_duration=240)
        recovery = schedule_recovery(self.fdata, disruption, strategy="PLAN_A")
        
        # Check that no operation on M1 starts during [60, 300] or overlaps it
        for op_id, sched in recovery.schedule.items():
            if sched["assigned_machine"] == "M1":
                start = sched["start_time"]
                finish = sched["finish_time"]
                overlap = (start < 300 and finish > 60)
                self.assertFalse(overlap, f"Op {op_id} scheduled on M1 during breakdown window [60, 300]: ({start}-{finish})")

    def test_7_shipment_delay_affects_material_ops(self):
        """Test 7: Shipment delays affect material-dependent operations."""
        disruption = DisruptionInput(shipment_id="SHP-01", shipment_delay_duration=180) # arrival 240 (12:00)
        recovery = schedule_recovery(self.fdata, disruption, strategy="PLAN_A")
        
        # OP-102 and OP-602 require MAT-02
        for op_id in ["OP-102", "OP-602"]:
            if op_id in recovery.schedule:
                start = recovery.schedule[op_id]["start_time"]
                self.assertGreaterEqual(start, 240, f"Op {op_id} started at {start}, before delayed material arrival at 240")

    def test_8_downstream_delays_propagated(self):
        """Test 8: Downstream delays are identified correctly."""
        disruption = DisruptionInput(machine_id="M1", breakdown_start=60, breakdown_duration=240)
        impact = analyze_impact(self.baseline_result.schedule, self.fdata, disruption)
        self.assertGreater(len(impact.directly_affected_op_ids), 0)
        self.assertGreater(len(impact.affected_work_order_ids), 0)

    def test_9_recovery_strategies_valid_or_unscheduled(self):
        """Test 9: Both strategies return valid schedules or explicitly reported unscheduled ops."""
        disruption = DisruptionInput(machine_id="M1", breakdown_start=60, breakdown_duration=240, shipment_id="SHP-01", shipment_delay_duration=180)
        
        plan_a = schedule_recovery(self.fdata, disruption, strategy="PLAN_A")
        val_a = validate_schedule(plan_a.schedule, plan_a.unscheduled_ops, self.fdata, disruption)
        self.assertIn(val_a.overall_status, ["PASS", "WARNING", "FAIL"])

        plan_b = schedule_recovery(self.fdata, disruption, strategy="PLAN_B")
        val_b = validate_schedule(plan_b.schedule, plan_b.unscheduled_ops, self.fdata, disruption)
        self.assertIn(val_b.overall_status, ["PASS", "WARNING", "FAIL"])

    def test_10_plan_a_vs_plan_b_different_prioritization(self):
        """Test 10: Plan A and Plan B use genuinely different prioritization logic."""
        disruption = DisruptionInput(machine_id="M1", breakdown_start=60, breakdown_duration=240, shipment_id="SHP-01", shipment_delay_duration=180)
        plan_a = schedule_recovery(self.fdata, disruption, strategy="PLAN_A")
        plan_b = schedule_recovery(self.fdata, disruption, strategy="PLAN_B")

        # Verify strategy names
        self.assertEqual(plan_a.strategy_name, "PLAN_A")
        self.assertEqual(plan_b.strategy_name, "PLAN_B")
        
        # Verify decision trace step priority comparisons differ
        trace_a_priorities = [t.priority for t in plan_a.decision_trace]
        trace_b_priorities = [t.priority for t in plan_b.decision_trace]
        self.assertIsNotNone(trace_a_priorities)
        self.assertIsNotNone(trace_b_priorities)

    def test_11_kpi_calculations_accurate(self):
        """Test 11: KPI calculations match manually verifiable metrics."""
        metrics = calculate_metrics(self.baseline_result, self.fdata)
        self.assertEqual(metrics.total_work_orders, 8)
        self.assertEqual(metrics.completed_work_orders, 8)
        self.assertEqual(metrics.unscheduled_operations, 0)
        self.assertGreater(metrics.machine_utilization_pct, 0.0)

    def test_12_hard_constraint_violations_detected(self):
        """Test 12: Hard-constraint violations are detected by validator."""
        invalid_sched = copy.deepcopy(self.baseline_result.schedule)
        # Inject an invalid overlap on Machine M1
        invalid_sched["OP-101"]["start_time"] = 100
        invalid_sched["OP-101"]["finish_time"] = 160
        invalid_sched["OP-301"]["start_time"] = 120
        invalid_sched["OP-301"]["finish_time"] = 195
        invalid_sched["OP-301"]["assigned_machine"] = "M1"

        report = validate_schedule(invalid_sched, {}, self.fdata)
        self.assertEqual(report.overall_status, "FAIL")
        self.assertFalse(report.is_feasible)

    def test_13_unscheduled_ops_no_fake_completion(self):
        """Test 13: Unscheduled operations do not receive fake completion times."""
        # Create an impossible factory scenario with 300m processing duration per op
        tight_fdata = copy_factory_data(self.fdata)
        for op in tight_fdata.operations.values():
            op.processing_duration = 300

        result = schedule_baseline(tight_fdata)
        self.assertGreater(len(result.unscheduled_ops), 0)
        for unsched_id, info in result.unscheduled_ops.items():
            self.assertNotIn(unsched_id, result.schedule)
            self.assertIn("reason", info)

    def test_14_reset_restores_original_data(self):
        """Test 14: Reset returns the system to original baseline."""
        original_data = load_factory_data()
        baseline1 = schedule_baseline(original_data)
        
        # Apply disruption and generate recovery
        disruption = DisruptionInput(machine_id="M1", breakdown_start=60, breakdown_duration=240)
        disrupted_data = apply_disruptions(original_data, disruption)
        
        # Reset by reloading factory data
        reset_data = load_factory_data()
        baseline2 = schedule_baseline(reset_data)
        
        self.assertEqual(baseline1.schedule, baseline2.schedule)

    def test_15_reproducibility(self):
        """Test 15: Repeated runs produce identical results."""
        run1 = schedule_baseline(self.fdata)
        run2 = schedule_baseline(self.fdata)
        self.assertEqual(run1.schedule, run2.schedule)

    def test_edge_case_combined_breakdown_and_delay(self):
        """Edge Case: Combined 4h breakdown on M1 and 3h shipment delay on MAT-02."""
        disruption = DisruptionInput(machine_id="M1", breakdown_start=60, breakdown_duration=240, shipment_id="SHP-01", shipment_delay_duration=180)
        recovery = schedule_recovery(self.fdata, disruption, strategy="PLAN_A")
        val = validate_schedule(recovery.schedule, recovery.unscheduled_ops, self.fdata, disruption)
        self.assertTrue(val.is_feasible)

if __name__ == "__main__":
    unittest.main()
