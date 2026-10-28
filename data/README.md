# Data

Readings of three smart water meters installed at cafeterias of the Víctor Levi Sasso campus,
Universidad Tecnológica de Panamá.

| File | Cafeteria | Rows | First reading | Last reading |
|---|---|---|---|---|
| `CAF_C1_readings.csv` | CAF_C1 | 4,216 | 2023-10-29 23:39 | 2025-06-26 09:24 |
| `CAF_CENTRAL_readings.csv` | CAF_CENTRAL | 49,024 | 2023-10-29 23:55 | 2025-09-10 17:55 |
| `CAF_C3_readings.csv` | CAF_C3 | 40,887 | 2023-10-29 23:26 | 2025-09-10 17:56 |

## Columns

| Column | Unit | Description |
|---|---|---|
| `datetime` | local time (UTC−5) | time of the reading, `YYYY-MM-DD HH:MM:SS` |
| `volume_L` | L | cumulative volume registered by the meter |

## Processing applied to these files

* Timestamps were exported by the meter platform in UTC and shifted by −5 h to local time
  (Panama has no daylight saving time).
* Rows were sorted by time; one duplicated timestamp in `CAF_CENTRAL` (same reading twice)
  was removed.
* No other change: readings are not resampled, interpolated or filtered.

## Known limitations

* The nominal interval is 15 min, but intervals of 30–60 min are frequent and there are gaps
  of several days (see notebook 1).
* `CAF_C1` is very sparse and has no readings after 26 June 2025.

## License

[CC BY 4.0](../LICENSE-DATA.md).
