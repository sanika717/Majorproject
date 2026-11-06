# Dataset Adapters — Design & Usage

## Purpose

Each external data source has a dedicated **Adapter** class implementing the
`BaseDataAdapter` interface. Adapters enforce a consistent 5-step pipeline:

```
fetch() → normalize() → validate() → handle_missing() → ingest()
```

This guarantees that **no malformed, incomplete, or fabricated data enters the domain model**.

---

## BaseDataAdapter Interface

```python
class BaseDataAdapter(ABC):
    def fetch(self, source_input) -> Any             # Retrieve raw data
    def normalize(self, raw_data) -> List[Dict]      # Standardize format
    def validate(self, data) -> ValidationResult     # Check schema & bounds
    def handle_missing(self, data) -> List[Dict]     # Deterministic imputation
    def ingest(self, db, data) -> AdapterResult      # Persist results
```

**ValidationResult** fields: `is_valid`, `errors`, `warnings`, `missing_fields`, `data_quality`

**DataQualityLevel** enum: `actual` | `estimated` | `unavailable`

---

## Available Adapters

### BbmpWorkOrderAdapter (`bbmp_adapter.py`)

- **Source:** BBMP Work Orders CSV / JSON (annual capital expenditure)
- **Aliases:** `bbmp`, `bbmp_work_orders`, `construction`
- **Required fields:** `work_order_number`, `ward_number`, `gross_amount`
- **Aliases handled:** `wo_number`, `ward`, `amount` → normalized to standard keys
- **Validation:** ward number 1-250 bounds, negative amount rejection
- **Missing handling:** auto-generate ward name from number, fill contractor as "Undisclosed / BBMP Direct"

### CrimeDataAdapter (`crime_adapter.py`)

- **Source:** Bengaluru City Police D47 annual crime statistics
- **Aliases:** `crime`, `crime_statistics`
- **Required fields:** `category`, `year`, `total_cases`
- **Aliases handled:** `crime_type`, `crime_year`, `cases_reported`
- **Validation:** year range 2000-2030, negative case count rejection, fatal > total warning
- **Missing handling:** auto-compute `non_fatal_cases = total - fatal`

### AqiDataAdapter (`aqi_adapter.py`)

- **Source:** Open-Meteo CAMS / CPCB / Google Air Quality API
- **Aliases:** `aqi`, `air_quality`, `environment`
- **Formats:** Flat dict, Open-Meteo `{current: {...}}` JSON structure, list
- **Validation:** Bengaluru bounding box (lat 12.0-14.0, lon 77.0-78.5), PM2.5 ≤ 1000
- **Missing handling:** flags `pm25_missing`, `pm10_missing` explicitly (no fabrication)

### WaterQualityAdapter (`water_adapter.py`)

- **Source:** KSPCB MINARS lake/river water quality sampling records
- **Aliases:** `water`, `water_quality`
- **CPCB Class Derivation:** BOD ≤2 → A, ≤3 → B, ≤6 → C, ≤10 → D, >10 → E
- **Validation:** pH 0-14 bounds, negative BOD rejection
- **Missing handling:** derives `body_name` from `station_name` if absent

### ElectricityDataAdapter (`electricity_adapter.py`)

- **Source:** BESCOM electricity consumption by sub-division
- **Aliases:** `electricity`, `energy`, `bescom`
- **Required fields:** `sub_division`, `consumption_kwh`
- **Validation:** negative kWh rejection, consumer count ≥ 1 warning
- **Missing handling:** default category assignment, consumer_count fallback

### GeospatialDataAdapter (`geospatial_adapter.py`)

- **Source:** Karnataka Police KML / GeoJSON, ward boundary GeoJSON
- **Aliases:** `geospatial`, `police_locations`
- **Formats:** Flat dict with lat/lon, GeoJSON FeatureCollection
- **Validation:** Bengaluru bounding box (lat 12.75-13.20, lon 77.40-77.80)
- **Missing handling:** fills `division` with "Bengaluru City Police Central Command"

---

## AdapterFactory Usage

```python
from backend.app.adapters.factory import AdapterFactory

# Get by source type string
adapter = AdapterFactory.get_adapter("bbmp")
adapter = AdapterFactory.get_adapter("aqi")
adapter = AdapterFactory.get_adapter("crime_statistics")

# Register a custom adapter at runtime
AdapterFactory.register_adapter("my_source", MyCustomAdapter)
```

---

## AdapterResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `source_name` | str | Adapter identifier |
| `status` | str | `"success"`, `"partial"`, `"failed"` |
| `records_processed` | int | Successfully handled records |
| `records_failed` | int | Failed records |
| `validation` | ValidationResult | Full validation output |
| `data_quality` | DataQualityLevel | `actual`, `estimated`, `unavailable` |
| `provenance_hash` | str | SHA-256 of normalized payload |
| `timestamp` | str | ISO-8601 UTC timestamp |
