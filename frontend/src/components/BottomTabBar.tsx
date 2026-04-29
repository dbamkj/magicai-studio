/**
 * BottomTabBar — floating glass bottom navigation for MagiCAi Studio.
 *
 * 5 items: Home / Templates / Create (raised FAB) / Library / Profile.
 *
 * The Create item is a raised, gradient-circle CTA that pops above the bar.
 * On press it opens a Quick Action sheet (Reel / Avatar / Voice) which is
 * controlled by the parent via the `onCreatePress` prop.
 *
 * Usage — add to ANY screen that should have tabs:
 *   <BottomTabBar active="home" />
 *
 * To override the Create FAB action (e.g. open a quick-action sheet):
 *   <BottomTabBar active="home" onCreatePress={() => setSheetOpen(true)} />
 */
import React from 'react';
import { View, Text, StyleSheet, Pressable, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { BlurView } from 'expo-blur';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, { useSharedValue, useAnimatedStyle, withSpring } from 'react-native-reanimated';
import { brandGradient, glass, text as txt } from '../theme';

export type TabKey = 'home' | 'templates' | 'create' | 'library' | 'profile';

type Props = {
  active: TabKey;
  /** Override the default Create-FAB tap; useful for opening a Quick Action sheet. */
  onCreatePress?: () => void;
};

type TabDef = {
  key: TabKey;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconActive: keyof typeof Ionicons.glyphMap;
  route: string;
};

const TABS: TabDef[] = [
  { key: 'home',      label: 'Home',      icon: 'home-outline',     iconActive: 'home',     route: '/' },
  { key: 'templates', label: 'Templates', icon: 'sparkles-outline', iconActive: 'sparkles', route: '/marketplace' },
  { key: 'create',    label: 'Create',    icon: 'add',              iconActive: 'add',      route: '/create-wizard' },
  { key: 'library',   label: 'Library',   icon: 'folder-outline',   iconActive: 'folder',   route: '/projects' },
  { key: 'profile',   label: 'Profile',   icon: 'person-outline',   iconActive: 'person',   route: '/profile' },
];

export default function BottomTabBar({ active, onCreatePress }: Props) {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  // Bottom safe-area is now ABSORBED by the bar background (extends flush to
  // bottom of screen) instead of leaving a transparent gap below the bar.
  const safeBottom = Math.max(insets.bottom, 6);

  return (
    <View style={s.wrap} pointerEvents="box-none">
      <View style={[s.barContainer, { paddingBottom: safeBottom }]}>
        {/* Glass blur layer */}
        {Platform.OS !== 'web' ? (
          <BlurView intensity={40} tint="dark" style={StyleSheet.absoluteFill} />
        ) : null}
        <View style={[StyleSheet.absoluteFill, s.glassBg]} />

        {/* Tab buttons */}
        <View style={s.row}>
          {TABS.map((t) => {
            const isActive = t.key === active;
            const isCreate = t.key === 'create';
            return (
              <TabButton
                key={t.key}
                tab={t}
                isActive={isActive}
                isCreate={isCreate}
                onPress={() => {
                  if (isCreate && onCreatePress) {
                    onCreatePress();
                    return;
                  }
                  if (isActive) return;
                  router.push(t.route as any);
                }}
              />
            );
          })}
        </View>
      </View>
    </View>
  );
}

/* ============== TabButton ============== */
function TabButton({
  tab, isActive, isCreate, onPress,
}: { tab: TabDef; isActive: boolean; isCreate: boolean; onPress: () => void; }) {
  // Press scale animation
  const scale = useSharedValue(1);
  const aStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  if (isCreate) {
    // Raised gradient circular CTA
    return (
      <Pressable
        onPressIn={() => { scale.value = withSpring(0.92, { damping: 14, stiffness: 240 }); }}
        onPressOut={() => { scale.value = withSpring(1, { damping: 14, stiffness: 240 }); }}
        onPress={onPress}
        hitSlop={8}
        style={s.createWrap}
      >
        <Animated.View style={[s.createBtn, aStyle]}>
          <LinearGradient
            colors={['#FF6B08', '#FF007F', '#AE29FF']}
            start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
            style={StyleSheet.absoluteFill}
          />
          <Ionicons name="add" size={24} color="#fff" />
        </Animated.View>
        <Text style={[s.label, { color: txt.secondary, marginTop: 2 }]} numberOfLines={1}>Create</Text>
      </Pressable>
    );
  }

  return (
    <Pressable
      onPressIn={() => { scale.value = withSpring(0.9, { damping: 14, stiffness: 240 }); }}
      onPressOut={() => { scale.value = withSpring(1, { damping: 14, stiffness: 240 }); }}
      onPress={onPress}
      hitSlop={8}
      style={s.tabBtn}
    >
      <Animated.View style={[s.iconWrap, aStyle]}>
        <Ionicons
          name={isActive ? tab.iconActive : tab.icon}
          size={22}
          color={isActive ? '#fff' : txt.muted}
        />
        {isActive && <View style={s.activeDot} />}
      </Animated.View>
      <Text
        style={[s.label, { color: isActive ? '#fff' : txt.muted, fontWeight: isActive ? '800' : '600' }]}
        numberOfLines={1}
      >
        {tab.label}
      </Text>
    </Pressable>
  );
}

/* ============== Styles ============== */
const s = StyleSheet.create({
  wrap: {
    position: 'absolute',
    left: 0, right: 0, bottom: 0,
    paddingHorizontal: 0,           // edge-to-edge
    paddingTop: 0,
    zIndex: 100,
  },
  barContainer: {
    minHeight: 56,
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: 0,
    overflow: 'hidden',
    borderWidth: 1,
    borderBottomWidth: 0,
    borderColor: 'rgba(255,255,255,0.10)',
    // 3D depth — top highlight + outer drop shadow
    ...Platform.select({
      web: {
        boxShadow:
          '0 -8px 24px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.08)' as any,
      },
      default: {
        shadowColor: '#000', shadowOpacity: 0.45, shadowRadius: 22,
        shadowOffset: { width: 0, height: -8 },
      },
    }),
  },
  glassBg: { backgroundColor: 'rgba(11, 17, 32, 0.96)' },
  row: {
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 6,
  },
  tabBtn: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
  },
  iconWrap: {
    alignItems: 'center', justifyContent: 'center',
    height: 24,
  },
  activeDot: {
    width: 4, height: 4, borderRadius: 2,
    backgroundColor: '#FF9A3C',
    marginTop: 2,
  },
  label: {
    fontSize: 9.5, marginTop: 1, letterSpacing: 0.2,
  },
  createWrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
  },
  createBtn: {
    width: 40, height: 40, borderRadius: 20,
    overflow: 'hidden',
    alignItems: 'center', justifyContent: 'center',
    marginTop: 0,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.30)',
    ...Platform.select({
      web: {
        boxShadow:
          '0 6px 16px rgba(255,107,8,0.55), inset 0 1px 0 rgba(255,255,255,0.35)' as any,
      },
      default: {
        shadowColor: '#FF6B08', shadowOpacity: 0.55, shadowRadius: 14, shadowOffset: { width: 0, height: 4 },
      },
    }),
  },
});
