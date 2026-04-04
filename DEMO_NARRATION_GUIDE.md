# 🎬 KavachAI: 60-Second Demo Narration Guide

This guide is designed to help you record a flawless, 5-star video for the Guidewire DEVTrails judges. 

### 💡 Setup Checklist Before Recording:
1.  **Split Screen**: Terminal on the **Left**, Phone/Mirror on the **Right**.
2.  **Clean State**: Run `python3 scripts/god_mode_demo.py seed` before starting.
3.  **Expo Go**: Open the KavachAI app and ensure it's connected to your local API.
4.  **Quiet Mode**: Turn off Slack/WhatsApp notifications on your desktop.

---

## ⏱️ The 60-Second Narration Sequence

| Time | Action (Terminal/App) | Narration Script (Suggested) |
| :--- | :--- | :--- |
| **T+00s** | **Terminal:** `python3 scripts/god_mode_demo.py trigger --scenario clean` | *"We're starting with a clean scenario. KavachAI just detected a severe AQI spike in Rohini, Delhi via our CPCB sensors."* |
| **T+02s** | **App:** Show Home Screen | *"On the rider app, Arjun sees 'Coverage Active'. The live AQI is dangerously high at 450, and the temperature is 38 degrees."* |
| **T+10s** | **App:** Tap 'My Policy' | *"Arjun is protected for just ₹67 a week. Our parametric engine watches for AQI, Rain, Heat, and even City Curfews."* |
| **T+18s** | **Terminal:** Watch 'Claim Created' logs | *"Back in the logs, you see the claim was auto-approved. A low fraud score of 0.12 means zero manual intervention was needed."* |
| **T+25s** | **App:** Tap 'Payouts' Tab | *"Instantly, Arjun sees a ₹350 credit in his history. No paperwork, no investigators, just instant relief."* |
| **T+28s** | **Phone:** Wait for FCM Push | *"And there's the Firebase push notification—Arjun knows his rent is safe before he even finishes his shift."* |
| **T+32s** | **Terminal:** `python3 scripts/god_mode_demo.py trigger --scenario spoofed` | *"Now, let's try to break it. A bad actor in Mumbai is spoofing their GPS to trick our Delhi sensors."* |
| **T+45s** | **Terminal:** Watch for `ZONE_MISMATCH` | *"Our Layer 5 defense catches it immediately. A 'ZONE_MISMATCH' flag was raised, hard-blocking the payout. Fraud score: 0.91."* |
| **T+50s** | **Terminal:** `curl http://localhost:8006/api/v1/premium/calculate ...` | *"We don't hardcode prices. Here is our live ML engine weighing AQI risk and seasonality to price Arjun's specific zone."* |
| **T+58s** | **Terminal:** `curl http://localhost:8005/api/v1/payments/summary` | *"Finally, our actuarial dashboard tracks real-time loss ratios, ensuring KavachAI stays solvent and ready for the next crisis."* |
| **T+60s** | **STOP RECORDING** | *"ML pricing, parametric triggers, and fraud-proof infrastructure. That is KavachAI."* |

---

## 🛠️ Rapid-Fire Commands (Copy/Paste)

### 1. Happy Path ( Delhi Clean)
```bash
python3 scripts/god_mode_demo.py trigger --scenario clean
```

### 2. Hostile Path (Mumbai Spoof)
```bash
python3 scripts/god_mode_demo.py trigger --scenario spoofed
```

### 3. ML Premium Breakdown (SHAP)
```bash
curl -s -X POST http://localhost:8006/api/v1/premium/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "city":"delhi_ncr",
    "vehicle_type":"bicycle",
    "coverage_tier":"standard",
    "month":7,
    "historical_aqi_events_12m":45,
    "historical_rain_events_12m":28,
    "disruption_history_90d":15,
    "declared_daily_trips":30,
    "avg_daily_earnings":1100.0,
    "monthly_work_days":22
  }' | python3 -m json.tool
```

### 4. Actuarial Live Summary
```bash
curl -s http://localhost:8005/api/v1/payments/summary | python3 -m json.tool
```

---

> **Tip for a 5-Star Video:** Keep your voice energetic but professional. Judges love seeing the Redpanda or Redis logs scrolling in the background—it proves the tech stack is real! 🚀
