/**
 * ModelPicker — Magic Hour-style model selector for the Creator Wizard.
 *
 * Usage:
 *   <ModelPicker
 *     value={modelId}
 *     onChange={setModelId}
 *     onResolutionChange={setResolution}
 *     onDurationChange={setDuration}
 *     resolution={resolution}
 *     duration={duration}
 *     userTier="free"
 *   />
 *
 * Behaviour:
 *  • Tap the picker pill → opens a bottom-sheet modal with all models.
 *  • Each model card lists its tier badge, blurb, and capability chips.
 *  • Selecting a model auto-cascades its supported resolutions + durations.
 *  • Models flagged `comingSoon` show a disabled state with a "Notify me"
 *    button (no-op for now). Free-tier users picking a higher-tier model
 *    see a "Upgrade required" tag.
 *  • Currently usable models map to the existing wizard pipelines:
 *      pixabay_stock → Pixabay video (reelMode='video')
 *      ai_images     → Pixabay images + ken-burns (reelMode='images')
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, Modal, ScrollView, Pressable, Platform, Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { BlurView } from 'expo-blur';
import { useRouter } from 'expo-router';

export type ModelTier = 'free' | 'starter' | 'creator' | 'pro';

export type ReelModelId =
  | 'kling_pro'
  | 'minimax_hailuo'
  | 'kling_v16'
  | 'sora_2'
  | 'runway_gen3'
  | 'veo_3'
  | 'hunyuan_video';

export type ReelModel = {
  id: ReelModelId;
  name: string;
  short: string;          // e.g. "Stock Video"
  vendor: string;         // e.g. "Pixabay"
  tier: ModelTier;
  blurb: string;
  icon: keyof typeof Ionicons.glyphMap;
  gradient: [string, string];
  /** "video" → real moving stock; "image" → ken-burns motion of stills */
  pipeline: 'video' | 'images';
  /** Allowed resolutions for this model. */
  resolutions: ('720p' | '1080p' | '4K')[];
  /** Allowed durations in seconds. */
  durations: number[];
  /** Tiers on which the model is announced but not yet shipped. Showing
      "Coming Soon" alert (instead of upgrade) when tapped. */
  comingSoonOnTiers?: ModelTier[];
  badges?: string[];      // e.g. ["NEW", "Cinematic"]
};

/* MagicHour-style premium video model catalog (Apr-29 2026 spec).
 * Pixabay options removed — backend still uses Pixabay as the actual
 * generation pipeline today, but the picker only exposes the curated MH
 * lineup so the experience matches a "premium AI" product. Locked /
 * coming-soon models trigger an upgrade-or-wait Alert when tapped. */
export const MODELS: ReelModel[] = [
  {
    id: 'kling_pro',
    name: 'Kling Pro',
    short: 'Kling Pro',
    vendor: 'Kuaishou · Default',
    tier: 'free',
    blurb: 'Default cinematic model — real motion physics on every plan, including Free.',
    icon: 'film',
    gradient: ['#7B5CFF', '#06B6D4'],
    pipeline: 'video',
    resolutions: ['720p', '1080p'],
    durations: [5, 10, 15],
    badges: ['DEFAULT', 'INSTANT'],
  },
  {
    id: 'minimax_hailuo',
    name: 'MiniMax Hailuo',
    short: 'Hailuo 02',
    vendor: 'MiniMax · Free for all',
    tier: 'free',
    blurb: 'Smooth motion + great prompt adherence. Available on every plan.',
    icon: 'flash',
    gradient: ['#FBBF24', '#FF6B08'],
    pipeline: 'video',
    resolutions: ['720p', '1080p'],
    durations: [5, 10, 15, 20],
    badges: ['FREE'],
  },
  {
    id: 'kling_v16',
    name: 'Kling 1.6 Cinematic',
    short: 'Kling 1.6',
    vendor: 'Kuaishou · Premium',
    tier: 'creator',
    blurb: 'Higher-fidelity Kling with cinematic camera control & long-form coherence.',
    icon: 'sparkles',
    gradient: ['#FF6B08', '#FF007F'],
    pipeline: 'video',
    resolutions: ['1080p', '4K'],
    durations: [5, 10],
    badges: ['CREATOR+', 'CINEMATIC'],
  },
  {
    id: 'sora_2',
    name: 'Sora 2.0',
    short: 'Sora 2',
    vendor: 'OpenAI',
    tier: 'creator',
    blurb: 'OpenAI Sora 2 — long-form coherence, complex camera moves, character consistency.',
    icon: 'rocket',
    gradient: ['#AE29FF', '#7B5CFF'],
    pipeline: 'video',
    resolutions: ['1080p'],
    durations: [5, 10, 20],
    badges: ['CREATOR+', 'NEW'],
  },
  {
    id: 'runway_gen3',
    name: 'Runway Gen-3',
    short: 'Runway Gen-3',
    vendor: 'Runway ML',
    tier: 'pro',
    blurb: 'Runway Gen-3 Alpha Turbo — fast text-to-video with exquisite motion control.',
    icon: 'flash',
    gradient: ['#10B981', '#06B6D4'],
    pipeline: 'video',
    resolutions: ['720p', '1080p'],
    durations: [5, 10],
    badges: ['PRO'],
  },
  {
    id: 'veo_3',
    name: 'Veo 3.0',
    short: 'Veo 3',
    vendor: 'Google DeepMind',
    tier: 'pro',
    comingSoonOnTiers: ['pro'],
    blurb: '4K AI video with native audio. Best for hyper-real ads and product reels.',
    icon: 'videocam',
    gradient: ['#00C6FF', '#AE29FF'],
    pipeline: 'video',
    resolutions: ['1080p', '4K'],
    durations: [8, 16],
    badges: ['PRO', '4K', 'SOON'],
  },
  {
    id: 'hunyuan_video',
    name: 'Hunyuan Video',
    short: 'Hunyuan',
    vendor: 'Tencent',
    tier: 'creator',
    comingSoonOnTiers: ['creator', 'pro'],
    blurb: 'Tencent Hunyuan video model — strong on Asian aesthetics & dance.',
    icon: 'planet',
    gradient: ['#EC4899', '#7B5CFF'],
    pipeline: 'video',
    resolutions: ['720p', '1080p'],
    durations: [5, 10],
    badges: ['CREATOR+', 'SOON'],
  },
];

