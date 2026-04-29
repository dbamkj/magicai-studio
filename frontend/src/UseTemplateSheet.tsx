import React from 'react';
import { View, Text, Modal, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export type TemplateForRouting = {
  id: string;
  title?: string;
  category?: string;
  hook_text?: string | null;
  lyrics?: string | null;
  thumbnail_url?: string | null;
  preview_url?: string | null;
  voice_id?: string | null;
  voice_style?: string | null;
  motion?: string | null;
  sound_effect?: string | null;
  aspect_ratio?: string | null;
  duration?: number | null;
};

export type Destination = {
  id: string;
  screen: string;
  icon: string;
  label: string;
  desc: string;
  costBadge: { text: string; color: 'mh' | 'instant' | 'flat' };
  build: (t: TemplateForRouting) => Record<string, any>;
};

/** Figure out which destination tools a template is compatible with. */
export function buildDestinations(t: TemplateForRouting): Destination[] {
  const hasText = !!(t.hook_text || t.lyrics);
  const hasMedia = !!(t.preview_url || t.thumbnail_url);
  const list: Destination[] = [];

  // Motion Control — works for ALL templates (uses thumbnail or user upload).
  list.push({
    id: 'motion',
    screen: '/motion-control',
    icon: 'move',
    label: 'Motion Control',
    desc: 'Apply Ken-Burns / zoom / pan on a photo. FFmpeg only.',
    costBadge: { text: '⚡ Free', color: 'instant' },
    build: (tpl) => ({
      motion: tpl.motion || 'ken_burns',
      aspect_ratio: tpl.aspect_ratio || '9:16',
      duration: tpl.duration || 5,
      thumbnail_url: tpl.thumbnail_url,
      source_label: tpl.title,
    }),
  });

  // AI Video Gen — always available (text-to-video fallback or image-to-video
  // if thumbnail is present)
  list.push({
    id: 'videogen',
    screen: '/videogen',
    icon: 'film',
    label: 'AI Video Gen',
    desc: hasMedia
      ? 'Generate new cinematic video · prompt + voice + SFX copied'
      : 'Text → Video · prompt + voice + SFX copied',
    costBadge: { text: '🪙 Credits', color: 'mh' },
    build: (tpl) => ({
      voice_id: tpl.voice_id,
      voice_style: tpl.voice_style,
      aspect_ratio: tpl.aspect_ratio,
      duration: tpl.duration,
      prompt: tpl.hook_text || tpl.title,
      lyrics: tpl.lyrics || undefined,
      sound_effect: tpl.sound_effect || undefined,
      motion: tpl.motion || undefined,
    }),
  });

  // Story Mode — if the template has narrative text, user can expand it into
  // a 3-scene story
  if (hasText) {
    list.push({
      id: 'story',
      screen: '/story',
      icon: 'book',
      label: 'Story Mode',
      desc: 'Expand as a 3-scene cinematic narrative.',
      costBadge: { text: '🪙 Flat 80', color: 'flat' },
      build: (tpl) => ({
        voice_id: tpl.voice_id,
        voice_style: tpl.voice_style,
        aspect_ratio: tpl.aspect_ratio,
        hook: tpl.hook_text,
      }),
    });
  }

  // Talking Avatar — works best when there's a script (hook_text) + portrait
  if (hasText && hasMedia) {
    list.push({
      id: 'avatar',
      screen: '/avatar',
      icon: 'person',
      label: 'Talking Avatar',
      desc: 'Make a portrait lip-sync the hook text.',
      costBadge: { text: '🪙 Credits', color: 'mh' },
      build: (tpl) => ({
        script: tpl.hook_text,
        voice_id: tpl.voice_id,
        voice_style: tpl.voice_style,
        aspect_ratio: tpl.aspect_ratio,
        thumbnail_url: tpl.thumbnail_url,
      }),
    });
  }

  // Lip Sync — works for BOTH videos (ref_video_plus_images mode) and static
  // images (images_only mode). The lipsync screen decides which mode to use
  // based on whether preview_url (video) is present.
  if (hasText && hasMedia) {
    list.push({
      id: 'lipsync',
      screen: '/lipsync',
      icon: 'mic',
      label: 'Lip Sync',
      desc: t.preview_url
        ? 'Use the template video as reference · auto-prefills ref + character'
        : 'Use the template photo · auto-prefills character image',
      costBadge: { text: '🪙 Credits', color: 'mh' },
      build: (tpl) => ({
        // Signal to lipsync screen what auto-setup to do
        template_preview_url: tpl.preview_url,
        template_thumbnail_url: tpl.thumbnail_url,
        mode: tpl.preview_url ? 'ref_video_plus_images' : 'images_only',
        dialogue_lines: tpl.hook_text
          ? [{ character_index: 0, text: tpl.hook_text }]
          : undefined,
        voice_style: tpl.voice_style,
        aspect_ratio: tpl.aspect_ratio,
      }),
    });
  }

  return list;
}

type Props = {
  visible: boolean;
  template: TemplateForRouting | null;
  onClose: () => void;
  onPick: (dest: Destination) => void;
};

/** Bottom-sheet modal presenting a list of compatible tools for the chosen
 *  template. Lets the user decide how to use it rather than us auto-routing. */
export default function UseTemplateSheet({ visible, template, onClose, onPick }: Props) {
  const dests = template ? buildDestinations(template) : [];
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity style={s.backdrop} activeOpacity={1} onPress={onClose} />
      <View style={s.sheet}>
        <View style={s.handleBar} />
        <View style={s.header}>
          <View style={{ flex: 1 }}>
            <Text style={s.title}>Use this template in…</Text>
            {!!template?.title && <Text style={s.sub} numberOfLines={1}>{template.title}</Text>}
          </View>
          <TouchableOpacity onPress={onClose} style={s.closeBtn} accessibilityLabel="Close">
            <Ionicons name="close" size={22} color="#94A3B8" />
          </TouchableOpacity>
        </View>
        <ScrollView contentContainerStyle={{ paddingBottom: 24 }} showsVerticalScrollIndicator={false}>
          {dests.map(d => (
            <TouchableOpacity
              key={d.id}
              style={s.row}
              onPress={() => onPick(d)}
              activeOpacity={0.82}
            >
              <View style={s.iconBubble}>
                <Ionicons name={d.icon as any} size={22} color="#FBBF24" />
              </View>
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <Text style={s.rowLabel}>{d.label}</Text>
                  <View style={[s.badge, badgeColor(d.costBadge.color)]}>
                    <Text style={[s.badgeText, badgeTextColor(d.costBadge.color)]}>{d.costBadge.text}</Text>
                  </View>
                </View>
                <Text style={s.rowDesc}>{d.desc}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color="#475569" />
            </TouchableOpacity>
          ))}
          {dests.length === 0 && (
            <Text style={s.empty}>No compatible tools for this template.</Text>
          )}
        </ScrollView>
      </View>
    </Modal>
  );
}

