"""
Unit tests for Data Adapters: normalization, validation, missing-value handling.
Tests all adapters against valid, partial, malformed, and empty datasets.
"""

import pytest
from backend.app.adapters.bbmp_adapter import BbmpWorkOrderAdapter
from backend.app.adapters.crime_adapter import CrimeDataAdapter
from backend.app.adapters.aqi_adapter import AqiDataAdapter
from backend.app.adapters.water_adapter import WaterQualityAdapter
from backend.app.adapters.electricity_adapter import ElectricityDataAdapter
from backend.app.adapters.geospatial_adapter import GeospatialDataAdapter
from backend.app.adapters.factory import AdapterFactory
from backend.app.adapters.base import DataQualityLevel


# ─── BBMP Work Order Adapter ─────────────────────────────────────────────────

class TestBbmpAdapter:
    def setup_method(self):
        self.adapter = BbmpWorkOrderAdapter()

    def _valid_row(self, overrides=None):
        base = {
            "work_order_number": "WO/BBMP/2025/001",
            "ward_number": 42,
            "gross_amount": 500000.0,
            "net_amount": 450000.0,
            "deduction": 50000.0,
            "category": "Road",
            "contractor_name": "ABC Constructions",
        }
        if overrides:
            base.update(overrides)
        return base

    def test_normalize_valid_row(self):
        rows = self.adapter.normalize([self._valid_row()])
        assert len(rows) == 1
        assert rows[0]["work_order_number"] == "WO/BBMP/2025/001"
        assert rows[0]["ward_number"] == 42
        assert rows[0]["gross_amount"] == 500000.0

    def test_normalize_empty_returns_empty(self):
        assert self.adapter.normalize([]) == []

    def test_normalize_handles_aliases(self):
        rows = self.adapter.normalize([{"wo_number": "W999", "ward": 10, "amount": 300000}])
        assert rows[0]["work_order_number"] == "W999"
        assert rows[0]["ward_number"] == 10

    def test_validate_valid_data(self):
        rows = self.adapter.normalize([self._valid_row()])
        result = self.adapter.validate(rows)
        assert result.is_valid is True
        assert result.data_quality == DataQualityLevel.ACTUAL

    def test_validate_missing_work_order_number(self):
        rows = self.adapter.normalize([self._valid_row({"work_order_number": ""})])
        result = self.adapter.validate(rows)
        assert result.is_valid is False

    def test_validate_missing_ward_number(self):
        rows = self.adapter.normalize([{"work_order_number": "WO001", "ward_number": None, "gross_amount": 100000}])
        result = self.adapter.validate(rows)
        assert not result.is_valid
        assert "ward_number" in result.missing_fields

    def test_validate_negative_gross_amount(self):
        rows = self.adapter.normalize([self._valid_row({"gross_amount": -1000})])
        result = self.adapter.validate(rows)
        assert result.is_valid is False

    def test_validate_empty_dataset(self):
        result = self.adapter.validate([])
        assert result.is_valid is False
        assert result.data_quality == DataQualityLevel.UNAVAILABLE

    def test_handle_missing_fills_ward_name(self):
        rows = self.adapter.normalize([self._valid_row({"ward_name": ""})])
        cleaned = self.adapter.handle_missing(rows)
        assert "Ward 42" in cleaned[0]["ward_name"]

    def test_handle_missing_fills_contractor_name(self):
        rows = self.adapter.normalize([self._valid_row({"contractor_name": ""})])
        cleaned = self.adapter.handle_missing(rows)
        assert "Undisclosed" in cleaned[0]["contractor_name"] or "BBMP" in cleaned[0]["contractor_name"]

    def test_fetch_from_list_passthrough(self):
        data = [{"work_order_number": "X1", "ward_number": 5, "gross_amount": 50000}]
        fetched = self.adapter.fetch(data)
        assert fetched == data

    def test_fetch_from_json_string(self):
        import json
        data = [{"work_order_number": "X2", "ward_number": 10, "gross_amount": 75000}]
        fetched = self.adapter.fetch(json.dumps(data))
        assert isinstance(fetched, list)
        assert fetched[0]["work_order_number"] == "X2"

    def test_fetch_malformed_json_returns_empty(self):
        fetched = self.adapter.fetch("{not_valid_json")
        assert fetched == []


# ─── Crime Data Adapter ───────────────────────────────────────────────────────

