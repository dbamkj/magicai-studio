/**
 * Premium Neon Glass — primitive UI components.
 *
 * • <GlassCard>     frosted card primitive with subtle border + radius
 * • <NeonButton>    pill gradient CTA (orange→pink→purple)
 * • <CoolButton>    cool gradient CTA (cyan→purple) — secondary action
 * • <GhostButton>   text-only neon link
 * • <GlassPill>     small pill-shape badge
 * • <SectionTitle>  heading text with optional caption
 *
 * All children render React Native primitives; no web-only deps.
 */
import React from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ViewStyle,
  TextStyle, ActivityIndicator,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { colors, radii, spacing, typography } from './theme';

/* --------------------------- GlassCard --------------------------- */
type GlassCardProps = {
  children: React.ReactNode;
  style?: ViewStyle | ViewStyle[];
  padding?: number;
  radius?: number;
  borderHi?: boolean;        // brighter border for emphasis
  glow?: 'purple' | 'orange' | 'cyan' | 'none';
};
export function GlassCard({
  children, style, padding = spacing.md, radius = radii.lg,
  borderHi = false, glow = 'none',
}: GlassCardProps) {
  const shadowColor =
    glow === 'purple' ? colors.auroraPurple
    : glow === 'orange' ? colors.auroraOrange
    : glow === 'cyan' ? colors.auroraCyan
    : 'transparent';
  return (
    <View
      style={[
        {
          backgroundColor: colors.glassBg,
          borderWidth: 1,
          borderColor: borderHi ? colors.glassBorderHi : colors.glassBorder,
          borderRadius: radius,
          padding,
          shadowColor,
          shadowOffset: { width: 0, height: 0 },
          shadowOpacity: glow !== 'none' ? 0.4 : 0,
          shadowRadius: glow !== 'none' ? 18 : 0,
          elevation: glow !== 'none' ? 8 : 0,
        },
        style as ViewStyle,
      ]}
    >
      {children}
    </View>
  );
}

/* --------------------------- NeonButton -------------------------- */
type ButtonProps = {
  label: string;
  onPress?: () => void;
  icon?: keyof typeof Ionicons.glyphMap;
  iconRight?: keyof typeof Ionicons.glyphMap;
  loading?: boolean;
  disabled?: boolean;
  size?: 'lg' | 'md' | 'sm';
  style?: ViewStyle;
  textStyle?: TextStyle;
  fullWidth?: boolean;
};

export function NeonButton({
  label, onPress, icon, iconRight, loading, disabled,
  size = 'lg', style, textStyle, fullWidth = true,
}: ButtonProps) {
  const heights = { lg: 54, md: 46, sm: 38 };
  const fontSizes = { lg: 16, md: 14, sm: 12 };
  return (
    <TouchableOpacity
      activeOpacity={0.85}
      disabled={disabled || loading}
      onPress={onPress}
      style={[
        {
          borderRadius: radii.pill,
          overflow: 'hidden',
          opacity: disabled ? 0.5 : 1,
          alignSelf: fullWidth ? 'stretch' : 'flex-start',
        },
        // outer glow
        {
          shadowColor: colors.auroraOrange,
          shadowOffset: { width: 0, height: 0 },
          shadowOpacity: disabled ? 0 : 0.5,
          shadowRadius: 16,
          elevation: 10,
        },
        style,
      ]}
    >
      <LinearGradient
        colors={colors.brandGradient as any}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={{
          height: heights[size],
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          paddingHorizontal: spacing.lg,
          gap: 8,
        }}
      >
        {loading ? <ActivityIndicator color="#fff" /> : (
          <>
            {icon ? <Ionicons name={icon} size={fontSizes[size] + 2} color="#fff" /> : null}
            <Text style={[{
              color: '#fff',
              fontSize: fontSizes[size],
              fontWeight: '800',
              letterSpacing: 0.3,
            }, textStyle]}>{label}</Text>
            {iconRight ? <Ionicons name={iconRight} size={fontSizes[size] + 2} color="#fff" /> : null}
          </>
        )}
      </LinearGradient>
    </TouchableOpacity>
  );
}

