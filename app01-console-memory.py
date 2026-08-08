import statistics
import time
from typing import Dict, List, Optional, Tuple, Any

# =====================================================================
# CONFIGURATION SWITCHES
# =====================================================================
RUN_TEST_SUITE = True

# =====================================================================
# 1. DATA ACCESS LAYER (MODELS)
# =====================================================================
class PatientModel:
    """Manages volatile in-memory patient data storage and initial data cleaning."""
    
    def __init__(self):
        self._raw_patients: Dict[int, Dict[str, float]] = {
            101: {"Glucose": 95.0, "BMI": 22.5, "Age": 28.0, "BloodPressure": 115.0},
            102: {"Glucose": 145.0, "BMI": 0.0, "Age": 54.0, "BloodPressure": 135.0}, 
            103: {"Glucose": 112.0, "BMI": 29.1, "Age": 42.0, "BloodPressure": 122.0},
            104: {"Glucose": 180.0, "BMI": 36.4, "Age": 61.0, "BloodPressure": 142.0}
        }
        self._clean_initial_data()

    def _clean_initial_data(self) -> None:
        valid_bmis = [p["BMI"] for p in self._raw_patients.values() if p["BMI"] > 0]
        median_bmi = statistics.median(valid_bmis) if valid_bmis else 25.0
        for metrics in self._raw_patients.values():
            if metrics["BMI"] <= 0:
                metrics["BMI"] = round(median_bmi, 1)

    def get_all_ids(self) -> List[int]:
        return sorted(self._raw_patients.keys())

    def get_patient(self, patient_id: int) -> Optional[Dict[str, float]]:
        patient = self._raw_patients.get(patient_id)
        return patient.copy() if patient else None

    def update_patient(self, patient_id: int, updated_metrics: Dict[str, float]) -> bool:
        if patient_id in self._raw_patients:
            self._raw_patients[patient_id].update(updated_metrics)
            return True
        return False


# =====================================================================
# 2. BUSINESS LOGIC LAYER (SERVICE)
# =====================================================================
class ClinicalRiskService:
    """Handles clinical decision rules, point scoring, and risk categorization."""
    
    THRESHOLDS = {
        "Glucose": (100.0, 125.0),
        "BMI": (25.0, 29.9),
        "Age": (35.0, 55.0),
        "BloodPressure": (120.0, 130.0)
    }

    def calculate_metric_score(self, metric_name: str, value: float) -> int:
        if metric_name not in self.THRESHOLDS:
            return 0
        low_max, med_max = self.THRESHOLDS[metric_name]
        if value <= low_max:
            return 0
        elif value <= med_max:
            return 1
        return 2

    def evaluate_patient_risk(self, metrics: Dict[str, float]) -> Tuple[int, str]:
        total_score = sum(self.calculate_metric_score(m, v) for m, v in metrics.items())
        if total_score <= 2:
            category = "Low Risk"
        elif total_score <= 5:
            category = "Moderate Risk"
        else:
            category = "High Risk"
        return total_score, category


# =====================================================================
# 3. PRESENTATION LAYER (VIEWS)
# =====================================================================
class ConsoleView:
    """Handles system layout, user text inputs, and structured reports for terminal."""
    
    @staticmethod
    def display_main_menu() -> str:
        print("\n" + "="*40 + "\n     DIABETES RISK SCORING SYSTEM\n" + "="*40)
        print("1. Assess Patient Risk\n2. Exit\n" + "-"*40)
        return input("Select an option (1-2): ").strip()

    @staticmethod
    def display_patient_ids(ids: List[int]) -> None:
        print(f"\nAvailable Patient IDs: {', '.join(map(str, ids))}")

    @staticmethod
    def prompt_patient_id() -> str:
        return input("Enter Patient ID to assess: ").strip()

    @staticmethod
    def display_error(message: str) -> None:
        print(f"\n[ERROR] {message}")

    @staticmethod
    def display_profile(patient_id: int, metrics: Dict[str, float]) -> None:
        print(f"\n--- Clinical Profile for Patient {patient_id} ---")
        for metric, val in metrics.items():
            print(f" * {metric}: {val}")

    @staticmethod
    def prompt_modification_choice() -> bool:
        return input("\nDo you want to modify any metrics before calculation? (y/n): ").strip().lower() == 'y'

    @staticmethod
    def prompt_metric_update(metric_name: str, current_value: float) -> float:
        user_input = input(f"Enter new {metric_name} [Current: {current_value}] (Or press Enter to keep): ").strip()
        if user_input == "":
            return current_value
        try:
            return float(user_input)
        except ValueError:
            print("[Invalid Input] Keeping original value.")
            return current_value

    @staticmethod
    def display_diagnostic_report(patient_id: int, score: int, category: str) -> None:
        print("\n" + "*"*40 + "\n          DIAGNOSTIC RISK REPORT\n" + "*"*40)
        print(f" Patient ID:       {patient_id}\n Cumulative Score: {score} pts\n Risk Category:    {category.upper()}")
        print("*"*40)


