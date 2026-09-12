# AI Usage & Challenges Faced

During this challenge, I used **Gemini** and **Claude** as pair-programming assistants. This document explains what I used them for, where they were helpful, and the real mistakes they made that I had to catch and fix.

---

## 1. What I Used AI For

* **Quick Data Checks**: The dataset is quite large, with 1.4 million rows split across eight monthly Parquet folders. I used Gemini and Claude to quickly write short Python scripts to check columns, look for missing values, and summarize the data so I didn't have to write all the basic code from scratch.
* **Working Out the Costs**: I used Claude as a sounding board to figure out the financial side of the project. It helped me figure out how to balance the €380 repair visit fee against the €600 weekly delay penalty to find the right time to take action.
* **Writing Setup and Chart Code**: I used Gemini to help generate basic setup files (like the Dockerfile and Makefile) and style the Matplotlib charts. Passing off these routine coding tasks let me spend more time focusing on why the equipment was actually failing.

---

## 2. Real AI Mistakes & How I Fixed Them

### Mistake 1: Gemini crashed on German characters
* **What happened**: When I asked Gemini for a script to load `gateway_master.csv`, it gave me a standard `pd.read_csv()` command. Running it immediately crashed Python with a `UnicodeDecodeError`.
* **Why it was wrong**: Gemini assumed the file used standard UTF-8 encoding. It didn't account for special German characters in the data, like `ß` in *Außenmast* or `ä` in *Gebäude*.
* **How I fixed it**: I checked the error message, recognized the Latin-1 / ISO-8859-1 encoding, and updated the script with fallback options (`latin1`, `cp1252`, `utf-8`) so it runs smoothly on any machine.

---

### Mistake 2: Claude misread the downtime metric
* **What happened**: Claude suggested calculating hourly downtime percentage by dividing `offline_duration_sec` by 3,600, assuming it capped out at 3,600 seconds per hour.
* **Why it was wrong**: Checking the actual summary statistics showed a max value over 726,000 seconds (~8.4 days). Claude missed a key detail in the data dictionary: it is a running cumulative counter, not an hourly measurement.
* **How I fixed it**: Treating a cumulative counter as an hourly metric ruins all statistical calculations. I scrapped Claude's formula and instead tracked actual outages using missing reports, dropped packets, and disconnect events.

---

### Mistake 3: Both models rushed straight to Machine Learning
* **What happened**: Gemini and Claude both pushed me to immediately build complex Machine Learning models (like Random Forest or LightGBM) on the telemetry data.
* **Why it was wrong**: They overlooked that 21 broken gateways had zero telemetry rows in recent weeks because they were completely dead, meaning an ML model wouldn't even see them to predict on them! Furthermore, 100% of historical visits for "unusual statistics" were false alarms anyway.
* **How I fixed it**: I set aside the complex ML models and focused on basic Data Science logic: defining what real physical failures look like (dead gateways, packet loss, repeated power reboots) and matching those rules to the actual repair costs (€380 vs €600).
