# 5 Key Decisions I Made (and What I Rejected)

Here are the five main engineering choices I made while building this solution, what else I considered, and why I chose this path.

---

### Decision 1: Catching "Dead" Gateways Instead of Just Counting Spikes
* **What I did**: I explicitly check if active gateways have gone completely silent (zero or near-zero telemetry in the last 7 days after running normally for the past month) and send technicians there first.
* **What else I could have done**: I could have just stuck with naive 3-sigma anomaly scoring like the baseline script does.
* **Why I rejected it**: When a gateway has a catastrophic hardware failure (like a blown power supply), it stops sending telemetry completely. The baseline script only groups rows that actually exist in the last 7 days. If a gateway sends zero rows, the baseline assigns it zero flags and never visits it! In February 2026 alone, 21 broken gateways were completely silent, and customer complaints were piling up. Leaving them broken costs €600 every single week. Catching silent gateways had to be priority number one.

---

### Decision 2: Automatic File Encoding and ID Normalization
* **What I did**: I wrote the data loader to automatically try `latin1`, `cp1252`, and `utf-8`, and cleaned all gateway IDs into standard 12-character uppercase hex strings.
* **What else I could have done**: I could have manually re-saved the files as clean UTF-8 on my laptop before running the code.
* **Why I rejected it**: The challenge brief is clear: the code must run on an evaluator's machine against the untouched raw data folder. The German system exports contain special characters like `ß` in *Außenmast* (byte `0xdf`) and `ä` in *Gebäude*, which instantly crash Python's standard `read_csv()` with a `UnicodeDecodeError`. Also, the master file uses MAC colons (`06:39:EA:56:02:C1`) while telemetry uses bare hex (`0639EA5602C1`). If you don't clean both automatically, your code either crashes or joins zero rows.

---

### Decision 3: Prioritizing Dropped Packets and Power Loops Over Raw Disconnects
* **What I did**: I scored gateways based on whether their LoRa packet throughput dropped by more than 70% (`rx_nr_pkts`) and whether they were caught in long power-cycling restart loops (`r_dur_power_cycle > 60s`).
* **What else I could have done**: I could have just counted how many times a gateway disconnected or rebooted.
* **Why I rejected it**: When I looked at the 642 past work orders, **60.7% of past visits found no problem**. Even crazier: **100% of visits sent out for 'unusual statistics' were false alarms**. Healthy gateways with very quiet baselines spike past 3-sigma on routine, harmless blips. Meanwhile, true physical defects (like dying power supplies, which accounted for 39 replacements) show up as long power-cycle loops. Most importantly, unread meter penalties happen when LoRa packets stop arriving, so measuring dropped packets directly targets the real business problem.

---

### Decision 4: Skipping Decommissioned (Retired) Gateways
* **What I did**: I cross-referenced `gateway_master.csv` at each target week to make sure we never send technicians to gateways that were already taken out of service.
* **What else I could have done**: Just run the ranking on all historical telemetry without checking the master inventory.
* **Why I rejected it**: 12 gateways in the fleet were decommissioned during this period (like `02:EB:C6:CD:43:98`, which was retired on 2026-02-04). When a gateway is being shut down or uninstalled, it often shows erratic disconnects and eventually goes silent. If you don't filter against decommissioning dates, the model will waste a €380 visit on equipment that has already been taken down.

---

### Decision 5: Picking Track D (Data Science) to Solve the Real Cost Problem
* **What I did**: I chose **Track D: Data Science** to answer the core question the brief left open: what does "needs a visit" actually mean, and how do we balance the €380 visit cost against the €600 weekly delay penalty?
* **What else I could have done**: I could have picked Software Development (building a web API) or Machine Learning (training a classifier).
* **Why I rejected it**: Right now, the field team picks visits using gut feel and a spreadsheet, which wastes €3,420 every single week on false alarms. Building a fancy web API or throwing a black-box ML model at bad labels doesn't fix the underlying problem. Data Science allowed me to tackle the real economics ($€600 / €380 \approx 1.58$), prove why statistical outliers were wasting money, and give the Operations Manager an optimal threshold ($p^* = 0.65$) that delivers estimated annual savings of €28,000 to €45,000.
