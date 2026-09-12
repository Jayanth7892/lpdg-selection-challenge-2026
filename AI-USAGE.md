# AI Usage & Challenges Faced

During this challenge, I used **Gemini** and **Claude** as pair-programming assistants. This document explains what I used them for, where they were helpful, and the real mistakes they made that I had to catch and fix.

---

## 1. What I Used AI For

* **Exploring the Data Quickly**: The telemetry dataset has 1.4 million rows across 8 monthly Parquet folders. I used Gemini and Claude to write quick Python snippets to inspect columns, check null values, and summarize large tables without writing everything from scratch.
* **Brainstorming the Cost Trade-Off**: I used Claude to bounce ideas around the economics of the problem—specifically how to turn the €380 visit cost and the compounding €600/week penalty into an actual decision threshold.
* **Boilerplate & Visualization Code**: I used Gemini to help draft the Dockerfile, Makefile targets, and Matplotlib chart styling so I could focus my time on understanding the failure modes.

---

## 2. Real Mistakes the AI Made (and How I Caught Them)

### Mistake 1: Gemini crashed on German characters in `gateway_master.csv`
* **What happened**: When I asked Gemini for a script to load `gateway_master.csv`, it gave me a standard `pd.read_csv("data/gateway_master.csv")`. As soon as I ran it, Python crashed with:
  ```text
  UnicodeDecodeError: 'utf-8' codec can't decode byte 0xdf in position 161
  ```
* **Why it was wrong**: Gemini assumed the CSV was UTF-8. It didn't realize the data came from a German system containing special characters like `ß` in *Außenmast* (byte `0xdf`) and `ä` in *Gebäude*.
* **How I fixed it**: I inspected the byte error, realized it was Latin-1 / ISO-8859-1, and wrote a safe loader with encoding fallbacks (`latin1`, `cp1252`, `utf-8`) so the pipeline wouldn't crash on anyone else's machine.

---

### Mistake 2: Claude treated `offline_duration_sec` as "seconds per hour"
* **What happened**: Claude suggested calculating the hourly downtime percentage by dividing:
  $$\text{downtime} = \frac{\text{offline\_duration\_sec}}{3600}$$
  assuming that an hour has 3,600 seconds, so this number would be between 0 and 3,600.
* **Why it was wrong**: When I ran summary statistics on that column, the maximum value was over **726,000 seconds (~8.4 days)**! Claude completely missed the detail in the data dictionary: *"Backhaul offline time counter, seconds"*. It is a **running cumulative counter** that keeps growing as long as the gateway stays disconnected, not an hourly measurement.
* **How I fixed it**: If you compute standard deviations or hourly percentages on a cumulative counter, the math is completely distorted. I rejected Claude's formula and instead measured outage by tracking reporting silence, packet drops, and disconnect severity.

---

### Mistake 3: Both models wanted to jump straight to complex Machine Learning
* **What happened**: Both Gemini and Claude initially pushed me to train complex classifiers (Random Forest, LightGBM) on the telemetry metrics.
* **Why it was wrong**: When I dug into the data myself, I noticed a huge blindspot: 21 broken gateways in February had **zero rows** in recent telemetry because they were completely dead/unpowered. An ML model trained on telemetry rows wouldn't even see these gateways to predict on them! Furthermore, historical data showed that 100% of visits triggered by "unusual statistics" were false alarms anyway.
* **How I fixed it**: I stepped back from blind ML modeling and focused on Data Science fundamentals: defining what a physical failure actually looks like (dead gateways, LoRa packet collapse, power-cycling PSU loops), and optimizing the decision threshold around the real business costs (€380 vs €600).
