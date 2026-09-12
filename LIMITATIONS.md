# System Limitations & What I Would Fix Next

Here is an honest look at where my current system falls short, where it might give the wrong answer, and what I would build if I had another two weeks to work on it.

---

## 1. Where the System Falls Short Right Now

* **Brand New Gateways (Cold Start)**: The model relies on having 28 days of past data to know what "normal" looks like for each gateway. If a gateway was installed just a week or two ago, it doesn't have enough history yet. Because of that, the system might miss an early defect or mislabel normal setup activity as an outage.

* **Treating All Gateways the Same**: Right now, the ranking treats every gateway as equally important. But in reality, some gateways connect to 40 meters while others connect to over 900 meters. If a 900-meter gateway goes down, that causes way more unread customer bills than a small one. Right now, the system doesn't factor in customer size when picking the top 15.

* **Cell Tower Outages vs. Broken Gateways**: If a local mobile tower (like Vodafone or O2) has an outage, several nearby gateways might lose their connection at the exact same time. The equipment itself isn't broken—it's just a cellular network issue. Right now, the system might still flag them and waste a €380 visit sending a technician to a site where nothing is actually wrong.

* **Flagging Gateways Right After They Were Fixed**: If a technician visits a site on a Wednesday and replaces a bad power supply, the past 7 days of data will still show all the downtime from Monday and Tuesday. The system doesn't know a technician just fixed it, so it might accidentally flag the same gateway again the following Monday.

---

## 2. What Another Two Weeks Would Fix

If I had another two weeks to keep improving this project, here is what I would focus on:

* **Use Group Averages for New Gateways**: Instead of waiting 28 days for a brand-new gateway to build its own history, I would compare it to other gateways of the same hardware model and location type (like basements or outdoor poles) until it has enough of its own data.

* **Prioritize by Customer Size**: I would update the ranking formula to multiply the failure risk by the number of installed meters (`n_meters_installed`). That way, the 15 weekly visits are used where they protect the most customer bills.

* **Group Together Local Network Drops**: I would write a check to see if multiple gateways in the same region and on the same cellular network go offline together. If three or four drop at the same moment, the system should flag it as a mobile carrier outage instead of rolling a truck.

* **Add a 14-Day Cooldown After Repairs**: I would link the prediction pipeline directly to the completed visit records (`field_visits.csv`). Once a repair is marked as completed, that gateway would get a temporary 2-week cooldown so we don't accidentally send someone out twice for the same resolved problem.
