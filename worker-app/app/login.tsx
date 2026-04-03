/**
 * GigShield Worker App — Login / OTP Screen (Supabase Auth)
 *
 * Uses Supabase Auth for Phone OTP authentication.
 * In development: uses Supabase "Test Phone Numbers" feature to bypass
 * real SMS delivery. Configure test numbers in the Supabase dashboard
 * under Authentication > Phone Auth > Test Phone Numbers.
 *
 * Flow:
 *   1. User enters 10-digit Indian phone number
 *   2. supabase.auth.signInWithOtp({ phone: "+91..." }) sends OTP
 *   3. User enters 6-digit OTP
 *   4. supabase.auth.verifyOtp({ phone, token, type: 'sms' }) verifies
 *   5. On success, session is stored and user is routed to home
 *
 * Test Phone Numbers (preconfigured in Supabase dashboard):
 *   +91 9999900001 → OTP: 123456
 *   +91 9999900002 → OTP: 123456
 */
import React, { useState } from 'react';
import {
  View, Text, TextInput, StyleSheet, TouchableOpacity,
  KeyboardAvoidingView, Platform, Alert,
} from 'react-native';
import { router } from 'expo-router';
import * as SecureStore from 'expo-secure-store';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, borderRadius, fonts } from '../lib/theme';
import { supabase } from '../lib/supabase';

