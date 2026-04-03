/**
 * GigShield Worker App — Home / Coverage Status Screen
 *
 * Displays:
 * - Active policy card (tier, premium, renewal)
 * - Real-time disruption status widget (AQI/rain/heat)
 * - Active trigger banner with pulse animation
 * - Quick stats: payouts this month, coverage days
 */
import React, { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
  Animated, Dimensions, Modal, TouchableOpacity, Alert
} from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import * as SecureStore from 'expo-secure-store';
import api from '../lib/api';
import { colors, spacing, borderRadius, fonts, shadows } from '../lib/theme';
import GPSCamera from '../components/GPSCamera';

const { width } = Dimensions.get('window');

// Demo worker ID — in production, this comes from auth
const DEMO_WORKER_ID = '00000000-0000-0000-0000-000000000001';

const EVENT_ICONS: Record<string, string> = {
  aqi: 'cloud',
  heavy_rain: 'rainy',
  extreme_heat: 'sunny',
  cyclone: 'thunderstorm',
  curfew: 'lock-closed',
  flood_alert: 'water',
};

const EVENT_COLORS: Record<string, string> = {
  aqi: '#FF7043',
  heavy_rain: '#42A5F5',
  extreme_heat: '#FFA726',
  cyclone: '#AB47BC',
  curfew: '#78909C',
  flood_alert: '#26C6DA',
};

