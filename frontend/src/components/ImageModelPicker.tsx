/**
 * ImageModelPicker — Magic Hour-style image model selector.
 *
 * Tier matrix (per user spec, Apr-29 2026):
 *   z-image turbo      → DEFAULT, all plans (Free / Starter / Creator / Pro)
 *   seedream 4         → all plans
 *   Nano Banana        → block w/ upsell on Free + Starter; Creator + Pro OK
 *   Nano Banana 2      → block w/ upsell on Free + Starter; Creator + Pro OK
 *   Gemini 3.1 Image   → block w/ upsell on Free + Starter; Creator + Pro OK
 *   Nano Banana Pro    → block w/ upsell on Free / Starter / Creator; Pro OK
 *   Flux 1.1 Pro       → block w/ upsell on Free / Starter / Creator; Pro OK
 *   Imagen 3           → block w/ upsell on Free / Starter / Creator;
 *                        Pro = "Coming Soon"
 *   Recraft 3          → block w/ upsell on Free + Starter;
 *                        Creator + Pro = "Coming Soon"
 *   GPT-Image 1        → block w/ upsell on Free + Starter;
 *                        Creator + Pro = "Coming Soon"
 *
 * Behaviour:
 *  • Tap the picker pill → bottom-sheet modal lists all models.
 *  • Selecting a *locked* model → Alert "Upgrade to <plan>" with a route
 *    button to /subscription. Selection is NOT applied.
 *  • Selecting a *coming-soon* model (user IS on the right tier) → Alert
 *    "Coming Soon — we'll notify you when it launches". Selection NOT applied.
 *  • Tier helpers come from useTierGuard so the matrix stays in sync.
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, Modal, ScrollView, Pressable,
  Platform, Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';

export type ImageModelTier = 'free' | 'starter' | 'creator' | 'pro';

export type ImageModelId =
  | 'z_image_turbo'
  | 'seedream_4'
  | 'nano_banana'
  | 'nano_banana_2'
  | 'gemini_3_1_image'
  | 'nano_banana_pro'
  | 'flux_1_1_pro'
  | 'imagen_3'
  | 'recraft_3'
  | 'gpt_image_1';

export type ImageModel = {
  id: ImageModelId;
  name: string;
  vendor: string;
  /** Minimum tier where the model is fully usable. Anything below shows
      the "Upgrade required" Alert. */
  tier: ImageModelTier;
  blurb: string;
  icon: keyof typeof import('@expo/vector-icons/Ionicons').glyphMap;
  gradient: [string, string];
  /** Tiers on which the model is announced but not yet shipped. Showing
      "Coming Soon" alert (instead of upgrade) when tapped. */
  comingSoonOnTiers?: ImageModelTier[];
  /** Allowed resolutions for this model. */
  resolutions: ('512' | '1024' | '2048' | '4K')[];
  badges?: string[];
};

