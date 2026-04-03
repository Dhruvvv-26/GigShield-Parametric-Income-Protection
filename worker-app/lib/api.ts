/**
 * GigShield — API Client Configuration
 * Configured for local development via Expo Go.
 */
import axios from 'axios';

// When running on physical device, replace with your machine's LAN IP
// e.g., 'http://192.168.1.100'
const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://10.0.2.2';

export const api = {
  worker:       axios.create({ baseURL: `${BASE_URL}:8001`, timeout: 10000 }),
  policy:       axios.create({ baseURL: `${BASE_URL}:8002`, timeout: 10000 }),
  trigger:      axios.create({ baseURL: `${BASE_URL}:8003`, timeout: 10000 }),
  claims:       axios.create({ baseURL: `${BASE_URL}:8004`, timeout: 10000 }),
  payments:     axios.create({ baseURL: `${BASE_URL}:8005`, timeout: 10000 }),
  notifications: axios.create({ baseURL: `${BASE_URL}:8006`, timeout: 10000 }),
};

// Add auth interceptor (JWT from SecureStore)
export const setAuthToken = (token: string) => {
  Object.values(api).forEach((instance) => {
    instance.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  });
};

export default api;