const TIER_RANK: Record<ModelTier, number> = { free: 0, starter: 1, creator: 2, pro: 3 };
const TIER_LABEL: Record<ModelTier, string> = {
  free: 'Free', starter: 'Starter', creator: 'Creator', pro: 'Pro',
};

export function getModel(id: ReelModelId): ReelModel {
  return MODELS.find(m => m.id === id) || MODELS[0];
}

export function isModelUnlocked(model: ReelModel, userTier: ModelTier): boolean {
  if (TIER_RANK[userTier] < TIER_RANK[model.tier]) return false;
  if (model.comingSoonOnTiers?.includes(userTier)) return false;
  return true;
}

type Props = {
  value: ReelModelId;
  onChange: (id: ReelModelId) => void;
  resolution: '720p' | '1080p' | '4K';
  onResolutionChange: (r: '720p' | '1080p' | '4K') => void;
  duration: number;
  onDurationChange: (d: number) => void;
  userTier?: ModelTier;
};

export default function ModelPicker({
  value, onChange, resolution, onResolutionChange,
  duration, onDurationChange, userTier = 'free',
}: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const current = getModel(value);

  const handleSelect = (m: ReelModel) => {
    // Coming-soon for the user's tier → tell them when it's launching.
    if (m.comingSoonOnTiers?.includes(userTier)) {
      Alert.alert(
        `${m.name} — Coming Soon`,
        `${m.name} will be available shortly on the ${TIER_LABEL[m.tier]} plan and above. We'll notify you the moment it launches.`,
        [{ text: 'OK', style: 'cancel' }],
      );
      return;
    }
    // Plan-tier locked → upsell.
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
    // Available — apply.
    onChange(m.id);
    if (!m.resolutions.includes(resolution as any)) onResolutionChange(m.resolutions[0]);
    if (!m.durations.includes(duration)) onDurationChange(m.durations[0]);
    setOpen(false);
  };

  return (
    <View>
      {/* The picker pill */}
      <TouchableOpacity
        style={s.pickerPill}
        activeOpacity={0.85}
        onPress={() => setOpen(true)}
      >
        <LinearGradient
          colors={current.gradient}
          start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
          style={s.pickerIconWrap}
        >
          <Ionicons name={current.icon} size={16} color="#fff" />
        </LinearGradient>
        <View style={{ flex: 1 }}>
          <Text style={s.pickerLabel}>MODEL</Text>
          <Text style={s.pickerName} numberOfLines={1}>{current.name}</Text>
        </View>
        <View style={s.pickerCascade}>
          <View style={s.cascadePill}>
            <Text style={s.cascadeTxt}>{resolution}</Text>
          </View>
          <View style={s.cascadePill}>
            <Text style={s.cascadeTxt}>{duration}s</Text>
          </View>
        </View>
        <Ionicons name="chevron-down" size={18} color="#A78BFA" />
      </TouchableOpacity>

      {/* Cascading resolution + duration row */}
      <View style={s.cascadeRow}>
        <View style={{ flex: 1 }}>
          <Text style={s.cascadeLabel}>Resolution</Text>
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
        <View style={{ width: 12 }} />
        <View style={{ flex: 1.2 }}>
          <Text style={s.cascadeLabel}>Duration</Text>
          <View style={s.segRow}>
            {current.durations.map((d) => (
              <TouchableOpacity
                key={d}
                onPress={() => onDurationChange(d)}
                style={[s.segBtn, duration === d && s.segBtnActive]}
                activeOpacity={0.85}
              >
                <Text style={[s.segTxt, duration === d && s.segTxtActive]}>{d}s</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </View>

      {/* Bottom-sheet model menu */}
      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <Pressable style={s.overlay} onPress={() => setOpen(false)}>
          <Pressable style={s.sheet} onPress={(e) => e.stopPropagation()}>
            <View style={s.dragHandle} />
            <View style={s.sheetHeader}>
              <View style={{ flex: 1 }}>
                <Text style={s.sheetTitle}>Choose a model</Text>
                <Text style={s.sheetSub}>Each model has its own resolution & duration matrix.</Text>
              </View>
              <TouchableOpacity onPress={() => setOpen(false)} style={s.closeBtn}>
                <Ionicons name="close" size={20} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            <ScrollView style={{ maxHeight: 540 }} contentContainerStyle={{ paddingBottom: 30 }}>
              {MODELS.map((m) => {
                const active = m.id === value;
                const unlocked = isModelUnlocked(m, userTier);
                const comingSoon = m.comingSoonOnTiers?.includes(userTier);
                return (
                  <TouchableOpacity
                    key={m.id}
                    style={[s.modelCard, active && s.modelCardActive, !unlocked && s.modelCardLocked]}
                    activeOpacity={unlocked ? 0.85 : 1}
                    onPress={() => handleSelect(m)}
                  >
                    {/* Frosted background hint */}
                    <LinearGradient
                      colors={[m.gradient[0] + '22', m.gradient[1] + '11']}
                      start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                      style={StyleSheet.absoluteFillObject}
                    />
                    {/* Icon medallion */}
                    <LinearGradient
                      colors={m.gradient}
                      start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                      style={s.modelIcon}
                    >
                      <Ionicons name={m.icon} size={20} color="#fff" />
                    </LinearGradient>

                    {/* Content */}
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
                        <View style={s.modelChip}>
                          <Ionicons name="time" size={9} color="#FBBF24" />
                          <Text style={s.modelChipTxt}>{m.durations.map(d => d + 's').join(' · ')}</Text>
                        </View>
                      </View>
                    </View>

                    {/* Active or lock indicator */}
                    {active ? (
                      <View style={s.activeMark}>
                        <Ionicons name="checkmark" size={14} color="#0B1120" />
                      </View>
                    ) : !unlocked ? (
                      <View style={s.lockMark}>
                        <Ionicons name={comingSoon ? 'time' : 'lock-closed'} size={14} color="#FBBF24" />
                      </View>
                    ) : null}
                  </TouchableOpacity>
                );
              })}

              <Text style={s.footerHint}>
                More models like Kling, Veo, Sora & Runway are coming soon. Free models work right now.
              </Text>
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  /* Picker pill */
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

  /* Cascade row */
  cascadeRow: { flexDirection: 'row', marginTop: 12, marginBottom: 4 },
  cascadeLabel: { color: '#94A3B8', fontSize: 10, fontWeight: '900', letterSpacing: 0.8, marginBottom: 6 },
  segRow: { flexDirection: 'row', gap: 6 },
  segBtn: {
    flex: 1,
    paddingVertical: 8,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
    borderRadius: 10, alignItems: 'center',
  },
  segBtnActive: {
    backgroundColor: '#FBBF24',
    borderColor: '#FBBF24',
  },
  segTxt: { color: '#94A3B8', fontSize: 12, fontWeight: '800' },
  segTxtActive: { color: '#0B1120' },

  /* Modal */
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

  /* Model card */
  modelCard: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: 'rgba(255,255,255,0.03)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
    borderRadius: 16, padding: 12,
    marginTop: 10,
    overflow: 'hidden',
  },
  modelCardActive: {
    borderColor: '#FBBF24',
    ...Platform.select({
      web: { boxShadow: '0 6px 22px rgba(251,191,36,0.25)' as any },
      default: { shadowColor: '#FBBF24', shadowOpacity: 0.45, shadowRadius: 12, shadowOffset: { width: 0, height: 4 } },
    }),
  },
  modelCardLocked: { opacity: 0.65 },
  modelIcon: {
    width: 44, height: 44, borderRadius: 14,
    alignItems: 'center', justifyContent: 'center',
  },
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
    backgroundColor: '#FBBF24',
    alignItems: 'center', justifyContent: 'center',
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
