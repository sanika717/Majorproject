"""
Unit tests for EsgEngine — deterministic CPCB AQI calculations and ESG scoring.
Tests exact CPCB breakpoints, boundary conditions, attribution, and pillar weights.
"""

import pytest
from backend.app.engines.esg_engine import EsgEngine, MetricAttribution


class TestCpcbAqiCalculation:
    """Unit tests for CPCB National Air Quality Index formula."""

    def test_good_category_low_pm25(self):
        result = EsgEngine.calculate_cpcb_aqi(pm25=15.0, pm10=None)
        assert result.aqi_score == 25
        assert result.category == "Good"
        assert result.dominant_pollutant == "PM2.5"

    def test_satisfactory_category(self):
        result = EsgEngine.calculate_cpcb_aqi(pm25=45.0, pm10=None)
        assert result.aqi_score <= 100
        assert result.category in ("Good", "Satisfactory")

    def test_moderate_pm10_dominant(self):
        result = EsgEngine.calculate_cpcb_aqi(pm25=None, pm10=180.0)
        assert result.aqi_score > 100
        assert result.category == "Moderate"
        assert result.dominant_pollutant == "PM10"

    def test_exact_cpcb_bp_boundary_pm25_30(self):
        """PM2.5=30 is at upper bound of Good breakpoint → AQI=50."""
        result = EsgEngine.calculate_cpcb_aqi(pm25=30.0, pm10=None)
        assert result.aqi_score == 50
        assert result.category == "Good"

    def test_exact_cpcb_bp_boundary_pm25_31(self):
        """PM2.5=31 falls in Satisfactory range."""
        result = EsgEngine.calculate_cpcb_aqi(pm25=31.0, pm10=None)
        assert result.aqi_score == 51
        assert result.category == "Satisfactory"

    def test_both_none_returns_unavailable(self):
        result = EsgEngine.calculate_cpcb_aqi(pm25=None, pm10=None)
        assert result.aqi_score == 0
        assert result.category == "Unavailable"
        assert result.attribution == MetricAttribution.UNAVAILABLE

    def test_one_pollutant_missing_gives_estimated(self):
        result = EsgEngine.calculate_cpcb_aqi(pm25=50.0, pm10=None)
        assert result.attribution == MetricAttribution.ESTIMATED

    def test_both_pollutants_gives_actual(self):
        result = EsgEngine.calculate_cpcb_aqi(pm25=20.0, pm10=40.0)
        assert result.attribution == MetricAttribution.ACTUAL

    def test_severe_category_above_400(self):
        result = EsgEngine.calculate_cpcb_aqi(pm25=300.0, pm10=None)
        assert result.aqi_score > 400
        assert result.category == "Severe"

    def test_pm10_at_250_boundary(self):
        """PM10=250 is at upper bound of Moderate breakpoint → AQI=200."""
        result = EsgEngine.calculate_cpcb_aqi(pm25=None, pm10=250.0)
        assert result.aqi_score == 200
        assert result.category == "Moderate"

    def test_negative_concentration_treated_as_zero(self):
        result = EsgEngine.calculate_cpcb_aqi(pm25=-5.0, pm10=None)
        assert result.aqi_score == 0


class TestEsgPillarScoring:
    """Unit tests for deterministic ESG pillar score calculations."""

    def test_environmental_pillar_all_data_available(self):
        result = EsgEngine.calculate_environmental_pillar(aqi_score=80, avg_lake_bod=4.0)
        assert 0 <= result.score <= 100
        assert result.attribution == MetricAttribution.ACTUAL
        assert result.pillar == "Environmental"
        assert result.data_points_missing == 0

    def test_environmental_pillar_missing_aqi(self):
        result = EsgEngine.calculate_environmental_pillar(aqi_score=None, avg_lake_bod=3.0)
        assert result.attribution == MetricAttribution.ESTIMATED
        assert result.data_points_missing == 1

    def test_environmental_pillar_all_missing(self):
        result = EsgEngine.calculate_environmental_pillar(aqi_score=None, avg_lake_bod=None, energy_efficiency_score=None)
        assert result.attribution == MetricAttribution.UNAVAILABLE

    def test_social_pillar_complaint_resolution(self):
        result = EsgEngine.calculate_social_pillar(
            complaint_resolution_rate=85.0,
            safety_index=70.0,
        )
        assert 0 <= result.score <= 100
        # civic_infrastructure_score has a default of 70.0, so 3 data points are always available
        assert result.data_points_available >= 2

    def test_governance_pillar_all_data(self):
        result = EsgEngine.calculate_governance_pillar(
            contractor_diversity_score=72.0,
            expenditure_transparency_score=68.0,
            audit_compliance_score=80.0,
        )
        assert result.data_points_missing == 0
        assert result.attribution == MetricAttribution.ACTUAL

    def test_composite_esg_weights_sum(self):
        env = EsgEngine.calculate_environmental_pillar(aqi_score=50, avg_lake_bod=3.0)
        soc = EsgEngine.calculate_social_pillar(complaint_resolution_rate=70.0, safety_index=65.0)
        gov = EsgEngine.calculate_governance_pillar(contractor_diversity_score=60.0, expenditure_transparency_score=70.0)
        composite = EsgEngine.calculate_composite_esg(env, soc, gov)
        assert composite.weights["environmental"] + composite.weights["social"] + composite.weights["governance"] == pytest.approx(1.0)

    def test_composite_esg_score_range(self):
        env = EsgEngine.calculate_environmental_pillar(aqi_score=100, avg_lake_bod=5.0)
        soc = EsgEngine.calculate_social_pillar(complaint_resolution_rate=60.0, safety_index=55.0)
        gov = EsgEngine.calculate_governance_pillar(contractor_diversity_score=70.0, expenditure_transparency_score=65.0)
        composite = EsgEngine.calculate_composite_esg(env, soc, gov)
        assert 0 <= composite.composite_score <= 100
        assert composite.grade in ("A+", "A", "B+", "B", "C", "D")

    def test_grade_boundaries(self):
        env = EsgEngine.calculate_environmental_pillar(aqi_score=0, avg_lake_bod=1.0)
        soc = EsgEngine.calculate_social_pillar(complaint_resolution_rate=100.0, safety_index=100.0)
        gov = EsgEngine.calculate_governance_pillar(contractor_diversity_score=100.0, expenditure_transparency_score=100.0)
        composite = EsgEngine.calculate_composite_esg(env, soc, gov)
        assert composite.grade in ("A+", "A")
