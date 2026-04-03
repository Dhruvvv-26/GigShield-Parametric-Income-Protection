/**
 * GigShield — Design System Theme
 * Brand colors, typography, spacing utilities.
 */
export const colors = {
  primary:    '#00C9B1',   // Teal — trust, protection
  primaryDim: '#00A896',
  accent:     '#00E5CC',
  background: '#0A1628',   // Deep navy
  surface:    '#0F2038',   // Card backgrounds
  surfaceLight: '#162A4A',
  border:     '#1E3A5F',
  text:       '#FFFFFF',
  textDim:    '#8FA3BF',
  textMuted:  '#5A7090',
  success:    '#00E676',
  warning:    '#FFB74D',
  error:      '#FF5252',
  errorDim:   '#E53935',
  tier1:      '#4CAF50',
  tier2:      '#FF9800',
  tier3:      '#F44336',
  statusApproved: '#00E676',
  statusHold:     '#FFB74D',
  statusBlocked:  '#FF5252',
  statusPending:  '#64B5F6',
  glass:      'rgba(15, 32, 56, 0.85)',
  glassBorder: 'rgba(0, 201, 177, 0.15)',
};

export const fonts = {
  regular:   'System',
  medium:    'System',
  bold:      'System',
  sizes: {
    xs:   11,
    sm:   13,
    md:   15,
    lg:   18,
    xl:   22,
    xxl:  28,
    hero: 36,
  },
};

export const spacing = {
  xs:  4,
  sm:  8,
  md:  16,
  lg:  24,
  xl:  32,
  xxl: 48,
};

export const borderRadius = {
  sm:   8,
  md:  12,
  lg:  16,
  xl:  20,
  pill: 50,
};

export const shadows = {
  card: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  glow: {
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.4,
    shadowRadius: 20,
    elevation: 12,
  },
};

export default { colors, fonts, spacing, borderRadius, shadows };
