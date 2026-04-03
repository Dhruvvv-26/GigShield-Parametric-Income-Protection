const CLAIMS_URL = "https://fifty-baboons-trade.loca.lt";
const POLICY_URL = "https://solid-hounds-stand.loca.lt";
export const WORKER_ID = "fffafc0b-7c28-42e8-ae34-020f51acf148";

export const SERVICES = {
  claims: CLAIMS_URL,
  policy: POLICY_URL,
  payment: `http://172.20.10.2:8005`,
  trigger: `http://172.20.10.2:8003`,
  worker: `http://172.20.10.2:8001`,
  ml: `http://172.20.10.2:8006`,
};

const HEADERS = {
  "bypass-tunnel-reminder": "true",
  "Content-Type": "application/json",
};

export const getWorkerClaims = async () => {
  console.log("📡 [PROD] Fetching Claims...");
  try {
    const response = await fetch(`${CLAIMS_URL}/api/v1/claims/worker/${WORKER_ID}`, { headers: HEADERS });
    const data = await response.json();
    return data.claims || [];
  } catch (e) {
    console.error("❌ Claims Error:", e);
    return [];
  }
};

export const getActivePolicy = async () => {
  console.log("📡 [PROD] Fetching Policy...");
  try {
    const response = await fetch(`${POLICY_URL}/api/v1/policies/active/${WORKER_ID}`, { headers: HEADERS });
    return await response.json();
  } catch (e) {
    console.error("❌ Policy Error:", e);
    return null;
  }
};

// Add your other production stubs below if needed
export const getZoneWeather = async () => { return null; };
export const getWorkerPayments = async () => { return []; };
export const getWorkerProfile = async () => { return null; };
export const sendSensorPing = async () => { return null; };
