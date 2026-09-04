# AI Assistance Disclosure & Validation Log

In accordance with Section Part 1, Item 5 of the challenge brief, this document transparently describes how AI assistance was leveraged, how outputs were critically validated, and specific AI-generated errors that were caught and corrected.

---

## 1. Scope of AI Tool Usage

AI assistance was utilized for:
1. **Accelerated Data Profiling**: Formulating initial exploratory scripts to inspect schema distributions across 1.43 million telemetry records and 8 monthly Parquet partitions.
2. **Cross-Tabulation & Statistical Auditing**: Rapidly querying historical correlations between reported work order reasons (`reason_reported`) and actual on-site outcomes (`Fehler behoben` vs `Kein Fehler gefunden`).
3. **Scaffolding Infrastructure**: Generating baseline boilerplate for `Dockerfile`, `docker-compose.yml`, and `Makefile`.

---

## 2. AI Errors Caught & Corrected

### Error 1: Assumption of Standard UTF-8 Encoding for German System Exports
* **What the AI Did**: In initial exploratory scripts, the AI wrote standard `pd.read_csv("data/gateway_master.csv")` without specifying an encoding.
* **The Failure**: The script crashed during execution with:
  ```text
  UnicodeDecodeError: 'utf-8' codec can't decode byte 0xdf in position 161: invalid continuation byte
  ```
* **Why It Happened**: The AI assumed modern web standard UTF-8. However, the data originated from legacy German enterprise utility systems exported in Windows-1252 / ISO-8859-1 (`latin1`). Byte `0xdf` is the German Eszett (`ß` in *Außenmast*), and `0xe4` is `ä` in *Gebäude*.
* **The Correction**: Replaced naive parsing with an automated fallback mechanism:
  ```python
  for enc in ["latin1", "cp1252", "iso-8859-1", "utf-8"]:
      try:
          df = pd.read_csv(master_path, encoding=enc)
          break
      except (UnicodeDecodeError, Exception):
          continue
  ```

---

### Error 2: Treating Cumulative Firmware Counter as Hourly Discrete Duration
* **What the AI Did**: The AI suggested calculating an "hourly downtime percentage" by computing:
  $$\text{downtime\_ratio} = \frac{\text{offline\_duration\_sec}}{3600}$$
  assuming that an hour contains 3,600 seconds and the metric represented duration within that hour.
* **The Failure**: Sanity checks on the distribution revealed values exceeding **726,642 seconds (~8.4 days)**, generating nonsensical ratios above 20,000%.
* **Why It Happened**: The AI overlooked the fine print in the Data Dictionary: *"Backhaul offline time counter, seconds."* It is a **running cumulative counter** maintained by firmware across persistent outages, not an hourly windowed measurement.
* **The Correction**: Prevented naive statistical aggregation over cumulative counters. Instead, downtime is quantified by detecting periods of continuous disconnection and reporting absence, or computing first-differences ($\Delta$) bounded by zero.