class TestCrimeAdapter:
    def setup_method(self):
        self.adapter = CrimeDataAdapter()

    def _valid_row(self, overrides=None):
        base = {"category": "Theft", "year": 2021, "total_cases": 500, "fatal_cases": 30}
        if overrides:
            base.update(overrides)
        return base

    def test_normalize_valid_row(self):
        rows = self.adapter.normalize([self._valid_row()])
        assert rows[0]["category"] == "Theft"
        assert rows[0]["year"] == 2021
        assert rows[0]["total_cases"] == 500

    def test_normalize_handles_aliases(self):
        rows = self.adapter.normalize([{"crime_type": "Assault", "crime_year": 2020, "cases_reported": 200}])
        assert rows[0]["category"] == "Assault"
        assert rows[0]["year"] == 2020
        assert rows[0]["total_cases"] == 200

    def test_validate_valid_data(self):
        rows = self.adapter.normalize([self._valid_row()])
        result = self.adapter.validate(rows)
        assert result.is_valid is True

    def test_validate_missing_category(self):
        rows = self.adapter.normalize([self._valid_row({"category": ""})])
        result = self.adapter.validate(rows)
        assert result.is_valid is False
        assert "category" in result.missing_fields

    def test_validate_fatal_exceeds_total_gives_warning(self):
        rows = self.adapter.normalize([self._valid_row({"fatal_cases": 600, "total_cases": 500})])
        result = self.adapter.validate(rows)
        assert len(result.warnings) > 0

    def test_handle_missing_fills_non_fatal(self):
        rows = self.adapter.normalize([self._valid_row({"non_fatal_cases": None})])
        cleaned = self.adapter.handle_missing(rows)
        assert cleaned[0]["non_fatal_cases"] == max(0, 500 - 30)

    def test_validate_empty_dataset(self):
        result = self.adapter.validate([])
        assert result.is_valid is False
        assert result.data_quality == DataQualityLevel.UNAVAILABLE


# ─── AQI Data Adapter ─────────────────────────────────────────────────────────

class TestAqiAdapter:
    def setup_method(self):
        self.adapter = AqiDataAdapter()

    def _valid_row(self):
        return {
            "station_name": "Central Bengaluru CPCB",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "pm25": 45.0,
            "pm10": 85.0,
        }

    def test_normalize_flat_row(self):
        rows = self.adapter.normalize([self._valid_row()])
        assert rows[0]["pm25"] == 45.0
        assert rows[0]["latitude"] == 12.9716

    def test_normalize_open_meteo_format(self):
        raw = {
            "latitude": 12.9716,
            "longitude": 77.5946,
            "current": {"pm2_5": 55.0, "pm10": 90.0, "nitrogen_dioxide": 25.0}
        }
        rows = self.adapter.normalize(raw)
        assert len(rows) == 1
        assert rows[0]["pm25"] == 55.0
        assert rows[0]["no2"] == 25.0

    def test_validate_inside_bengaluru_bounds(self):
        rows = self.adapter.normalize([self._valid_row()])
        result = self.adapter.validate(rows)
        assert result.is_valid is True

    def test_validate_outside_bengaluru_gives_warning(self):
        row = self._valid_row()
        row["latitude"] = 19.0
        row["longitude"] = 72.8
        rows = self.adapter.normalize([row])
        result = self.adapter.validate(rows)
        assert len(result.warnings) > 0

    def test_validate_negative_pm25_error(self):
        row = self._valid_row()
        row["pm25"] = -10.0
        rows = self.adapter.normalize([row])
        result = self.adapter.validate(rows)
        assert result.is_valid is False

    def test_handle_missing_flags_missing_pm25(self):
        row = self._valid_row()
        row.pop("pm25")
        rows = self.adapter.normalize([row])
        cleaned = self.adapter.handle_missing(rows)
        assert cleaned[0]["pm25_missing"] is True

    def test_validate_empty_dataset(self):
        result = self.adapter.validate([])
        assert result.is_valid is False


# ─── Water Quality Adapter ───────────────────────────────────────────────────

class TestWaterAdapter:
    def setup_method(self):
        self.adapter = WaterQualityAdapter()

    def test_normalize_valid(self):
        rows = self.adapter.normalize([{
            "station_name": "Bellandur Lake Station A",
            "body_name": "Bellandur Lake",
            "bod": 8.5,
            "ph": 7.2,
            "dissolved_oxygen": 3.1,
        }])
        assert rows[0]["station_name"] == "Bellandur Lake Station A"
        assert rows[0]["bod"] == 8.5

    def test_water_class_derived_from_bod(self):
        rows = self.adapter.normalize([{
            "station_name": "Test Station",
            "body_name": "Test Lake",
            "bod": 1.5,
        }])
        assert rows[0]["water_class"] == "A"

    def test_validate_invalid_ph(self):
        rows = self.adapter.normalize([{
            "station_name": "Bad Station",
            "body_name": "Bad Lake",
            "ph": 15.0,
        }])
        result = self.adapter.validate(rows)
        assert result.is_valid is False

    def test_validate_missing_names(self):
        result = self.adapter.validate([{"ph": 7.0}])
        assert result.is_valid is False

    def test_validate_empty_dataset(self):
        result = self.adapter.validate([])
        assert result.is_valid is False


