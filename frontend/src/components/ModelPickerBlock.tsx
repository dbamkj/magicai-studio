/**
 * ModelPickerBlock — drop-in reusable model picker block for ANY tool screen.
 *
 * Usage (in any screen):
 *
 *   import ModelPickerBlock from '../src/components/ModelPickerBlock';
 *   ...
 *   <ModelPickerBlock kind="video" />          // for video-tool screens
 *   <ModelPickerBlock kind="image" />          // for image-tool screens
 *
 * Why a block?
 *   The 11 tool screens (Talking Avatar / AI Video Gen / Motion Control /
 *   Lip Sync / AI Bg Lip Sync / Re-dub / Face Swap / Head & Body Swap /
 *   Multi Swap / Divine Transform / AI Image Gen) all need the SAME picker
 *   semantics: a label, a glass picker pill, and the bottom-sheet model
 *   menu. Wrapping it in one component means every screen is a 1-line
 *   integration.
 *
 *   The block manages its own state internally (default model id, default
 *   resolution, default duration) — the chosen model isn't yet plumbed
 *   into the per-screen generation request because backend support for the
 *   premium catalog is still pending. When backend integrations land, the
 *   `onSelect` prop can be wired through.
 */
import React, { useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAuth } from '../AuthContext';
import ModelPicker, { type ReelModelId, type ModelTier } from './ModelPicker';
import ImageModelPicker, {
  type ImageModelId, type ImageModelTier,
} from './ImageModelPicker';

type Props =
  | { kind: 'video'; defaultModel?: ReelModelId; label?: string }
  | { kind: 'image'; defaultModel?: ImageModelId; label?: string };

export default function ModelPickerBlock(props: Props) {
  const { user } = useAuth();
  const tier = (user?.subscription_tier as any) || 'free';

  if (props.kind === 'image') {
    return <ImageBlock defaultModel={props.defaultModel} label={props.label} tier={tier} />;
  }
  return <VideoBlock defaultModel={props.defaultModel} label={props.label} tier={tier} />;
}

function VideoBlock({
  defaultModel = 'kling_pro' as ReelModelId,
  label = 'AI Model',
  tier,
}: { defaultModel?: ReelModelId; label?: string; tier: ModelTier }) {
  const [modelId, setModelId] = useState<ReelModelId>(defaultModel);
  const [resolution, setResolution] = useState<'720p' | '1080p' | '4K'>('1080p');
  const [duration, setDuration] = useState<number>(10);
  return (
    <View style={s.wrap}>
      <Text style={s.label}>{label}</Text>
      <ModelPicker
        value={modelId}
        onChange={setModelId}
        resolution={resolution}
        onResolutionChange={setResolution}
        duration={duration}
        onDurationChange={setDuration}
        userTier={tier}
      />
    </View>
  );
}

function ImageBlock({
  defaultModel = 'z_image_turbo' as ImageModelId,
  label = 'Image Model',
  tier,
}: { defaultModel?: ImageModelId; label?: string; tier: ImageModelTier }) {
  const [modelId, setModelId] = useState<ImageModelId>(defaultModel);
  const [resolution, setResolution] = useState<'512' | '1024' | '2048' | '4K'>('1024');
  return (
    <View style={s.wrap}>
      <Text style={s.label}>{label}</Text>
      <ImageModelPicker
        value={modelId}
        onChange={setModelId}
        resolution={resolution}
        onResolutionChange={setResolution}
        userTier={tier}
      />
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { marginTop: 14, marginBottom: 4 },
  label: {
    color: '#94A3B8', fontSize: 11, fontWeight: '900', letterSpacing: 0.8,
    marginBottom: 8,
  },
});
