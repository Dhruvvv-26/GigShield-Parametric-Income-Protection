/**
 * GigShield Worker App — Payout History Screen
 *
 * Chronological list of all claims/payouts with:
 * - Trigger type icon
 * - Date, tier, amount, status badge
 * - Soft-hold countdown timer
 * - Pull-to-refresh
 */
import React from 'react';
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import * as SecureStore from 'expo-secure-store';
import { getWorkerClaims, getWorkerPayments } from '../lib/api';
import { colors, spacing, borderRadius, fonts } from '../lib/theme';

const STATUS_COLORS: Record<string, string> = {
  completed: colors.success,
  auto_approved: colors.success,
  processing: colors.statusPending,
  soft_hold: colors.warning,
  blocked: colors.error,
  pending: colors.textMuted,
  failed: colors.error,
};

const STATUS_LABELS: Record<string, string> = {
  completed: 'Credited',
  auto_approved: 'Approved',
  processing: 'Processing',
  soft_hold: 'Under Review',
  blocked: 'Blocked',
  pending: 'Pending',
  failed: 'Failed',
};

const EVENT_ICONS: Record<string, string> = {
  aqi: 'cloud',
  heavy_rain: 'rainy',
  extreme_heat: 'sunny',
  cyclone: 'thunderstorm',
  curfew: 'lock-closed',
  flood_alert: 'water',
};