# ─── Electricity Adapter ──────────────────────────────────────────────────────

class TestElectricityAdapter:
    def setup_method(self):
        self.adapter = ElectricityDataAdapter()

    def test_normalize_valid(self):
        rows = self.adapter.normalize([{
            "sub_division": "Indiranagar",
            "consumption_kwh": 450000.0,
            "consumer_count": 12000,
        }])
        assert rows[0]["consumption_kwh"] == 450000.0

    def test_validate_negative_kwh(self):
        rows = self.adapter.normalize([{
            "sub_division": "Whitefield",
            "consumption_kwh": -1000,
        }])
        result = self.adapter.validate(rows)
        assert result.is_valid is False

    def test_validate_missing_sub_division(self):
        rows = self.adapter.normalize([{"consumption_kwh": 100000}])
        result = self.adapter.validate(rows)
        assert result.is_valid is False

    def test_handle_missing_fills_category(self):
        rows = self.adapter.normalize([{"sub_division": "Koramangala", "consumption_kwh": 200000}])
        cleaned = self.adapter.handle_missing(rows)
        assert cleaned[0]["category"]  # category is set to a non-empty default


# ─── Geospatial Adapter ───────────────────────────────────────────────────────

class TestGeospatialAdapter:
    def setup_method(self):
        self.adapter = GeospatialDataAdapter()

    def test_normalize_flat_row(self):
        rows = self.adapter.normalize([{
            "name": "Indiranagar PS",
            "latitude": 12.9784,
            "longitude": 77.6408,
            "category": "police_station",
        }])
        assert rows[0]["name"] == "Indiranagar PS"
        assert rows[0]["latitude"] == 12.9784

    def test_normalize_geojson_feature_collection(self):
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [77.6408, 12.9784]},
                    "properties": {"name": "Koramangala PS"},
                }
            ],
        }
        rows = self.adapter.normalize(geojson)
        assert len(rows) == 1
        assert rows[0]["name"] == "Koramangala PS"
        assert rows[0]["longitude"] == 77.6408

    def test_validate_inside_bengaluru(self):
        rows = self.adapter.normalize([{
            "name": "MG Road PS",
            "latitude": 12.9757,
            "longitude": 77.6075,
        }])
        result = self.adapter.validate(rows)
        assert result.is_valid is True

    def test_validate_outside_bengaluru_warns(self):
        rows = self.adapter.normalize([{
            "name": "Far Away",
            "latitude": 18.5,
            "longitude": 73.8,
        }])
        result = self.adapter.validate(rows)
        assert len(result.warnings) > 0

    def test_validate_missing_coordinates(self):
        rows = self.adapter.normalize([{"name": "No Coords"}])
        result = self.adapter.validate(rows)
        assert result.is_valid is False

    def test_validate_empty_dataset(self):
        result = self.adapter.validate([])
        assert result.is_valid is False


# ─── Adapter Factory ──────────────────────────────────────────────────────────

class TestAdapterFactory:
    def test_get_bbmp_adapter(self):
        adapter = AdapterFactory.get_adapter("bbmp")
        assert isinstance(adapter, BbmpWorkOrderAdapter)

    def test_get_crime_adapter_by_alias(self):
        adapter = AdapterFactory.get_adapter("crime_statistics")
        assert isinstance(adapter, CrimeDataAdapter)

    def test_get_aqi_adapter(self):
        adapter = AdapterFactory.get_adapter("aqi")
        assert isinstance(adapter, AqiDataAdapter)

    def test_get_water_adapter(self):
        adapter = AdapterFactory.get_adapter("water_quality")
        assert isinstance(adapter, WaterQualityAdapter)

    def test_get_electricity_adapter(self):
        adapter = AdapterFactory.get_adapter("bescom")
        assert isinstance(adapter, ElectricityDataAdapter)

    def test_get_geospatial_adapter(self):
        adapter = AdapterFactory.get_adapter("police_locations")
        assert isinstance(adapter, GeospatialDataAdapter)

    def test_case_insensitive_lookup(self):
        adapter = AdapterFactory.get_adapter("BBMP")
        assert isinstance(adapter, BbmpWorkOrderAdapter)

    def test_unknown_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported adapter source type"):
            AdapterFactory.get_adapter("unknown_dataset_type")

    def test_register_custom_adapter(self):
        class DummyAdapter(BbmpWorkOrderAdapter):
            pass
        AdapterFactory.register_adapter("custom_test", DummyAdapter)
        adapter = AdapterFactory.get_adapter("custom_test")
        assert isinstance(adapter, DummyAdapter)
