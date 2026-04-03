/**
 * GigShield — Supabase Client
 *
 * Initializes the Supabase JS client for authentication and data access.
 * Uses AsyncStorage for persistent session management in React Native.
 *
 * Environment Variables (set in .env or app.config.ts):
 *   EXPO_PUBLIC_SUPABASE_URL   — Your Supabase project URL
 *   EXPO_PUBLIC_SUPABASE_ANON  — Your Supabase anonymous/public key
 *
 * Supabase Phone Auth Setup:
 *   1. Enable Phone Auth in Supabase Dashboard > Authentication > Providers
 *   2. Add Test Phone Numbers under Authentication > Phone Auth:
 *      +919999900001 → 123456
 *      +919999900002 → 123456
 *   3. These test numbers bypass real SMS delivery — ideal for hackathon demos
 */
import 'react-native-url-polyfill/auto';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL || 'https://your-project.supabase.co';
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON || 'your-anon-key';

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    storage: AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false, // Required for React Native
  },
});