export const IMAGE_MODELS: ImageModel[] = [
  {
    id: 'z_image_turbo',
    name: 'Z-Image Turbo',
    vendor: 'Z-Lab · Default',
    tier: 'free',
    blurb: 'Fastest path to a clean, on-brand image. Great default for every plan.',
    icon: 'flash',
    gradient: ['#7B5CFF', '#06B6D4'],
    resolutions: ['512', '1024'],
    badges: ['DEFAULT', 'INSTANT'],
  },
  {
    id: 'seedream_4',
    name: 'Seedream 4',
    vendor: 'Seedream · Free for all',
    tier: 'free',
    blurb: 'Stylised dream-like portraits & scenes. Available on every plan.',
    icon: 'cloud',
    gradient: ['#FBBF24', '#FF6B08'],
    resolutions: ['512', '1024'],
    badges: ['FREE'],
  },
  {
    id: 'nano_banana',
    name: 'Nano Banana',
    vendor: 'Google Gemini',
    tier: 'creator',
    blurb: 'Photoreal portrait & scene generation with Gemini Nano Banana.',
    icon: 'sparkles',
    gradient: ['#F59E0B', '#EC4899'],
    resolutions: ['1024', '2048'],
    badges: ['CREATOR+'],
  },
  {
    id: 'nano_banana_2',
    name: 'Nano Banana 2',
    vendor: 'Google · Latest',
    tier: 'creator',
    blurb: 'Faster and more consistent portraits than Nano Banana v1.',
    icon: 'sparkles-outline',
    gradient: ['#EC4899', '#7B5CFF'],
    resolutions: ['1024', '2048'],
    badges: ['CREATOR+', 'NEW'],
  },
  {
    id: 'gemini_3_1_image',
    name: 'Gemini 3.1 Image',
    vendor: 'Google DeepMind',
    tier: 'creator',
    blurb: 'Top-tier prompt adherence + identity-preserving editing.',
    icon: 'image',
    gradient: ['#06B6D4', '#7B5CFF'],
    resolutions: ['1024', '2048'],
    badges: ['CREATOR+'],
  },
  {
    id: 'nano_banana_pro',
    name: 'Nano Banana Pro',
    vendor: 'Google · Pro tier',
    tier: 'pro',
    blurb: 'Highest-fidelity Nano Banana variant. Pro plan exclusive.',
    icon: 'diamond',
    gradient: ['#FBBF24', '#F59E0B'],
    resolutions: ['1024', '2048', '4K'],
    badges: ['PRO'],
  },
  {
    id: 'flux_1_1_pro',
    name: 'Flux 1.1 Pro',
    vendor: 'Black Forest Labs',
    tier: 'pro',
    blurb: 'Studio-grade photorealism & detail. Pro plan exclusive.',
    icon: 'flame',
    gradient: ['#FF6B08', '#FF007F'],
    resolutions: ['1024', '2048', '4K'],
    badges: ['PRO'],
  },
  {
    id: 'imagen_3',
    name: 'Imagen 3',
    vendor: 'Google DeepMind',
    tier: 'pro',
    comingSoonOnTiers: ['pro'],
    blurb: 'Cinematic stills with rich lighting & complex composition.',
    icon: 'aperture',
    gradient: ['#10B981', '#06B6D4'],
    resolutions: ['1024', '2048'],
    badges: ['PRO', 'SOON'],
  },
  {
    id: 'recraft_3',
    name: 'Recraft 3',
    vendor: 'Recraft · Vector + raster',
    tier: 'creator',
    comingSoonOnTiers: ['creator', 'pro'],
    blurb: 'Vector-clean SVG + raster — great for branded posters & logos.',
    icon: 'shapes',
    gradient: ['#A78BFA', '#06B6D4'],
    resolutions: ['1024', '2048'],
    badges: ['CREATOR+', 'SOON'],
  },
  {
    id: 'gpt_image_1',
    name: 'GPT-Image 1',
    vendor: 'OpenAI',
    tier: 'creator',
    comingSoonOnTiers: ['creator', 'pro'],
    blurb: 'OpenAI\'s flagship image model. Best at typography and posters.',
    icon: 'rocket',
    gradient: ['#7B5CFF', '#FF007F'],
    resolutions: ['1024', '2048'],
    badges: ['CREATOR+', 'SOON'],
  },
];

const TIER_RANK: Record<ImageModelTier, number> = { free: 0, starter: 1, creator: 2, pro: 3 };
const TIER_LABEL: Record<ImageModelTier, string> = {
  free: 'Free', starter: 'Starter', creator: 'Creator', pro: 'Pro',
};

export function getImageModel(id: ImageModelId): ImageModel {
  return IMAGE_MODELS.find(m => m.id === id) || IMAGE_MODELS[0];
}

export function isImageModelUsable(model: ImageModel, userTier: ImageModelTier): boolean {
  if (TIER_RANK[userTier] < TIER_RANK[model.tier]) return false;
  if (model.comingSoonOnTiers?.includes(userTier)) return false;
  return true;
}

type Props = {
  value: ImageModelId;
  onChange: (id: ImageModelId) => void;
  resolution?: '512' | '1024' | '2048' | '4K';
  onResolutionChange?: (r: '512' | '1024' | '2048' | '4K') => void;
  userTier?: ImageModelTier;
};