const badgeColor = (c: 'mh' | 'instant' | 'flat') => {
  if (c === 'instant') return { backgroundColor: 'rgba(16,185,129,0.15)', borderColor: 'rgba(16,185,129,0.5)' };
  if (c === 'flat') return { backgroundColor: 'rgba(251,191,36,0.15)', borderColor: 'rgba(251,191,36,0.5)' };
  return { backgroundColor: 'rgba(249,115,22,0.15)', borderColor: 'rgba(249,115,22,0.5)' };
};
const badgeTextColor = (c: 'mh' | 'instant' | 'flat') => {
  if (c === 'instant') return { color: '#6EE7B7' };
  if (c === 'flat') return { color: '#FBBF24' };
  return { color: '#FDBA74' };
};

const s = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(15,23,42,0.72)' },
  sheet: {
    position: 'absolute', left: 0, right: 0, bottom: 0,
    backgroundColor: '#1E293B',
    borderTopLeftRadius: 22, borderTopRightRadius: 22,
    padding: 18, paddingBottom: 28,
    borderTopWidth: 1, borderTopColor: 'rgba(167,139,250,0.25)',
    maxHeight: '85%',
  },
  handleBar: { alignSelf: 'center', width: 44, height: 4, borderRadius: 2, backgroundColor: '#475569', marginBottom: 12 },
  header: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 12 },
  title: { color: '#F1F5F9', fontSize: 18, fontWeight: '800' },
  sub: { color: '#94A3B8', fontSize: 12, marginTop: 3 },
  closeBtn: { padding: 6, marginLeft: 6 },
  row: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingVertical: 12, paddingHorizontal: 8,
    borderRadius: 12, marginBottom: 8,
    backgroundColor: 'rgba(30,41,59,0.6)',
    borderWidth: 1, borderColor: 'rgba(71,85,105,0.6)',
  },
  iconBubble: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: 'rgba(251,191,36,0.14)',
    borderWidth: 1, borderColor: 'rgba(251,191,36,0.35)',
    alignItems: 'center', justifyContent: 'center',
  },
  rowLabel: { color: '#F1F5F9', fontSize: 15, fontWeight: '800' },
  rowDesc: { color: '#94A3B8', fontSize: 12, marginTop: 3, lineHeight: 17 },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999, borderWidth: 1 },
  badgeText: { fontSize: 10, fontWeight: '900', letterSpacing: 0.3 },
  empty: { color: '#64748B', fontSize: 13, textAlign: 'center', paddingVertical: 30 },
});