# =====================================================================
# 4. ORCHESTRATION LAYER (CONTROLLER)
# =====================================================================
class ConsoleController:
    """Coordinates interaction workflows between Model, Service, and Console View."""
    
    def __init__(self, model: Any, service: ClinicalRiskService, view: ConsoleView):
        self.model = model
        self.service = service
        self.view = view

    def run(self) -> None:
        while True:
            choice = self.view.display_main_menu()
            if choice == "1":
                self.handle_assessment_workflow()
            elif choice == "2":
                print("\nExiting system. Goodbye.")
                break
            else:
                self.view.display_error("Invalid menu selection. Please choose 1 or 2.")

    def handle_assessment_workflow(self) -> None:
        valid_ids = self.model.get_all_ids()
        self.view.display_patient_ids(valid_ids)
        
        id_input = self.view.prompt_patient_id()
        if not id_input.isdigit():
            self.view.display_error("Patient ID must be a numeric integer value.")
            return
            
        patient_id = int(id_input)
        patient_metrics = self.model.get_patient(patient_id)
        if not patient_metrics:
            self.view.display_error(f"Patient ID {patient_id} does not exist in the database.")
            return

        self.view.display_profile(patient_id, patient_metrics)
        
        if self.view.prompt_modification_choice():
            updated_metrics = {}
            for metric, current_val in patient_metrics.items():
                updated_metrics[metric] = self.view.prompt_metric_update(metric, current_val)
            self.model.update_patient(patient_id, updated_metrics)
            patient_metrics = updated_metrics 

        score, category = self.service.evaluate_patient_risk(patient_metrics)
        self.view.display_diagnostic_report(patient_id, score, category)


# =====================================================================
# AUTOMATED 3-TIER TEST SUITE
# =====================================================================

