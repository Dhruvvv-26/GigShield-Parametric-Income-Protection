/**
 * KavachAI Worker App — My Policy Screen
 *
 * Displays:
 * - Coverage tier details (Basic/Standard/Premium)
 * - Weekly premium breakdown with SHAP-style factors
 * - Policy pause/cancel options
 * - Renew button
 */
import React from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, borderRadius, fonts } from '../lib/theme';

const TIER_DETAILS: Record<string, any> = {
  basic: {
    name: 'Basic',
    color: '#4CAF50',
    maxPayout: 300,
    triggers: ['AQI', 'Heavy Rain'],
    weeklyPremium: 35,
  },
  standard: {
    name: 'Standard',
    color: colors.primary,
    maxPayout: 600,
    triggers: ['AQI', 'Heavy Rain', 'Extreme Heat', 'Cyclone', 'Curfew'],
    weeklyPremium: 67.60,
  },
  premium: {
    name: 'Premium',
    color: '#FFD700',
    maxPayout: 1000,
    triggers: ['All 5 Triggers', '3× daily coverage', 'Priority claims'],
    weeklyPremium: 125,
  },
};

export default function PolicyScreen() {
  const currentTier = 'standard';
  const tier = TIER_DETAILS[currentTier];

  const handlePause = () => {
    Alert.alert(
      'Pause Policy',
      'Your coverage will be paused. You can resume anytime.',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Pause', style: 'destructive' },
      ],
    );
  };

  const handleRenew = () => {
    Alert.alert(
      'Renew Policy',
      `Renew your ${tier.name} tier policy for ₹${tier.weeklyPremium}/week?`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Renew via UPI', style: 'default' },
      ],
    );
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Policy Card */}
      <View style={[styles.policyCard, { borderTopColor: tier.color }]}>
        <View style={styles.policyHeader}>
          <View style={[styles.tierBadge, { backgroundColor: `${tier.color}20` }]}>
            <Ionicons name="shield-checkmark" size={32} color={tier.color} />
          </View>
          <View style={styles.policyInfo}>
            <Text style={styles.tierName}>{tier.name} Tier</Text>
            <Text style={styles.policyStatus}>Active until Apr 7, 2026</Text>
          </View>
          <View style={[styles.activeBadge, { borderColor: colors.success }]}>
            <View style={styles.activeDot} />
            <Text style={styles.activeText}>ACTIVE</Text>
          </View>
        </View>

        {/* Coverage Details */}
        <View style={styles.coverageGrid}>
          <View style={styles.coverageItem}>
            <Text style={styles.coverageLabel}>Max Payout</Text>
            <Text style={styles.coverageValue}>₹{tier.maxPayout}/event</Text>
          </View>
          <View style={styles.coverageItem}>
            <Text style={styles.coverageLabel}>Weekly Premium</Text>
            <Text style={styles.coverageValue}>₹{tier.weeklyPremium}</Text>
          </View>
          <View style={styles.coverageItem}>
            <Text style={styles.coverageLabel}>Zone</Text>
            <Text style={styles.coverageValue}>Delhi Rohini</Text>
          </View>
          <View style={styles.coverageItem}>
            <Text style={styles.coverageLabel}>Payout Mode</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 }}>
              <View style={{
                backgroundColor: 'rgba(0, 201, 177, 0.15)',
                paddingHorizontal: 8,
                paddingVertical: 2,
                borderRadius: 12,
              }}>
                <Text style={{ color: colors.primary, fontSize: 11, fontWeight: '700' }}>
                  LUMP SUM
                </Text>
              </View>
            </View>
          </View>
        </View>

        {/* Covered Triggers */}
        <View style={styles.triggersSection}>
          <Text style={styles.sectionTitle}>Covered Triggers</Text>
          <View style={styles.triggerList}>
            {tier.triggers.map((trigger: string, idx: number) => (
              <View key={idx} style={styles.triggerItem}>
                <Ionicons name="checkmark-circle" size={16} color={colors.success} />
                <Text style={styles.triggerText}>{trigger}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Force Majeure Exclusions */}
        <View style={[styles.triggersSection, { marginTop: spacing.lg }]}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.sm }}>
            <Ionicons name="alert-circle-outline" size={18} color={colors.warning} />
            <Text style={[styles.sectionTitle, { marginBottom: 0 }]}>Force Majeure Exclusions</Text>
          </View>
          <Text style={{ color: colors.textMuted, fontSize: 12, marginBottom: spacing.sm }}>
            Events excluded from parametric coverage per IRDAI guidelines:
          </Text>
          <View style={styles.triggerList}>
            {[
              { code: 'ACT_OF_WAR', label: 'Act of War' },
              { code: 'PANDEMIC_DECLARED', label: 'WHO Pandemic Declaration' },
              { code: 'TERRORISM', label: 'Terrorist Incident' },
              { code: 'NUCLEAR_EVENT', label: 'Nuclear / Radiological Event' },
              { code: 'GOV_LOCKDOWN_72H+', label: 'Extended Lockdown (>72h)' },
            ].map((excl, idx) => (
              <View key={idx} style={styles.triggerItem}>
                <Ionicons name="close-circle" size={16} color={colors.error} />
                <Text style={styles.triggerText}>{excl.label}</Text>
              </View>
            ))}
          </View>
          <View style={{
            backgroundColor: 'rgba(255, 193, 7, 0.08)',
            borderWidth: 1,
            borderColor: 'rgba(255, 193, 7, 0.2)',
            borderRadius: 8,
            padding: 10,
            marginTop: spacing.sm,
          }}>
            <Text style={{ color: colors.textDim, fontSize: 11, lineHeight: 16 }}>
              ℹ️ Short-term curfews (≤72h) and weather disruptions remain covered.
              Exclusions only apply for officially designated events.
            </Text>
          </View>
        </View>
      </View>

      {/* Premium Breakdown — SHAP-style */}
      <View style={styles.breakdownCard}>
        <Text style={styles.sectionTitle}>Premium Breakdown</Text>
        <Text style={styles.breakdownSubtitle}>
          Rule-based calculation with SHAP-style transparency
        </Text>

        <View style={styles.breakdownRows}>
          {[
            { label: 'Base Rate (Delhi NCR)', value: '₹25.00', factor: '1.0×' },
            { label: 'Zone Risk (Rohini)', value: '₹40.00', factor: '2.6×', highlight: true },
            { label: 'Seasonal Adjustment', value: '+₹5.10', factor: '1.2×' },
            { label: 'Platform (Blinkit)', value: '+₹2.50', factor: '1.1×' },
            { label: 'Tier Uplift', value: '+₹0.00', factor: '1.0×' },
          ].map((row, idx) => (
            <View key={idx} style={[styles.breakdownRow,
              row.highlight && styles.breakdownRowHighlight]}>
              <View style={styles.breakdownLeft}>
                <Text style={styles.breakdownLabel}>{row.label}</Text>
                <Text style={styles.breakdownFactor}>{row.factor}</Text>
              </View>
              <Text style={[styles.breakdownValue,
                row.highlight && { color: colors.primary }]}>
                {row.value}
              </Text>
            </View>
          ))}

          <View style={styles.breakdownTotal}>
            <Text style={styles.totalLabel}>Weekly Premium</Text>
            <Text style={styles.totalValue}>₹67.60</Text>
          </View>
        </View>
      </View>

      {/* Tier Comparison */}
      <View style={styles.tierCompare}>
        <Text style={styles.sectionTitle}>All Tiers</Text>
        {Object.entries(TIER_DETAILS).map(([key, t]) => (
          <View key={key} style={[styles.tierRow,
            key === currentTier && styles.tierRowActive]}>
            <View style={[styles.tierDot, { backgroundColor: t.color }]} />
            <View style={styles.tierRowInfo}>
              <Text style={styles.tierRowName}>{t.name}</Text>
              <Text style={styles.tierRowDetail}>
                ₹{t.weeklyPremium}/wk · Max ₹{t.maxPayout}/event
              </Text>
            </View>
            {key === currentTier && (
              <View style={styles.currentBadge}>
                <Text style={styles.currentBadgeText}>CURRENT</Text>
              </View>
            )}
          </View>
        ))}
      </View>

      {/* Actions */}
      <View style={styles.actions}>
        <TouchableOpacity
          style={styles.renewButton}
          onPress={handleRenew} activeOpacity={0.8}
        >
          <Ionicons name="refresh" size={20} color="#FFF" />
          <Text style={styles.renewButtonText}>Renew Policy</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.pauseButton}
          onPress={handlePause} activeOpacity={0.8}
        >
          <Ionicons name="pause-circle" size={20} color={colors.warning} />
          <Text style={styles.pauseButtonText}>Pause Coverage</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  policyCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    borderTopWidth: 3,
    borderWidth: 1,
    borderColor: colors.border,
  },
  policyHeader: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  tierBadge: {
    width: 56, height: 56, borderRadius: 28,
    justifyContent: 'center', alignItems: 'center',
  },
  policyInfo: { flex: 1 },
  tierName: { color: colors.text, fontSize: fonts.sizes.xl, fontWeight: '700' },
  policyStatus: { color: colors.textDim, fontSize: fonts.sizes.sm, marginTop: 2 },
  activeBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    borderWidth: 1, borderRadius: borderRadius.pill,
    paddingHorizontal: spacing.sm, paddingVertical: 4,
  },
  activeDot: {
    width: 8, height: 8, borderRadius: 4, backgroundColor: colors.success,
  },
  activeText: {
    color: colors.success, fontSize: fonts.sizes.xs, fontWeight: '700', letterSpacing: 1,
  },
  coverageGrid: {
    flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm,
  },
  coverageItem: {
    width: '47%', backgroundColor: colors.surfaceLight,
    borderRadius: borderRadius.sm, padding: spacing.md,
  },
  coverageLabel: { color: colors.textMuted, fontSize: fonts.sizes.xs },
  coverageValue: {
    color: colors.text, fontSize: fonts.sizes.md, fontWeight: '700', marginTop: 4,
  },
  triggersSection: { marginTop: spacing.lg },
  sectionTitle: {
    color: colors.text, fontSize: fonts.sizes.lg, fontWeight: '700',
    marginBottom: spacing.sm,
  },
  triggerList: { gap: spacing.xs },
  triggerItem: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  triggerText: { color: colors.textDim, fontSize: fonts.sizes.md },
  breakdownCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  breakdownSubtitle: {
    color: colors.textMuted, fontSize: fonts.sizes.sm,
    marginBottom: spacing.md,
  },
  breakdownRows: { gap: spacing.xs },
  breakdownRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  breakdownRowHighlight: {
    backgroundColor: 'rgba(0, 201, 177, 0.05)',
    marginHorizontal: -spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: borderRadius.sm,
  },
  breakdownLeft: { flex: 1 },
  breakdownLabel: { color: colors.textDim, fontSize: fonts.sizes.sm },
  breakdownFactor: { color: colors.textMuted, fontSize: fonts.sizes.xs, marginTop: 1 },
  breakdownValue: { color: colors.text, fontSize: fonts.sizes.md, fontWeight: '600' },
  breakdownTotal: {
    flexDirection: 'row', justifyContent: 'space-between',
    paddingTop: spacing.md, marginTop: spacing.sm,
  },
  totalLabel: { color: colors.text, fontSize: fonts.sizes.lg, fontWeight: '700' },
  totalValue: {
    color: colors.primary, fontSize: fonts.sizes.xl, fontWeight: '700',
  },
  tierCompare: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  tierRow: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  tierRowActive: {
    backgroundColor: 'rgba(0, 201, 177, 0.05)',
    marginHorizontal: -spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: borderRadius.sm,
  },
  tierDot: { width: 12, height: 12, borderRadius: 6 },
  tierRowInfo: { flex: 1 },
  tierRowName: { color: colors.text, fontSize: fonts.sizes.md, fontWeight: '600' },
  tierRowDetail: { color: colors.textMuted, fontSize: fonts.sizes.xs, marginTop: 2 },
  currentBadge: {
    backgroundColor: 'rgba(0, 201, 177, 0.15)',
    paddingHorizontal: 8, paddingVertical: 2,
    borderRadius: borderRadius.pill,
  },
  currentBadgeText: {
    color: colors.primary, fontSize: fonts.sizes.xs, fontWeight: '700',
  },
  actions: { gap: spacing.sm },
  renewButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: spacing.sm,
  },
  renewButtonText: { color: '#FFF', fontSize: fonts.sizes.lg, fontWeight: '700' },
  pauseButton: {
    borderWidth: 1,
    borderColor: colors.warning,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: spacing.sm,
  },
  pauseButtonText: { color: colors.warning, fontSize: fonts.sizes.md, fontWeight: '600' },
});