export default function HomeScreen() {
  const [workerId, setWorkerId] = useState<string>(DEMO_WORKER_ID);
  const [showCamera, setShowCamera] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const pulseAnim = new Animated.Value(1);

  useEffect(() => {
    (async () => {
      const stored = await SecureStore.getItemAsync('worker_id');
      if (stored) setWorkerId(stored);
    })();
  }, []);

  // Active trigger pulse animation
  useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.05,
          duration: 1000,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        }),
      ])
    );
    animation.start();
    return () => animation.stop();
  }, []);

  // Fetch notifications (latest events)
  const { data: notifications, refetch, isLoading } = useQuery({
    queryKey: ['notifications', workerId],
    queryFn: async () => {
      const res = await api.notifications.get(
        `/api/v1/notifications/worker/${workerId}`
      );
      return res.data;
    },
    refetchInterval: 5000,
  });

  // Fetch payment summary
  const { data: summary } = useQuery({
    queryKey: ['paymentSummary'],
    queryFn: async () => {
      const res = await api.payments.get('/api/v1/payments/summary');
      return res.data;
    },
    refetchInterval: 15000,
  });

  // Fetch trigger status
  const { data: triggerStatus } = useQuery({
    queryKey: ['triggerStatus'],
    queryFn: async () => {
      const res = await api.trigger.get('/api/v1/trigger/status');
      return res.data;
    },
    refetchInterval: 10000,
  });

  const activeTriggers = triggerStatus?.active_trigger_count || 0;
  const latestNotifications = notifications?.notifications?.slice(0, 3) || [];

  const handleClaimPayout = () => {
    setShowCamera(true);
  };

  // Vuln D: Exponential backoff retry for poor 4G networks during storms
  const retryWithBackoff = async <T,>(
    fn: () => Promise<T>,
    maxRetries: number = 3,
    baseDelayMs: number = 1000,
  ): Promise<T> => {
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await fn();
      } catch (err: any) {
        const status = err.response?.status;
        // Don't retry 4xx client errors — they are deterministic rejections
        if (status && status >= 400 && status < 500) {
          throw err;
        }
        if (attempt === maxRetries) {
          throw err;
        }
        const delay = baseDelayMs * Math.pow(2, attempt); // 1s, 2s, 4s
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    throw new Error("Retry exhausted"); // Unreachable, but satisfies TS
  };

  const onCameraCapture = async (cameraPayload: any) => {
    setShowCamera(false);
    setIsSubmitting(true);
    
    try {
      // Mocking hardware sensors for demo purposes
      const sensorData = {
        active_zone_id: triggerStatus?.zone_id || "demo-zone-id", // Included for Bouncer check
        accelerometer_rms: 3.5, // moving
        gyroscope_yaw_rate: 0.2, // standard device handling
        is_mock_location: false,
        gps_pings: [
          { lat: cameraPayload.gps_lat, lng: cameraPayload.gps_lng, accuracy_m: 5, timestamp: Date.now() },
        ],
        // Adding the Layer 5 Zero-Trust biometric payload
        photo_base64: cameraPayload.photo_base64,
        camera_gps_lat: cameraPayload.gps_lat,
        camera_gps_lng: cameraPayload.gps_lng,
        capture_timestamp_ms: cameraPayload.capture_timestamp_ms,
      };

      // Vuln D: Retry with exponential backoff (1s → 2s → 4s) for network failures
      const res = await retryWithBackoff(
        () => api.claims.post(`/api/v1/claims/sensor_data/${workerId}`, sensorData)
      );
      
      if (res.status === 202) {
        Alert.alert(
          "Liveness Verified & Claim Submitted", 
          "Your live selfie, GPS coordinates, and hardware sensors have been securely verified."
        );
      }
    } catch (err: any) {
      // Handle the 403 ZONE_MISMATCH_REJECTED or STALE capture
      const msg = err.response?.data?.detail || "Failed to verify liveness and submit claim.";
      Alert.alert("Verification Failed", msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.contentContainer}
      refreshControl={
        <RefreshControl refreshing={isLoading} onRefresh={refetch}
          tintColor={colors.primary} />
      }
    >
      {/* Active Trigger Banner */}
      {activeTriggers > 0 && (
        <Animated.View
          style={[styles.triggerBanner, { transform: [{ scale: pulseAnim }] }]}
        >
          <View style={styles.triggerBannerContent}>
            <Ionicons name="warning" size={24} color="#FFF" />
            <View style={styles.triggerBannerText}>
              <Text style={styles.triggerBannerTitle}>
                ⚡ Active Trigger Detected
              </Text>
              <Text style={styles.triggerBannerSubtitle}>
                {activeTriggers} disruption event(s) in your zone
              </Text>
            </View>
          </View>
          <TouchableOpacity 
            style={styles.claimButton}
            onPress={handleClaimPayout}
            disabled={isSubmitting}
          >
            <Text style={styles.claimButtonText}>
              {isSubmitting ? "Verifying..." : "Claim Payout (Requires Liveness Check)"}
            </Text>
          </TouchableOpacity>
        </Animated.View>
      )}

      <Modal visible={showCamera} animationType="slide">
        <GPSCamera 
          onCapture={onCameraCapture} 
          onCancel={() => setShowCamera(false)} 
        />
      </Modal>

      {/* Coverage Status Card */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={styles.shieldIcon}>
            <Ionicons name="shield-checkmark" size={28} color={colors.primary} />
          </View>
          <View>
            <Text style={styles.cardTitle}>Coverage Active</Text>
            <Text style={styles.cardSubtitle}>Standard Tier</Text>
          </View>
          <View style={styles.statusBadge}>
            <View style={styles.activeDot} />
            <Text style={styles.statusText}>ACTIVE</Text>
          </View>
        </View>

        <View style={styles.coverageDetails}>
          <View style={styles.detailItem}>
            <Text style={styles.detailLabel}>Weekly Premium</Text>
            <Text style={styles.detailValue}>₹67.60</Text>
          </View>
          <View style={styles.divider} />
          <View style={styles.detailItem}>
            <Text style={styles.detailLabel}>Max Payout</Text>
            <Text style={styles.detailValue}>₹600/event</Text>
          </View>
          <View style={styles.divider} />
          <View style={styles.detailItem}>
            <Text style={styles.detailLabel}>Renewal</Text>
            <Text style={styles.detailValue}>Apr 7</Text>
          </View>
        </View>
      </View>

      {/* Quick Stats Row */}
      <View style={styles.statsRow}>
        <View style={[styles.statCard, { borderLeftColor: colors.success }]}>
          <Ionicons name="cash" size={20} color={colors.success} />
          <Text style={styles.statValue}>
            ₹{summary?.total_payouts_this_week?.toFixed(0) || '0'}
          </Text>
          <Text style={styles.statLabel}>Payouts This Week</Text>
        </View>
        <View style={[styles.statCard, { borderLeftColor: colors.primary }]}>
          <Ionicons name="calendar" size={20} color={colors.primary} />
          <Text style={styles.statValue}>
            {summary?.active_policies || 0}
          </Text>
          <Text style={styles.statLabel}>Active Policies</Text>
        </View>
        <View style={[styles.statCard, { borderLeftColor: colors.warning }]}>
          <Ionicons name="analytics" size={20} color={colors.warning} />
          <Text style={styles.statValue}>
            {summary?.loss_ratio_percent?.toFixed(0) || '0'}%
          </Text>
          <Text style={styles.statLabel}>Loss Ratio</Text>
        </View>
      </View>

      {/* Disruption Monitor */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Disruption Monitor</Text>
        <Text style={styles.sectionSubtitle}>Your Zone: Delhi Rohini</Text>
      </View>

      <View style={styles.disruptionGrid}>
        {[
          { type: 'aqi', label: 'Air Quality', value: 'AQI 280', status: 'Moderate' },
          { type: 'heavy_rain', label: 'Rainfall', value: '12mm/hr', status: 'Light' },
          { type: 'extreme_heat', label: 'Temperature', value: '38°C', status: 'Normal' },
          { type: 'cyclone', label: 'Wind Speed', value: '15 km/h', status: 'Calm' },
        ].map((item) => (
          <View key={item.type} style={styles.disruptionCard}>
            <Ionicons
              name={EVENT_ICONS[item.type] as any}
              size={22}
              color={EVENT_COLORS[item.type]}
            />
            <Text style={styles.disruptionLabel}>{item.label}</Text>
            <Text style={styles.disruptionValue}>{item.value}</Text>
            <Text style={styles.disruptionStatus}>{item.status}</Text>
          </View>
        ))}
      </View>

      {/* Recent Activity */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Recent Activity</Text>
      </View>

      {latestNotifications.length > 0 ? (
        latestNotifications.map((notif: any, idx: number) => (
          <View key={idx} style={styles.activityCard}>
            <View style={styles.activityIcon}>
              <Ionicons
                name={EVENT_ICONS[notif.event_type] || 'notifications'}
                size={20}
                color={colors.primary}
              />
            </View>
            <View style={styles.activityContent}>
              <Text style={styles.activityTitle}>{notif.title}</Text>
              <Text style={styles.activityBody}>{notif.body}</Text>
              <Text style={styles.activityTime}>
                {new Date(notif.sent_at).toLocaleString('en-IN')}
              </Text>
            </View>
          </View>
        ))
      ) : (
        <View style={styles.emptyState}>
          <Ionicons name="shield" size={48} color={colors.textMuted} />
          <Text style={styles.emptyText}>
            No disruption events yet. You're protected!
          </Text>
        </View>
      )}

      {/* Brand Footer */}
      <View style={styles.footer}>
        <Text style={styles.footerText}>
          Income protection. Automatic. Instant.
        </Text>
        <Text style={styles.footerVersion}>GigShield v3.0 — Phase 3 (ML-Powered)</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  contentContainer: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  triggerBanner: {
    backgroundColor: '#C62828',
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    ...shadows.glow,
    shadowColor: '#FF5252',
  },
  triggerBannerContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  triggerBannerText: {
    flex: 1,
  },
  triggerBannerTitle: {
    color: '#FFF',
    fontSize: fonts.sizes.lg,
    fontWeight: '700',
  },
  triggerBannerSubtitle: {
    color: 'rgba(255,255,255,0.8)',
    fontSize: fonts.sizes.sm,
    marginTop: 2,
  },
  claimButton: {
    backgroundColor: '#FFF',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.sm,
    marginTop: spacing.md,
    alignItems: 'center',
  },
  claimButtonText: {
    color: '#C62828',
    fontSize: fonts.sizes.sm,
    fontWeight: '700',
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    ...shadows.card,
    marginBottom: spacing.md,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  shieldIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: 'rgba(0, 201, 177, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  cardTitle: {
    color: colors.text,
    fontSize: fonts.sizes.xl,
    fontWeight: '700',
  },
  cardSubtitle: {
    color: colors.textDim,
    fontSize: fonts.sizes.sm,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: 'auto',
    backgroundColor: 'rgba(0, 230, 118, 0.15)',
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: borderRadius.pill,
    gap: 4,
  },
  activeDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.success,
  },
  statusText: {
    color: colors.success,
    fontSize: fonts.sizes.xs,
    fontWeight: '700',
    letterSpacing: 1,
  },
  coverageDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  detailItem: {
    flex: 1,
    alignItems: 'center',
  },
  detailLabel: {
    color: colors.textMuted,
    fontSize: fonts.sizes.xs,
    marginBottom: 4,
  },
  detailValue: {
    color: colors.text,
    fontSize: fonts.sizes.md,
    fontWeight: '700',
  },
  divider: {
    width: 1,
    backgroundColor: colors.border,
  },
  statsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  statCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    borderLeftWidth: 3,
    alignItems: 'center',
    gap: 4,
  },
  statValue: {
    color: colors.text,
    fontSize: fonts.sizes.lg,
    fontWeight: '700',
  },
  statLabel: {
    color: colors.textMuted,
    fontSize: fonts.sizes.xs,
    textAlign: 'center',
  },
  sectionHeader: {
    marginBottom: spacing.md,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: fonts.sizes.lg,
    fontWeight: '700',
  },
  sectionSubtitle: {
    color: colors.textDim,
    fontSize: fonts.sizes.sm,
    marginTop: 2,
  },
  disruptionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  disruptionCard: {
    width: (width - spacing.md * 2 - spacing.sm) / 2 - 1,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    alignItems: 'center',
    gap: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  disruptionLabel: {
    color: colors.textDim,
    fontSize: fonts.sizes.xs,
    marginTop: 4,
  },
  disruptionValue: {
    color: colors.text,
    fontSize: fonts.sizes.md,
    fontWeight: '700',
  },
  disruptionStatus: {
    color: colors.textMuted,
    fontSize: fonts.sizes.xs,
  },
  activityCard: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  activityIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(0, 201, 177, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  activityContent: {
    flex: 1,
  },
  activityTitle: {
    color: colors.text,
    fontSize: fonts.sizes.md,
    fontWeight: '600',
  },
  activityBody: {
    color: colors.textDim,
    fontSize: fonts.sizes.sm,
    marginTop: 2,
  },
  activityTime: {
    color: colors.textMuted,
    fontSize: fonts.sizes.xs,
    marginTop: 4,
  },
  emptyState: {
    alignItems: 'center',
    padding: spacing.xl,
    gap: spacing.md,
  },
  emptyText: {
    color: colors.textMuted,
    fontSize: fonts.sizes.md,
    textAlign: 'center',
  },
  footer: {
    alignItems: 'center',
    paddingTop: spacing.xl,
    gap: 4,
  },
  footerText: {
    color: colors.textDim,
    fontSize: fonts.sizes.sm,
    fontStyle: 'italic',
  },
  footerVersion: {
    color: colors.textMuted,
    fontSize: fonts.sizes.xs,
  },
});
