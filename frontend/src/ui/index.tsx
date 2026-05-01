/**
 * MagiCAi Studio — Shared UI primitives (Track 1A)
 *
 * Compact glassmorphism + aurora design-system kit. These primitives
 * eliminate ~40-80 LOC of boilerplate StyleSheet from every screen and
 * guarantee a unified premium-neon-glass look.
 *
 * Public API:
 *   <ScreenShell>         — Aurora bg + safe-area + bottom-tab clearance
 *   <GlassCard>           — Frosted glass panel with optional aurora border
 *   <GradientButton>      — Primary CTA (pink→orange gradient)
 *   <GhostButton>         — Secondary glass button
 *   <Chip>                — Small pill-shaped tag/filter
 *   <SectionHeader>       — Eyebrow + Title pair, used at top of sections
 *   <FieldLabel>          — Small uppercase label above an input
 *
 * Design tokens come from `src/theme.ts` so visual changes propagate.
 */

import React, { ReactNode } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, Platform, ScrollView,
  ViewStyle, StyleProp, TextStyle,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import AuroraBackground from '../AuroraBackground';
import * as theme from '../theme';

// ──────────────────────────── ScreenShell ────────────────────────────────
type ShellProps = {
  children: ReactNode;
  scroll?: boolean;
  /** Add bottom padding so content doesn't hide under the floating tab bar. */
  withTabBar?: boolean;
  /** Optional sticky header inserted at top, OUTSIDE the scrollview. */
  header?: ReactNode;
  contentStyle?: StyleProp<ViewStyle>;
  testID?: string;
};

export function ScreenShell({
  children, scroll = true, withTabBar = false, header, contentStyle, testID,
}: ShellProps) {
  const Body = scroll ? ScrollView : View;
  const bodyProps = scroll
    ? {
        showsVerticalScrollIndicator: false,
        contentContainerStyle: [
          styles.shellBody,
          withTabBar && { paddingBottom: 110 },
          contentStyle,
        ],
        keyboardShouldPersistTaps: 'handled' as const,
      }
    : {
        style: [
          styles.shellBody,
          withTabBar && { paddingBottom: 110 },
          { flex: 1 },
          contentStyle,
        ],
      };
  return (
    <View style={styles.shellRoot} testID={testID}>
      <AuroraBackground />
      {header}
      {/* @ts-ignore — Body switches between View/ScrollView */}
      <Body {...bodyProps}>{children}</Body>
    </View>
  );
}

// ──────────────────────────── GlassCard ──────────────────────────────────
type GlassCardProps = {
  children: ReactNode;
  /** Apply a soft aurora-pink glow border (e.g. for the "active plan" card). */
  glow?: boolean;
  /** Reduced padding variant for dense lists. */
  compact?: boolean;
  style?: StyleProp<ViewStyle>;
  onPress?: () => void;
  testID?: string;
};

export function GlassCard({ children, glow, compact, style, onPress, testID }: GlassCardProps) {
  const Wrap: any = onPress ? TouchableOpacity : View;
  return (
    <Wrap
      activeOpacity={onPress ? 0.85 : 1}
      onPress={onPress}
      testID={testID}
      style={[
        styles.glassCard,
        compact && { padding: 12 },
        glow && styles.glassCardGlow,
        style,
      ]}
    >
      {children}
    </Wrap>
  );
}

// ──────────────────────────── GradientButton ─────────────────────────────
type GradientBtnProps = {
  label: string;
  onPress?: () => void;
  icon?: keyof typeof Ionicons.glyphMap;
  iconRight?: keyof typeof Ionicons.glyphMap;
  loading?: boolean;
  disabled?: boolean;
  /** 'lg' (default), 'md', 'sm' */
  size?: 'sm' | 'md' | 'lg';
  /** Override gradient (defaults to brand pink→orange). */
  colors?: readonly [string, string, ...string[]];
  fullWidth?: boolean;
  style?: StyleProp<ViewStyle>;
  testID?: string;
};

export function GradientButton({
  label, onPress, icon, iconRight, loading, disabled,
  size = 'lg', colors, fullWidth = true, style, testID,
}: GradientBtnProps) {
  const sizeStyle = SIZE_STYLES[size];
  return (
    <TouchableOpacity
      onPress={loading || disabled ? undefined : onPress}
      activeOpacity={0.88}
      disabled={!!loading || !!disabled}
      style={[
        fullWidth && { alignSelf: 'stretch' },
        disabled && { opacity: 0.5 },
        style,
      ]}
      testID={testID}
    >
      <LinearGradient
        colors={(colors || ['#FF4D8D', '#FF9A3C']) as any}
        start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
        style={[styles.gradBtnBase, sizeStyle.btn]}
      >
        {!!icon && (
          <Ionicons name={icon} size={sizeStyle.iconSize} color="#fff" style={{ marginRight: 6 }} />
        )}
        <Text style={[styles.gradBtnText, sizeStyle.text]}>{loading ? '…' : label}</Text>
        {!!iconRight && (
          <Ionicons name={iconRight} size={sizeStyle.iconSize} color="#fff" style={{ marginLeft: 6 }} />
        )}
      </LinearGradient>
    </TouchableOpacity>
  );
}

// ──────────────────────────── GhostButton ────────────────────────────────
export function GhostButton({
  label, onPress, icon, size = 'lg', fullWidth = true, style, testID,
}: Omit<GradientBtnProps, 'colors' | 'iconRight' | 'loading' | 'disabled'>) {
  const sizeStyle = SIZE_STYLES[size];
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.85}
      style={[
        styles.ghostBtnBase,
        sizeStyle.btn,
        fullWidth && { alignSelf: 'stretch' },
        style,
      ]}
      testID={testID}
    >
      {!!icon && (
        <Ionicons name={icon} size={sizeStyle.iconSize} color={theme.text.primary} style={{ marginRight: 6 }} />
      )}
      <Text style={[styles.ghostBtnText, sizeStyle.text]}>{label}</Text>
    </TouchableOpacity>
  );
}

