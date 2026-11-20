# NYC 311 Data Quality Report

**Generated:** 2026-11-20 23:09:14  
**Rows analysed:** 10,000  
**Columns:** 44  

---

## 1. Null Values

| Column | Null Count | Null % |
|--------|-----------|--------|
| closed_date | 56 | 0.56% |
| descriptor | 296 | 2.96% |
| location_type | 824 | 8.24% |
| incident_zip | 117 | 1.17% |
| incident_address | 292 | 2.92% |
| street_name | 292 | 2.92% |
| cross_street_1 | 2,244 | 22.44% |
| cross_street_2 | 2,225 | 22.25% |
| intersection_street_1 | 2,628 | 26.28% |
| intersection_street_2 | 2,612 | 26.12% |
| address_type | 62 | 0.62% |
| city | 469 | 4.69% |
| landmark | 3,198 | 31.98% |
| resolution_description | 40 | 0.4% |
| resolution_action_updated_date | 34 | 0.34% |
| council_district | 206 | 2.06% |
| bbl | 982 | 9.82% |
| x_coordinate_state_plane | 150 | 1.5% |
| y_coordinate_state_plane | 145 | 1.45% |
| park_facility_name | 6 | 0.06% |
| latitude | 152 | 1.52% |
| longitude | 152 | 1.52% |
| location | 152 | 1.52% |
| descriptor_2 | 6,896 | 68.96% |
| taxi_pick_up_location | 9,915 | 99.15% |
| facility_type | 9,946 | 99.46% |
| bridge_highway_name | 9,944 | 99.44% |
| bridge_highway_segment | 9,944 | 99.44% |
| road_ramp | 9,976 | 99.76% |
| bridge_highway_direction | 9,972 | 99.72% |
| vehicle_type | 9,994 | 99.94% |
| taxi_company_borough | 9,996 | 99.96% |
| due_date | 9,984 | 99.84% |

## 2. Duplicates

- **Exact duplicate rows:** 0 (0.0%)
- **Duplicate unique_key values:** 0

## 3. Date Issues

- **created_date** — unparseable: 0, future: 0
- **closed_date** — unparseable: 0, future: 0
- **closed_before_created:** 0 rows

## 4. Coordinate Issues

- **latitude** — non-numeric: 0, out-of-range: 3
- **longitude** — non-numeric: 0, out-of-range: 0
- **Likely lat/lon swapped:** 0 rows

## 5. Text Length Anomalies

| Column | Mean Len | Min | Max | Outliers |
|--------|----------|-----|-----|---------|
| descriptor | 16.2 | 3 | 71 | 915 |
| resolution_description | 160.5 | 26 | 930 | 839 |
| incident_address | 17.8 | 3 | 37 | 17 |

## 6. Type Issues

No type issues detected.

## 7. Cardinality / Value Distribution


### borough (6 unique values, 0 nulls)

| Value | Count |
|-------|-------|
| BROOKLYN | 2,948 |
| QUEENS | 2,599 |
| MANHATTAN | 2,053 |
| BRONX | 2,008 |
| STATEN ISLAND | 359 |

### agency (14 unique values, 0 nulls)

| Value | Count |
|-------|-------|
| NYPD | 5,676 |
| HPD | 1,725 |
| DSNY | 671 |
| DOT | 431 |
| DEP | 350 |

### complaint_type (124 unique values, 0 nulls)

| Value | Count |
|-------|-------|
| Noise - Residential | 1,762 |
| Illegal Parking | 1,614 |
| HEAT/HOT WATER | 831 |
| Blocked Driveway | 683 |
| Noise - Street/Sidewalk | 552 |

### status (7 unique values, 0 nulls)

| Value | Count |
|-------|-------|
| Closed | 9,943 |
| In Progress | 44 |
| Open | 5 |
| Assigned | 4 |
| Pending | 2 |

## 8. PII Heuristic

- Phone numbers found in `descriptor`: **0**
- Email addresses found in `descriptor`: **0**