/* --------------------------- CoolButton -------------------------- */
export function CoolButton(props: ButtonProps) {
  const { label, onPress, icon, iconRight, loading, disabled,
    size = 'lg', style, textStyle, fullWidth = true } = props;
  const heights = { lg: 54, md: 46, sm: 38 };
  const fontSizes = { lg: 16, md: 14, sm: 12 };
  return (
    <TouchableOpacity
      activeOpacity={0.85}
      disabled={disabled || loading}
      onPress={onPress}
      style={[
        {
          borderRadius: radii.pill,
          overflow: 'hidden',
          opacity: disabled ? 0.5 : 1,
          alignSelf: fullWidth ? 'stretch' : 'flex-start',
        },
        {
          shadowColor: colors.auroraCyan,
          shadowOffset: { width: 0, height: 0 },
          shadowOpacity: disabled ? 0 : 0.45,
          shadowRadius: 16,
          elevation: 10,
        },
        style,
      ]}
    >
      <LinearGradient
        colors={colors.coolGradient as any}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={{
          height: heights[size],
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          paddingHorizontal: spacing.lg,
          gap: 8,
        }}
      >
        {loading ? <ActivityIndicator color="#fff" /> : (
          <>
            {icon ? <Ionicons name={icon} size={fontSizes[size] + 2} color="#fff" /> : null}
            <Text style={[{
              color: '#fff', fontSize: fontSizes[size],
              fontWeight: '800', letterSpacing: 0.3,
            }, textStyle]}>{label}</Text>
            {iconRight ? <Ionicons name={iconRight} size={fontSizes[size] + 2} color="#fff" /> : null}
          </>
        )}
      </LinearGradient>
    </TouchableOpacity>
  );
}

/* --------------------------- GlassButton ------------------------- */
/** Translucent secondary CTA — same shape as NeonButton */
export function GlassButton(props: ButtonProps) {
  const { label, onPress, icon, iconRight, loading, disabled,
    size = 'lg', style, textStyle, fullWidth = true } = props;
  const heights = { lg: 54, md: 46, sm: 38 };
  const fontSizes = { lg: 16, md: 14, sm: 12 };
  return (
    <TouchableOpacity
      activeOpacity={0.85}
      disabled={disabled || loading}
      onPress={onPress}
      style={[
        {
          height: heights[size],
          borderRadius: radii.pill,
          backgroundColor: colors.glassBg,
          borderWidth: 1,
          borderColor: colors.glassBorderHi,
          alignSelf: fullWidth ? 'stretch' : 'flex-start',
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          paddingHorizontal: spacing.lg,
          gap: 8,
          opacity: disabled ? 0.5 : 1,
        },
        style,
      ]}
    >
      {loading ? <ActivityIndicator color="#fff" /> : (
        <>
          {icon ? <Ionicons name={icon} size={fontSizes[size] + 2} color="#fff" /> : null}
          <Text style={[{
            color: '#fff', fontSize: fontSizes[size],
            fontWeight: '700', letterSpacing: 0.2,
          }, textStyle]}>{label}</Text>
          {iconRight ? <Ionicons name={iconRight} size={fontSizes[size] + 2} color="#fff" /> : null}
        </>
      )}
    </TouchableOpacity>
  );
}

/* --------------------------- GhostButton ------------------------- */
export function GhostButton({ label, onPress, color = colors.auroraPurple, style, textStyle }:
  { label: string; onPress?: () => void; color?: string; style?: ViewStyle; textStyle?: TextStyle }) {
  return (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={onPress}
      style={[{ paddingVertical: spacing.sm, paddingHorizontal: spacing.md, alignItems: 'center' }, style]}
    >
      <Text style={[{ color, fontSize: 14, fontWeight: '700' }, textStyle]}>{label}</Text>
    </TouchableOpacity>
  );
}

/* --------------------------- GlassPill --------------------------- */
export function GlassPill({
  children, color = colors.text, bg = colors.glassBg, border = colors.glassBorder,
  style,
}: { children: React.ReactNode; color?: string; bg?: string; border?: string; style?: ViewStyle }) {
  return (
    <View
      style={[
        {
          flexDirection: 'row', alignItems: 'center', gap: 6,
          backgroundColor: bg,
          borderWidth: 1, borderColor: border,
          paddingHorizontal: 10, paddingVertical: 5,
          borderRadius: radii.pill,
        },
        style,
      ]}
    >
      {typeof children === 'string'
        ? <Text style={{ color, fontSize: 11, fontWeight: '700', letterSpacing: 0.4 }}>{children}</Text>
        : children}
    </View>
  );
}

/* --------------------------- SectionTitle ------------------------ */
export function SectionTitle({
  title, caption, right,
}: { title: string; caption?: string; right?: React.ReactNode }) {
  return (
    <View style={localStyles.sectionTitleRow}>
      <View style={{ flex: 1 }}>
        <Text style={localStyles.sectionTitle}>{title}</Text>
        {caption ? <Text style={localStyles.sectionCaption}>{caption}</Text> : null}
      </View>
      {right}
    </View>
  );
}

const localStyles = StyleSheet.create({
  sectionTitleRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginTop: spacing.lg, marginBottom: spacing.sm,
  },
  sectionTitle: { ...typography.h3, color: colors.text },
  sectionCaption: { ...typography.small, color: colors.textDim, marginTop: 2 },
});