export default function ImageModelPicker({
  value, onChange, resolution = '1024', onResolutionChange,
  userTier = 'free',
}: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const current = getImageModel(value);

  const handleSelect = (m: ImageModel) => {
    // Coming-soon (user is on the right tier but model isn't shipped yet)
    if (m.comingSoonOnTiers?.includes(userTier)) {
      Alert.alert(
        `${m.name} — Coming Soon`,
        `${m.name} will be available shortly on the ${TIER_LABEL[m.tier]} plan and above. We'll notify you the moment it launches.`,
        [{ text: 'OK', style: 'cancel' }],
      );
      return;
    }
    // Locked because of plan tier → upsell
    if (TIER_RANK[userTier] < TIER_RANK[m.tier]) {
      Alert.alert(
        `${TIER_LABEL[m.tier]} plan required`,
        `${m.name} is part of the ${TIER_LABEL[m.tier]} plan. Upgrade to unlock this model and a lot more.`,
        [
          { text: 'Maybe later', style: 'cancel' },
          { text: 'View plans', onPress: () => router.push('/subscription' as any) },
        ],
      );
      return;
    }
    // Available
    onChange(m.id);
    if (onResolutionChange && !m.resolutions.includes(resolution as any)) {
      onResolutionChange(m.resolutions[0]);
    }
    setOpen(false);
  };

  return (
    <View>
      <TouchableOpacity style={s.pickerPill} activeOpacity={0.85} onPress={() => setOpen(true)}>
        <LinearGradient
          colors={current.gradient}
          start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
          style={s.pickerIconWrap}
        >
          <Ionicons name={current.icon} size={16} color="#fff" />
        </LinearGradient>
        <View style={{ flex: 1 }}>
          <Text style={s.pickerLabel}>IMAGE MODEL</Text>
          <Text style={s.pickerName} numberOfLines={1}>{current.name}</Text>
        </View>
        <View style={s.pickerCascade}>
          <View style={s.cascadePill}><Text style={s.cascadeTxt}>{resolution}</Text></View>
        </View>
        <Ionicons name="chevron-down" size={18} color="#A78BFA" />
      </TouchableOpacity>

      {!!onResolutionChange && (
        <View style={s.cascadeRow}>
          <Text style={s.cascadeLabel}>Model Detail</Text>
          <View style={s.segRow}>
            {current.resolutions.map((r) => (
              <TouchableOpacity
                key={r}
                onPress={() => onResolutionChange(r)}
                style={[s.segBtn, resolution === r && s.segBtnActive]}
                activeOpacity={0.85}
              >
                <Text style={[s.segTxt, resolution === r && s.segTxtActive]}>{r}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <Pressable style={s.overlay} onPress={() => setOpen(false)}>
          <Pressable style={s.sheet} onPress={(e) => e.stopPropagation()}>
            <View style={s.dragHandle} />
            <View style={s.sheetHeader}>
              <View style={{ flex: 1 }}>
                <Text style={s.sheetTitle}>Choose an image model</Text>
                <Text style={s.sheetSub}>Each model has its own quality / fidelity / cost.</Text>
              </View>
              <TouchableOpacity onPress={() => setOpen(false)} style={s.closeBtn}>
                <Ionicons name="close" size={20} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            <ScrollView style={{ maxHeight: 580 }} contentContainerStyle={{ paddingBottom: 30 }}>
              {IMAGE_MODELS.map((m) => {
                const active = m.id === value;
                const usable = isImageModelUsable(m, userTier);
                const comingSoon = m.comingSoonOnTiers?.includes(userTier);
                return (
                  <TouchableOpacity
                    key={m.id}
                    style={[
                      s.modelCard,
                      active && s.modelCardActive,
                      !usable && s.modelCardLocked,
                    ]}
                    activeOpacity={0.85}
                    onPress={() => handleSelect(m)}
                  >
                    <LinearGradient
                      colors={[m.gradient[0] + '22', m.gradient[1] + '11']}
                      start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                      style={StyleSheet.absoluteFillObject}
                    />
                    <LinearGradient
                      colors={m.gradient}
                      start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                      style={s.modelIcon}
                    >
                      <Ionicons name={m.icon} size={20} color="#fff" />
                    </LinearGradient>
                    <View style={{ flex: 1 }}>
                      <View style={s.modelTitleRow}>
                        <Text style={s.modelName} numberOfLines={1}>{m.name}</Text>
                        {(m.badges || []).map(b => (
                          <View key={b} style={s.modelBadge}><Text style={s.modelBadgeTxt}>{b}</Text></View>
                        ))}
                      </View>
                      <Text style={s.modelVendor}>{m.vendor}</Text>
                      <Text style={s.modelBlurb} numberOfLines={2}>{m.blurb}</Text>
                      <View style={s.modelChipRow}>
                        <View style={s.modelChip}>
                          <Ionicons name="resize" size={9} color="#A78BFA" />
                          <Text style={s.modelChipTxt}>{m.resolutions.join(' · ')}</Text>
                        </View>
                      </View>
                    </View>
                    {active ? (
                      <View style={s.activeMark}>
                        <Ionicons name="checkmark" size={14} color="#0B1120" />
                      </View>
                    ) : comingSoon ? (
                      <View style={s.lockMark}>
                        <Ionicons name="time" size={14} color="#FBBF24" />
                      </View>
                    ) : !usable ? (
                      <View style={s.lockMark}>
                        <Ionicons name="lock-closed" size={14} color="#FBBF24" />
                      </View>
                    ) : null}
                  </TouchableOpacity>
                );
              })}
              <Text style={s.footerHint}>
                Tap any locked model to see its upgrade path.
              </Text>
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  pickerPill: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: 'rgba(167,139,250,0.32)',
    borderRadius: 14, paddingVertical: 10, paddingHorizontal: 12,
  },
  pickerIconWrap: {
    width: 36, height: 36, borderRadius: 10,
    alignItems: 'center', justifyContent: 'center',
  },
  pickerLabel: { color: '#94A3B8', fontSize: 9, fontWeight: '900', letterSpacing: 0.8 },
  pickerName: { color: '#F1F5F9', fontSize: 14, fontWeight: '800', marginTop: 1 },
  pickerCascade: { flexDirection: 'row', gap: 4 },
  cascadePill: {
    backgroundColor: 'rgba(167,139,250,0.15)',
    borderWidth: 1, borderColor: 'rgba(167,139,250,0.32)',
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999,
  },
  cascadeTxt: { color: '#A78BFA', fontSize: 10, fontWeight: '900', letterSpacing: 0.4 },
  cascadeRow: { marginTop: 12 },
  cascadeLabel: { color: '#94A3B8', fontSize: 10, fontWeight: '900', letterSpacing: 0.8, marginBottom: 6 },
  segRow: { flexDirection: 'row', gap: 6 },
  segBtn: {
    flex: 1, paddingVertical: 8,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
    borderRadius: 10, alignItems: 'center',
  },
  segBtnActive: { backgroundColor: '#FBBF24', borderColor: '#FBBF24' },
  segTxt: { color: '#94A3B8', fontSize: 12, fontWeight: '800' },
  segTxtActive: { color: '#0B1120' },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.65)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: '#1E1B4B',
    borderTopLeftRadius: 24, borderTopRightRadius: 24,
    paddingHorizontal: 16, paddingTop: 6, paddingBottom: 16,
    borderWidth: 1, borderColor: 'rgba(167,139,250,0.22)',
  },
  dragHandle: { width: 40, height: 4, backgroundColor: '#475569', borderRadius: 2, alignSelf: 'center', marginBottom: 8 },
  sheetHeader: {
    flexDirection: 'row', alignItems: 'flex-start',
    paddingHorizontal: 4, paddingVertical: 6, gap: 8,
  },
  sheetTitle: { color: '#F1F5F9', fontSize: 18, fontWeight: '900' },
  sheetSub: { color: '#94A3B8', fontSize: 12, marginTop: 4 },
  closeBtn: {
    width: 34, height: 34, borderRadius: 17,
    backgroundColor: 'rgba(255,255,255,0.06)',
    alignItems: 'center', justifyContent: 'center',
  },
  modelCard: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: 'rgba(255,255,255,0.03)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
    borderRadius: 16, padding: 12, marginTop: 10, overflow: 'hidden',
  },
  modelCardActive: {
    borderColor: '#FBBF24',
    ...Platform.select({
      web: { boxShadow: '0 6px 22px rgba(251,191,36,0.25)' as any },
      default: { shadowColor: '#FBBF24', shadowOpacity: 0.45, shadowRadius: 12, shadowOffset: { width: 0, height: 4 } },
    }),
  },
  modelCardLocked: { opacity: 0.65 },
  modelIcon: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  modelTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  modelName: { color: '#F1F5F9', fontSize: 14, fontWeight: '900' },
  modelBadge: {
    backgroundColor: 'rgba(251,191,36,0.18)',
    borderWidth: 1, borderColor: 'rgba(251,191,36,0.45)',
    paddingHorizontal: 5, paddingVertical: 1, borderRadius: 5,
  },
  modelBadgeTxt: { color: '#FBBF24', fontSize: 8, fontWeight: '900', letterSpacing: 0.4 },
  modelVendor: { color: '#A78BFA', fontSize: 10, fontWeight: '700', marginTop: 2 },
  modelBlurb: { color: '#CBD5E1', fontSize: 11, lineHeight: 15, marginTop: 4 },
  modelChipRow: { flexDirection: 'row', gap: 6, marginTop: 6, flexWrap: 'wrap' },
  modelChip: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
    paddingHorizontal: 6, paddingVertical: 3, borderRadius: 7,
  },
  modelChipTxt: { color: '#E2E8F0', fontSize: 9, fontWeight: '700' },
  activeMark: {
    width: 26, height: 26, borderRadius: 13,
    backgroundColor: '#FBBF24', alignItems: 'center', justifyContent: 'center',
  },
  lockMark: {
    width: 26, height: 26, borderRadius: 13,
    backgroundColor: 'rgba(251,191,36,0.16)',
    borderWidth: 1, borderColor: 'rgba(251,191,36,0.4)',
    alignItems: 'center', justifyContent: 'center',
  },
  footerHint: {
    color: '#64748B', fontSize: 11, textAlign: 'center',
    marginTop: 18, lineHeight: 16, paddingHorizontal: 24,
  },
});