export default function PayoutsScreen() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['payouts'],
    queryFn: async () => {
      const [claimsRes, paymentsRes] = await Promise.allSettled([
        getWorkerClaims(),
        getWorkerPayments(),
      ]);

      const claims = claimsRes.status === 'fulfilled' ? claimsRes.value : [];
      const payments = paymentsRes.status === 'fulfilled' ? paymentsRes.value : [];

      return { claims, payments };
    },
    refetchInterval: 10000,
  });

  const claims = data?.claims || [];
  const payments = data?.payments || [];

  // Merge claims with payment status
  const payoutItems = (claims || []).map((claim: any) => {
    const payment = payments.find((p: any) => p?.claim_id === claim?.claim_id);
    return {
      ...claim,
      paymentStatus: payment?.status || claim?.status,
      razorpayId: payment?.razorpay_payout_id,
      upiMasked: payment?.upi_id_masked,
    };
  });

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={isLoading} onRefresh={refetch}
          tintColor={colors.primary} />
      }
    >
      {/* Summary Header */}
      <View style={styles.summaryCard}>
        <View style={styles.summaryRow}>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryValue}>
              ₹{payoutItems?.reduce((sum: number, p: any) =>
                sum + ((p?.paymentStatus === 'completed' || p?.paymentStatus === 'auto_approved') ? (p?.payout_amount || 0) : 0), 0).toFixed(0)}
            </Text>
            <Text style={styles.summaryLabel}>Total Credited</Text>
          </View>
          <View style={styles.summaryDivider} />
          <View style={styles.summaryItem}>
            <Text style={styles.summaryValue}>{payoutItems.length}</Text>
            <Text style={styles.summaryLabel}>Total Claims</Text>
          </View>
          <View style={styles.summaryDivider} />
          <View style={styles.summaryItem}>
            <Text style={styles.summaryValue}>
              {payoutItems.filter((p: any) =>
                p.paymentStatus === 'completed' || p.paymentStatus === 'auto_approved'
              ).length}
            </Text>
            <Text style={styles.summaryLabel}>Approved</Text>
          </View>
        </View>
      </View>

      {/* Payout List */}
      {isLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Loading payouts...</Text>
        </View>
      ) : payoutItems.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="wallet-outline" size={64} color={colors.textMuted} />
          <Text style={styles.emptyTitle}>No payouts yet</Text>
          <Text style={styles.emptySubtitle}>
            When a disruption is detected in your zone, claims are automatically filed
            and payouts are credited instantly.
          </Text>
        </View>
      ) : (
        payoutItems.map((item: any, idx: number) => (
          <View key={idx} style={styles.payoutCard}>
            <View style={styles.payoutHeader}>
              <View style={[styles.eventIcon, {
                backgroundColor: `${EVENT_ICONS[item.event_type]
                  ? 'rgba(0, 201, 177, 0.12)' : 'rgba(139, 163, 191, 0.12)'}`,
              }]}>
                <Ionicons
                  name={(EVENT_ICONS[item.event_type] || 'alert-circle') as any}
                  size={20}
                  color={colors.primary}
                />
              </View>
              <View style={styles.payoutInfo}>
                <Text style={styles.payoutEventType}>
                  {(item.event_type || 'disruption').replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
                </Text>
                <Text style={styles.payoutDate}>
                  {new Date(item.created_at).toLocaleDateString('en-IN', {
                    day: 'numeric', month: 'short', year: 'numeric',
                    hour: '2-digit', minute: '2-digit',
                  })}
                </Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={styles.payoutAmount}>₹{item?.payout_amount}</Text>
                <View style={[styles.statusBadge, {
                  backgroundColor: `${STATUS_COLORS[item.paymentStatus]}20`,
                }]}>
                  <Text style={[styles.statusText, {
                    color: STATUS_COLORS[item.paymentStatus] || colors.textMuted,
                  }]}>
                    {STATUS_LABELS[item.paymentStatus] || item.paymentStatus}
                  </Text>
                </View>
              </View>
            </View>

            {/* Fraud score indicator */}
            {item.fraud_score !== null && item.fraud_score !== undefined && (
              <View style={styles.fraudRow}>
                <Text style={styles.fraudLabel}>Fraud Score</Text>
                <View style={styles.fraudBarBg}>
                  <View style={[styles.fraudBarFill, {
                    width: `${Math.min(item.fraud_score * 100, 100)}%`,
                    backgroundColor: item.fraud_score < 0.3 ? colors.success
                      : item.fraud_score < 0.65 ? colors.warning : colors.error,
                  }]} />
                </View>
                <Text style={styles.fraudValue}>
                  {(item.fraud_score * 100).toFixed(0)}%
                </Text>
              </View>
            )}

            {/* Soft hold countdown */}
            {item.paymentStatus === 'soft_hold' && (
              <View style={styles.holdBanner}>
                <Ionicons name="time" size={16} color={colors.warning} />
                <Text style={styles.holdText}>
                  50% credited. Balance releases in 2-hour review window.
                </Text>
              </View>
            )}
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  summaryCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between' },
  summaryItem: { flex: 1, alignItems: 'center' },
  summaryValue: {
    color: colors.text, fontSize: fonts.sizes.xl, fontWeight: '700',
  },
  summaryLabel: { color: colors.textMuted, fontSize: fonts.sizes.xs, marginTop: 4 },
  summaryDivider: { width: 1, backgroundColor: colors.border },
  loadingContainer: {
    alignItems: 'center', padding: spacing.xxl, gap: spacing.md,
  },
  loadingText: { color: colors.textMuted, fontSize: fonts.sizes.md },
  emptyState: {
    alignItems: 'center', padding: spacing.xxl, gap: spacing.md,
  },
  emptyTitle: { color: colors.text, fontSize: fonts.sizes.xl, fontWeight: '700' },
  emptySubtitle: {
    color: colors.textDim, fontSize: fonts.sizes.md, textAlign: 'center',
    lineHeight: 22,
  },
  payoutCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  payoutHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  eventIcon: {
    width: 42, height: 42, borderRadius: 21,
    justifyContent: 'center', alignItems: 'center',
  },
  payoutInfo: { flex: 1 },
  payoutEventType: { color: colors.text, fontSize: fonts.sizes.md, fontWeight: '600' },
  payoutDate: { color: colors.textMuted, fontSize: fonts.sizes.xs, marginTop: 2 },
  payoutAmount: { color: colors.text, fontSize: fonts.sizes.lg, fontWeight: '700' },
  statusBadge: {
    paddingHorizontal: 8, paddingVertical: 2,
    borderRadius: borderRadius.pill, marginTop: 4,
  },
  statusText: { fontSize: fonts.sizes.xs, fontWeight: '700' },
  fraudRow: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm,
    marginTop: spacing.sm, paddingTop: spacing.sm,
    borderTopWidth: 1, borderTopColor: colors.border,
  },
  fraudLabel: { color: colors.textMuted, fontSize: fonts.sizes.xs, width: 70 },
  fraudBarBg: {
    flex: 1, height: 6, backgroundColor: colors.border,
    borderRadius: 3, overflow: 'hidden',
  },
  fraudBarFill: { height: '100%', borderRadius: 3 },
  fraudValue: { color: colors.textDim, fontSize: fonts.sizes.xs, width: 30, textAlign: 'right' },
  holdBanner: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm,
    marginTop: spacing.sm, paddingTop: spacing.sm,
    borderTopWidth: 1, borderTopColor: colors.border,
  },
  holdText: { color: colors.warning, fontSize: fonts.sizes.xs, flex: 1 },
});