// ──────────────────────────── Chip ───────────────────────────────────────
type ChipProps = {
  label: string;
  active?: boolean;
  icon?: keyof typeof Ionicons.glyphMap;
  onPress?: () => void;
  /** Hex color used for the active background tint. */
  activeColor?: string;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
};

export function Chip({ label, active, icon, onPress, activeColor, style, textStyle }: ChipProps) {
  const tint = activeColor || theme.aurora.pink;
  const Wrap: any = onPress ? TouchableOpacity : View;
  return (
    <Wrap
      onPress={onPress}
      activeOpacity={0.8}
      style={[
        styles.chipBase,
        active && { backgroundColor: `${tint}26`, borderColor: tint },
        style,
      ]}
    >
      {!!icon && (
        <Ionicons
          name={icon}
          size={12}
          color={active ? '#fff' : theme.text.muted}
          style={{ marginRight: 4 }}
        />
      )}
      <Text
        style={[
          styles.chipText,
          active && { color: '#fff', fontWeight: '800' },
          textStyle,
        ]}
      >
        {label}
      </Text>
    </Wrap>
  );
}

// ──────────────────────────── SectionHeader ──────────────────────────────
type SectionHeaderProps = {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  right?: ReactNode;
  style?: StyleProp<ViewStyle>;
};

export function SectionHeader({ eyebrow, title, subtitle, right, style }: SectionHeaderProps) {
  return (
    <View style={[styles.sectionHeader, style]}>
      <View style={{ flex: 1 }}>
        {!!eyebrow && <Text style={styles.shEyebrow}>{eyebrow}</Text>}
        <Text style={styles.shTitle}>{title}</Text>
        {!!subtitle && <Text style={styles.shSubtitle}>{subtitle}</Text>}
      </View>
      {!!right && right}
    </View>
  );
}

// ──────────────────────────── FieldLabel ─────────────────────────────────
export function FieldLabel({ children, style }: { children: ReactNode; style?: StyleProp<TextStyle> }) {
  return <Text style={[styles.fieldLabel, style]}>{children}</Text>;
}

// ──────────────────────────── Sizes ──────────────────────────────────────
const SIZE_STYLES: Record<'sm' | 'md' | 'lg', { btn: ViewStyle; text: TextStyle; iconSize: number }> = {
  sm: { btn: { paddingVertical: 8,  paddingHorizontal: 12 }, text: { fontSize: 12, fontWeight: '700' }, iconSize: 14 },
  md: { btn: { paddingVertical: 11, paddingHorizontal: 16 }, text: { fontSize: 14, fontWeight: '800' }, iconSize: 16 },
  lg: { btn: { paddingVertical: 14, paddingHorizontal: 20 }, text: { fontSize: 15, fontWeight: '800' }, iconSize: 18 },
};

// ──────────────────────────── Stylesheet ─────────────────────────────────
const styles = StyleSheet.create({
  shellRoot: { flex: 1, backgroundColor: theme.aurora.bg0 },
  shellBody: {
    paddingHorizontal: theme.space.md,
    paddingTop: Platform.select({ ios: 56, android: 36, default: 24 }),
    paddingBottom: theme.space.lg,
    gap: theme.space.md,
  },

  glassCard: {
    backgroundColor: theme.glass.background,
    borderWidth: 1, borderColor: theme.glass.border,
    borderRadius: theme.radius.lg,
    padding: 16,
    ...Platform.select({
      web: { boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.08)' as any },
      default: {},
    }),
  },
  glassCardGlow: {
    borderColor: theme.aurora.pink,
    backgroundColor: `${theme.aurora.pink}12`,
    ...Platform.select({
      web: { boxShadow: `0 0 24px ${theme.aurora.pink}44` as any },
      default: {},
    }),
  },

  gradBtnBase: {
    flexDirection: 'row',
    alignItems: 'center', justifyContent: 'center',
    borderRadius: theme.radius.pill,
  },
  gradBtnText: { color: '#fff', letterSpacing: 0.3 },

  ghostBtnBase: {
    flexDirection: 'row',
    alignItems: 'center', justifyContent: 'center',
    borderRadius: theme.radius.pill,
    backgroundColor: theme.glass.background,
    borderWidth: 1, borderColor: theme.glass.border,
  },
  ghostBtnText: { color: theme.text.primary, letterSpacing: 0.3 },

  chipBase: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10, paddingVertical: 6,
    backgroundColor: theme.glass.background,
    borderRadius: theme.radius.pill,
    borderWidth: 1, borderColor: theme.glass.border,
  },
  chipText: { color: theme.text.muted, fontSize: 11, fontWeight: '700' },

  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: theme.space.sm,
  },
  shEyebrow: {
    color: theme.aurora.orange,
    fontSize: 10, fontWeight: '800',
    letterSpacing: 1.2, marginBottom: 2,
    textTransform: 'uppercase',
  },
  shTitle: {
    color: theme.text.primary,
    fontSize: 22, fontWeight: '900', lineHeight: 26,
  },
  shSubtitle: {
    color: theme.text.muted,
    fontSize: 13, marginTop: 4, lineHeight: 18,
  },

  fieldLabel: {
    color: theme.text.muted,
    fontSize: 11, fontWeight: '800', letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginBottom: 6,
  },
});

// re-export theme tokens for convenience
export { theme };