export default function LoginScreen() {
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [step, setStep] = useState<'phone' | 'otp'>('phone');
  const [loading, setLoading] = useState(false);

  /**
   * Step 1: Send OTP via Supabase Phone Auth.
   * For test phone numbers configured in the Supabase dashboard,
   * no real SMS is sent — the predefined OTP is accepted directly.
   */
  const sendOtp = async () => {
    if (phone.length !== 10) {
      Alert.alert('Invalid Number', 'Please enter a valid 10-digit phone number.');
      return;
    }

    setLoading(true);
    try {
      const fullPhone = `+91${phone}`;
      const { error } = await supabase.auth.signInWithOtp({
        phone: fullPhone,
      });

      if (error) {
        Alert.alert('OTP Error', error.message);
        setLoading(false);
        return;
      }

      setStep('otp');

      // Hint for test phone numbers
      if (phone.startsWith('99999')) {
        Alert.alert('OTP Sent', 'Test mode: Use OTP 123456');
      } else {
        Alert.alert('OTP Sent', `A 6-digit code has been sent to +91 ${phone}`);
      }
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Failed to send OTP');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Step 2: Verify OTP via Supabase.
   * On success, stores the session access token and navigates to home.
   */
  const verifyOtp = async () => {
    if (otp.length !== 6) {
      Alert.alert('Invalid OTP', 'Please enter the 6-digit OTP.');
      return;
    }

    setLoading(true);
    try {
      const fullPhone = `+91${phone}`;
      const { data, error } = await supabase.auth.verifyOtp({
        phone: fullPhone,
        token: otp,
        type: 'sms',
      });

      if (error) {
        Alert.alert('Verification Failed', error.message);
        setLoading(false);
        return;
      }

      // Store session tokens securely
      if (data?.session) {
        await SecureStore.setItemAsync('auth_token', data.session.access_token);
        await SecureStore.setItemAsync('refresh_token', data.session.refresh_token);
      }
      if (data?.user) {
        await SecureStore.setItemAsync('user_id', data.user.id);
      }
      await SecureStore.setItemAsync('phone', phone);

      // Navigate to home
      router.replace('/');
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Failed to verify OTP');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={styles.content}>
        {/* Logo Area */}
        <View style={styles.logoArea}>
          <View style={styles.logoCircle}>
            <Ionicons name="shield-checkmark" size={64} color={colors.primary} />
          </View>
          <Text style={styles.brandName}>GigShield</Text>
          <Text style={styles.tagline}>
            Income protection. Automatic. Instant.
          </Text>
        </View>

        {/* Input Area */}
        <View style={styles.formArea}>
          {step === 'phone' ? (
            <>
              <Text style={styles.inputLabel}>Phone Number</Text>
              <View style={styles.phoneInputRow}>
                <View style={styles.countryCode}>
                  <Text style={styles.countryCodeText}>+91</Text>
                </View>
                <TextInput
                  style={styles.phoneInput}
                  placeholder="Enter your phone number"
                  placeholderTextColor={colors.textMuted}
                  keyboardType="phone-pad"
                  maxLength={10}
                  value={phone}
                  onChangeText={setPhone}
                />
              </View>

              {/* Test phone hint */}
              <Text style={styles.testHint}>
                Demo: Use 9999900001 with OTP 123456
              </Text>

              <TouchableOpacity
                style={[styles.primaryButton, phone.length !== 10 && styles.buttonDisabled]}
                onPress={sendOtp}
                disabled={phone.length !== 10 || loading}
                activeOpacity={0.8}
              >
                <Text style={styles.buttonText}>
                  {loading ? 'Sending...' : 'Send OTP'}
                </Text>
              </TouchableOpacity>
            </>
          ) : (
            <>
              <Text style={styles.inputLabel}>
                Enter OTP sent to +91 {phone}
              </Text>
              <TextInput
                style={styles.otpInput}
                placeholder="• • • • • •"
                placeholderTextColor={colors.textMuted}
                keyboardType="number-pad"
                maxLength={6}
                value={otp}
                onChangeText={setOtp}
                textAlign="center"
              />
              <TouchableOpacity
                style={[styles.primaryButton, otp.length !== 6 && styles.buttonDisabled]}
                onPress={verifyOtp}
                disabled={otp.length !== 6 || loading}
                activeOpacity={0.8}
              >
                <Text style={styles.buttonText}>
                  {loading ? 'Verifying...' : 'Verify OTP'}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={() => { setStep('phone'); setOtp(''); }}
                style={styles.backButton}
              >
                <Text style={styles.backButtonText}>← Change Number</Text>
              </TouchableOpacity>
            </>
          )}
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            By continuing, you agree to GigShield's Terms of Service
            and Privacy Policy
          </Text>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: {
    flex: 1, justifyContent: 'center', padding: spacing.xl,
  },
  logoArea: { alignItems: 'center', marginBottom: spacing.xxl },
  logoCircle: {
    width: 120, height: 120, borderRadius: 60,
    backgroundColor: 'rgba(0, 201, 177, 0.1)',
    justifyContent: 'center', alignItems: 'center',
    borderWidth: 2, borderColor: 'rgba(0, 201, 177, 0.3)',
    marginBottom: spacing.lg,
  },
  brandName: {
    color: colors.text, fontSize: fonts.sizes.hero,
    fontWeight: '700', letterSpacing: 1,
  },
  tagline: {
    color: colors.textDim, fontSize: fonts.sizes.md,
    marginTop: spacing.sm, fontStyle: 'italic',
  },
  formArea: { marginBottom: spacing.xl },
  inputLabel: {
    color: colors.textDim, fontSize: fonts.sizes.sm,
    marginBottom: spacing.sm,
  },
  phoneInputRow: { flexDirection: 'row', marginBottom: spacing.xs },
  countryCode: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    justifyContent: 'center',
    borderWidth: 1, borderColor: colors.border,
    marginRight: spacing.sm,
  },
  countryCodeText: {
    color: colors.text, fontSize: fonts.sizes.lg, fontWeight: '600',
  },
  phoneInput: {
    flex: 1, backgroundColor: colors.surface,
    borderRadius: borderRadius.md, padding: spacing.md,
    color: colors.text, fontSize: fonts.sizes.lg,
    borderWidth: 1, borderColor: colors.border,
    letterSpacing: 2,
  },
  testHint: {
    color: colors.textMuted, fontSize: fonts.sizes.xs,
    textAlign: 'center', marginBottom: spacing.md,
    fontStyle: 'italic',
  },
  otpInput: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md, padding: spacing.lg,
    color: colors.text, fontSize: fonts.sizes.xxl,
    borderWidth: 1, borderColor: colors.border,
    marginBottom: spacing.md, letterSpacing: 8,
    fontWeight: '700',
  },
  primaryButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
  },
  buttonDisabled: { opacity: 0.5 },
  buttonText: {
    color: '#FFF', fontSize: fonts.sizes.lg, fontWeight: '700',
  },
  backButton: { alignItems: 'center', marginTop: spacing.md },
  backButtonText: { color: colors.primary, fontSize: fonts.sizes.md },
  footer: { alignItems: 'center' },
  footerText: {
    color: colors.textMuted, fontSize: fonts.sizes.xs,
    textAlign: 'center', lineHeight: 18,
  },
});