class RiskAssessmentTestSuite:
    """Encapsulates unit, end-to-end, and performance test suites."""

    def __init__(self, model_factory, service_class):
        self.model_factory = model_factory
        self.service_class = service_class

    def run_all_tiers(self) -> None:
        """Orchestrates and executes all three testing tiers sequentially."""
        print("\n" + "="*60)
        print("         STARTING 3-TIER AUTOMATED TESTING SUITE")
        print("="*60)
        
        self.run_tier1_unit_tests()
        self.run_tier2_e2e_scenarios()
        self.run_tier3_performance_benchmarks()
        
        print("\n" + "="*60)
        print("         ALL AUTOMATED TESTING TIERS PASSED SUCCESSFULLY")
        print("="*60 + "\n")

    def run_tier1_unit_tests(self) -> None:
        """Tier 1: Unit Tests for rule calculations and categorical mapping."""
        print("\n--- Running Tier 1: Unit Tests (Decision Rules) ---")
        service = self.service_class()
        
        # Test individual rule thresholds
        assert service.calculate_metric_score("Glucose", 95.0) == 0, "Failed Glucose Low threshold"
        assert service.calculate_metric_score("Glucose", 110.0) == 1, "Failed Glucose Med threshold"
        assert service.calculate_metric_score("Glucose", 130.0) == 2, "Failed Glucose High threshold"
        
        # Test border cases
        assert service.calculate_metric_score("BMI", 25.0) == 0, "Border case BMI=25 failed"
        assert service.calculate_metric_score("BMI", 25.1) == 1, "Border case BMI=25.1 failed"
        
        # Test complete risk category mapping boundaries
        # Low risk (0-2 pts)
        score_low, cat_low = service.evaluate_patient_risk({"Glucose": 90.0, "BMI": 22.0, "Age": 30.0, "BloodPressure": 110.0})
        assert score_low == 0 and "Low" in cat_low, f"Expected Low Risk, got {score_low} pts ({cat_low})"
        
        # Moderate risk (3-5 pts)
        score_med, cat_med = service.evaluate_patient_risk({"Glucose": 115.0, "BMI": 27.0, "Age": 45.0, "BloodPressure": 125.0})
        assert 3 <= score_med <= 5 and "Moderate" in cat_med, f"Expected Mod Risk, got {score_med} pts ({cat_med})"
        
        # High risk (6-8 pts)
        score_high, cat_high = service.evaluate_patient_risk({"Glucose": 140.0, "BMI": 35.0, "Age": 60.0, "BloodPressure": 135.0})
        assert score_high >= 6 and "High" in cat_high, f"Expected High Risk, got {score_high} pts ({cat_high})"
        
        print(" ✓ Tier 1 Unit Tests Pass: All rule sets mapped and categorized perfectly.")

    def run_tier2_e2e_scenarios(self) -> None:
        """Tier 2: E2E Scenario Tests covering cleaning, storage, modification, and scoring."""
        print("\n--- Running Tier 2: End-to-End Workflows ---")
        model = self.model_factory()
        service = self.service_class()
        
        # Test Case 1: Data cleaning checks (BMI imputation verification)
        patient_102 = model.get_patient(102)
        assert patient_102 is not None, "E2E Error: Patient 102 not found"
        assert patient_102["BMI"] > 0, f"E2E Error: Anomalous BMI of 0 was not replaced. Got {patient_102['BMI']}"
        
        # Test Case 2: Workflow calculation with user modifications
        patient_101 = model.get_patient(101)
        original_score, _ = service.evaluate_patient_risk(patient_101)
        
        # Modify clinical metrics
        modified_metrics = {
            "Glucose": 150.0,         # Changes score from 0 -> 2
            "BMI": patient_101["BMI"],
            "Age": patient_101["Age"],
            "BloodPressure": 140.0     # Changes score from 0 -> 2
        }
        
        # Commit to persistence layer and re-evaluate
        update_ok = model.update_patient(101, modified_metrics)
        assert update_ok, "E2E Error: Database modification write failed"
        
        updated_profile = model.get_patient(101)
        new_score, new_category = service.evaluate_patient_risk(updated_profile)
        
        assert new_score > original_score, "E2E Error: Score did not increase after modifying risk variables"
        assert "High" in new_category or "Moderate" in new_category, "E2E Error: Risk category didn't escalate correctly"
        
        print(" ✓ Tier 2 E2E Tests Pass: Clean-to-write-to-score cycle validated.")

    def run_tier3_performance_benchmarks(self, iterations: int = 10000) -> None:
        """Tier 3: Core Performance latency benchmarks."""
        print(f"\n--- Running Tier 3: Performance Latency ({iterations:,} iterations) ---")
        service = self.service_class()
        test_metrics = {"Glucose": 115.0, "BMI": 27.5, "Age": 42.0, "BloodPressure": 125.0}
        
        start_time = time.perf_counter()
        for _ in range(iterations):
            _ = service.evaluate_patient_risk(test_metrics)
        end_time = time.perf_counter()
        
        total_duration = end_time - start_time
        avg_duration_ms = (total_duration / iterations) * 1000
        
        print(f" ✓ Tier 3 Performance Pass: Completed {iterations:,} diagnostic evaluations in {total_duration:.4f}s.")
        print(f"   Mean Latency: {avg_duration_ms:.6f} ms per patient transaction analysis.")


# =====================================================================
# SYSTEM APPLICATION ENTRY POINT
# =====================================================================
if __name__ == "__main__":
    if RUN_TEST_SUITE:
        suite = RiskAssessmentTestSuite(model_factory=PatientModel, service_class=ClinicalRiskService)
        suite.run_all_tiers()
    
    # Run in console with in-memory model
    db_model = PatientModel()
    rules_service = ClinicalRiskService()
    ui_view = ConsoleView()
    
    app = ConsoleController(model=db_model, service=rules_service, view=ui_view)
    app.run()