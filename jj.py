import sqlite3
import statistics
import time
from typing import Dict, List, Optional, Tuple, Any
import streamlit as st
import pandas as pd

# =====================================================================
# CONFIGURATION SWITCHES
# =====================================================================
RUN_TEST_SUITE = False

# Set page layout to wide and add custom title/icon
st.set_page_config(
    page_title="Diabetes Risk Scoring System",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling for polished UI elements
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #0d6efd;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }
    .status-normal { border-left-color: #198754; }
    .status-warning { border-left-color: #ffc107; }
    .status-danger { border-left-color: #dc3545; }
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        height: 3em;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# 1. DATA ACCESS LAYER (MODELS - SQLITE3 DATABASE)
# =====================================================================
class PatientModel:
    """Manages persistent SQLite database patient data storage and initial data cleaning."""
    
    def __init__(self, db_path: str = "patients.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    Glucose REAL,
                    BMI REAL,
                    Age REAL,
                    BloodPressure REAL
                )
            """)
            
            cursor.execute("SELECT COUNT(*) FROM patients")
            if cursor.fetchone()[0] == 0:
                seed_data = [
                    (101, 95.0, 22.5, 28.0, 115.0),
                    (102, 145.0, 0.0, 54.0, 135.0),
                    (103, 112.0, 29.1, 42.0, 122.0),
                    (104, 180.0, 36.4, 61.0, 142.0)
                ]
                cursor.executemany("""
                    INSERT INTO patients (patient_id, Glucose, BMI, Age, BloodPressure)
                    VALUES (?, ?, ?, ?, ?)
                """, seed_data)
                conn.commit()
                
        self._clean_initial_data()

    def _clean_initial_data(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT BMI FROM patients WHERE BMI > 0")
            valid_bmis = [row["BMI"] for row in cursor.fetchall()]
            
            median_bmi = statistics.median(valid_bmis) if valid_bmis else 25.0
            
            cursor.execute("""
                UPDATE patients 
                SET BMI = ? 
                WHERE BMI <= 0
            """, (round(median_bmi, 1),))
            conn.commit()

    def get_all_ids(self) -> List[int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT patient_id FROM patients ORDER BY patient_id ASC")
            return [row["patient_id"] for row in cursor.fetchall()]

    def get_patient(self, patient_id: int) -> Optional[Dict[str, float]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT Glucose, BMI, Age, BloodPressure 
                FROM patients 
                WHERE patient_id = ?
            """, (patient_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_all_patients_df(self) -> pd.DataFrame:
        with self._get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM patients ORDER BY patient_id ASC", conn)

    def add_patient(self, metrics: Dict[str, float]) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO patients (Glucose, BMI, Age, BloodPressure)
                VALUES (?, ?, ?, ?)
            """, (metrics["Glucose"], metrics["BMI"], metrics["Age"], metrics["BloodPressure"]))
            conn.commit()
            return cursor.lastrowid

    def update_patient(self, patient_id: int, updated_metrics: Dict[str, float]) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE patients 
                SET Glucose = ?, BMI = ?, Age = ?, BloodPressure = ?
                WHERE patient_id = ?
            """, (
                updated_metrics.get("Glucose"),
                updated_metrics.get("BMI"),
                updated_metrics.get("Age"),
                updated_metrics.get("BloodPressure"),
                patient_id
            ))
            conn.commit()
            return cursor.rowcount > 0


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

    def get_metric_status_label(self, metric_name: str, value: float) -> Tuple[str, str]:
        score = self.calculate_metric_score(metric_name, value)
        if score == 0:
            return "Normal", "status-normal"
        elif score == 1:
            return "Elevated", "status-warning"
        return "High", "status-danger"


# =====================================================================
# 3. PRESENTATION LAYER (ENHANCED STREAMLIT GUI)
# =====================================================================
class StreamlitView:
    """Handles layout, interactive input widgets, and visual outputs."""
    
    @staticmethod
    def render_app(model: PatientModel, service: ClinicalRiskService) -> None:
        st.title("🩺 Clinical Diabetes Risk Scoring System")
        st.caption("Real-time clinical triage dashboard powered by SQLite3")

        tab_assess, tab_add, tab_records = st.tabs([
            "📋 Patient Assessment", 
            "➕ Add New Patient", 
            "🗂️ Patient Records"
        ])

        # TAB 1: ASSESSMENT & EDITING
        with tab_assess:
            valid_ids = model.get_all_ids()
            if not valid_ids:
                st.info("No patients available in the database.")
                return

            col_select, col_empty = st.columns([1, 2])
            with col_select:
                selected_id = st.selectbox("🎯 Select Patient ID", options=valid_ids)

            if selected_id:
                patient_metrics = model.get_patient(selected_id)
                if patient_metrics:
                    st.divider()
                    col_inputs, col_analysis = st.columns([1, 1], gap="large")

                    with col_inputs:
                        st.subheader(f"Update Patient #{selected_id}")
                        updated_metrics = {}
                        
                        updated_metrics["Glucose"] = st.number_input(
                            "Glucose (mg/dL)", value=float(patient_metrics["Glucose"]), step=1.0, format="%.1f"
                        )
                        updated_metrics["BMI"] = st.number_input(
                            "BMI (kg/m²)", value=float(patient_metrics["BMI"]), step=0.1, format="%.1f"
                        )
                        updated_metrics["BloodPressure"] = st.number_input(
                            "Blood Pressure (mmHg)", value=float(patient_metrics["BloodPressure"]), step=1.0, format="%.1f"
                        )
                        updated_metrics["Age"] = st.number_input(
                            "Age (years)", value=float(patient_metrics["Age"]), step=1.0, format="%.1f"
                        )

                        if st.button("💾 Save & Re-evaluate Risk", type="primary"):
                            model.update_patient(selected_id, updated_metrics)
                            st.toast(f"Patient #{selected_id} metrics updated successfully!", icon="✅")

                    with col_analysis:
                        st.subheader("Diagnostic Risk Analysis")
                        score, category = service.evaluate_patient_risk(updated_metrics)

                        # Top-level KPI Indicators
                        m1, m2 = st.columns(2)
                        m1.metric("Cumulative Score", f"{score} / 8 pts")
                        m2.metric("Overall Category", category)

                        if category == "Low Risk":
                            st.success("🟢 **LOW RISK**: Routine follow-up recommended.")
                        elif category == "Moderate Risk":
                            st.warning("🟡 **MODERATE RISK**: Lifestyle intervention recommended.")
                        else:
                            st.error("🔴 **HIGH RISK**: Immediate clinical evaluation required.")

                        st.divider()
                        st.markdown("##### Metric Status Breakdown")
                        for metric, value in updated_metrics.items():
                            status_label, status_class = service.get_metric_status_label(metric, value)
                            st.markdown(
                                f"""
                                <div class="metric-card {status_class}">
                                    <strong>{metric}:</strong> {value} 
                                    <span style="float: right; font-weight: bold;">{status_label}</span>
                                </div>
                                """, 
                                unsafe_allow_html=True
                            )

        # TAB 2: ADD PATIENT
        with tab_add:
            st.subheader("Add New Patient Record")
            with st.form("new_patient_form", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                with col_a:
                    new_glucose = st.number_input("Glucose Level", min_value=0.0, value=100.0, step=1.0)
                    new_bmi = st.number_input("BMI", min_value=0.0, value=24.0, step=0.1)
                with col_b:
                    new_bp = st.number_input("Blood Pressure", min_value=0.0, value=120.0, step=1.0)
                    new_age = st.number_input("Age", min_value=0.0, value=30.0, step=1.0)

                if st.form_submit_button("➕ Register Patient", type="primary"):
                    new_data = {
                        "Glucose": new_glucose,
                        "BMI": new_bmi,
                        "BloodPressure": new_bp,
                        "Age": new_age
                    }
                    new_id = model.add_patient(new_data)
                    st.success(f"Patient registered successfully with ID: **#{new_id}**")
                    st.rerun()

        # TAB 3: RECORDS & VISUALIZATION
        with tab_records:
            st.subheader("Database Overview")
            df = model.get_all_patients_df()
            
            if not df.empty:
                # Add calculated risk scores dynamically to DataFrame view
                scores = []
                categories = []
                for _, row in df.iterrows():
                    metrics = {"Glucose": row["Glucose"], "BMI": row["BMI"], "Age": row["Age"], "BloodPressure": row["BloodPressure"]}
                    s, c = service.evaluate_patient_risk(metrics)
                    scores.append(s)
                    categories.append(c)
                
                df["Risk Score"] = scores
                df["Risk Category"] = categories

                st.dataframe(df, use_container_width=True, hide_index=True)

                st.divider()
                st.subheader("Cohort Metrics Comparison")
                chart_data = df.set_index("patient_id")[["Glucose", "BMI", "BloodPressure", "Age"]]
                st.bar_chart(chart_data)


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
        
        assert service.calculate_metric_score("Glucose", 95.0) == 0, "Failed Glucose Low threshold"
        assert service.calculate_metric_score("Glucose", 110.0) == 1, "Failed Glucose Med threshold"
        assert service.calculate_metric_score("Glucose", 130.0) == 2, "Failed Glucose High threshold"
        
        assert service.calculate_metric_score("BMI", 25.0) == 0, "Border case BMI=25 failed"
        assert service.calculate_metric_score("BMI", 25.1) == 1, "Border case BMI=25.1 failed"
        
        score_low, cat_low = service.evaluate_patient_risk({"Glucose": 90.0, "BMI": 22.0, "Age": 30.0, "BloodPressure": 110.0})
        assert score_low == 0 and "Low" in cat_low, f"Expected Low Risk, got {score_low} pts ({cat_low})"
        
        score_med, cat_med = service.evaluate_patient_risk({"Glucose": 115.0, "BMI": 27.0, "Age": 45.0, "BloodPressure": 125.0})
        assert 3 <= score_med <= 5 and "Moderate" in cat_med, f"Expected Mod Risk, got {score_med} pts ({cat_med})"
        
        score_high, cat_high = service.evaluate_patient_risk({"Glucose": 140.0, "BMI": 35.0, "Age": 60.0, "BloodPressure": 135.0})
        assert score_high >= 6 and "High" in cat_high, f"Expected High Risk, got {score_high} pts ({cat_high})"
        
        print(" ✓ Tier 1 Unit Tests Pass: All rule sets mapped and categorized perfectly.")

    def run_tier2_e2e_scenarios(self) -> None:
        """Tier 2: E2E Scenario Tests covering cleaning, storage, modification, and scoring."""
        print("\n--- Running Tier 2: End-to-End Workflows ---")
        model = self.model_factory()
        service = self.service_class()
        
        patient_102 = model.get_patient(102)
        assert patient_102 is not None, "E2E Error: Patient 102 not found"
        assert patient_102["BMI"] > 0, f"E2E Error: Anomalous BMI of 0 was not replaced. Got {patient_102['BMI']}"
        
        baseline_low_metrics = {
            "Glucose": 85.0,
            "BMI": 20.0,
            "Age": 25.0,
            "BloodPressure": 110.0
        }
        model.update_patient(101, baseline_low_metrics)
        patient_101_base = model.get_patient(101)
        original_score, _ = service.evaluate_patient_risk(patient_101_base)
        
        modified_metrics = {
            "Glucose": 160.0,
            "BMI": 32.0,
            "Age": 60.0,
            "BloodPressure": 140.0
        }
        
        update_ok = model.update_patient(101, modified_metrics)
        assert update_ok, "E2E Error: Database modification write failed"
        
        updated_profile = model.get_patient(101)
        new_score, new_category = service.evaluate_patient_risk(updated_profile)
        
        assert new_score > original_score, f"E2E Error: Score did not increase (Old: {original_score}, New: {new_score})"
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
# SYSTEM APPLICATION ENTRY POINT (STREAMLIT)
# =====================================================================
if __name__ == "__main__":
    if RUN_TEST_SUITE:
        suite = RiskAssessmentTestSuite(model_factory=PatientModel, service_class=ClinicalRiskService)
        suite.run_all_tiers()
    
    # Initialize Model and Service in Streamlit Session State
    if "db_model" not in st.session_state:
        st.session_state.db_model = PatientModel()
    if "rules_service" not in st.session_state:
        st.session_state.rules_service = ClinicalRiskService()
    
    # Render UI
    StreamlitView.render_app(
        model=st.session_state.db_model, 
        service=st.session_state.rules_service
    )
