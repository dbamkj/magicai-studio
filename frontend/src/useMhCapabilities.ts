import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

export type MhModel = {
  id: string; label: string; enabled: boolean;
  credits_per_sec?: number; credits_per_image?: number; min_cost?: number;
  default?: boolean; desc?: string;
};

export type MhResolution = { id: string; label: string; enabled: boolean; note?: string };

export type MhFeature = {
  models?: MhModel[];
  duration_options: number[] | null;
  resolution_options: MhResolution[];
  flat_cost?: number;
  credits_per_sec?: number;
  min_cost?: number;
  desc?: string;
};

type MhModelsResponse = {
  quality_tiers: any[];
  min_billed_seconds: number;
  resolutions: MhResolution[];
  features: Record<string, MhFeature>;
  notice?: string;
};

// Simple in-memory cache shared across all hook instances for the app session.
let _cache: MhModelsResponse | null = null;
let _inflight: Promise<MhModelsResponse | null> | null = null;

async function fetchMh(): Promise<MhModelsResponse | null> {
  if (_cache) return _cache;
  if (_inflight) return _inflight;
  _inflight = axios.get(`${BACKEND_URL}/api/mh-models`, { timeout: 15000 })
    .then(r => { _cache = r.data; return r.data; })
    .catch(() => null)
    .finally(() => { _inflight = null; });
  return _inflight;
}

/** Hook that returns the MH capabilities for a given feature
 *  (text_to_video / image_to_video / video_to_video / ai_image_generator /
 *  face_swap_photo / face_swap_video / lip_sync / talking_avatar).
 *
 *  For each feature the hook returns:
 *   - modelsEnabled: list of selectable models (filtered to enabled=true)
 *   - durationOptions: list of integer seconds the picker should expose
 *   - resolutionOptions: list of {id,label,enabled,note} for resolution picker
 *   - minBilled: MH min billed seconds (usually 5)
 *   - costPerSec for the picked model
 *   - minCost for the picked model
 */
export function useMhCapabilities(feature: string, modelId?: string) {
  const [data, setData] = useState<MhModelsResponse | null>(_cache);
  useEffect(() => {
    if (!data) fetchMh().then(d => d && setData(d));
  }, [data]);

  const featData = data?.features?.[feature];
  const modelsEnabled = useMemo(() => (featData?.models || []).filter(m => m.enabled !== false), [featData]);
  const chosen: MhModel | undefined = useMemo(
    () => modelsEnabled.find(m => m.id === modelId) || modelsEnabled.find(m => m.default) || modelsEnabled[0],
    [modelsEnabled, modelId],
  );
  const durationOptions = featData?.duration_options || null;
  const resolutionOptions = (featData?.resolution_options || data?.resolutions || []).filter(r => r.enabled !== false);
  const costPerSec = chosen?.credits_per_sec ?? featData?.credits_per_sec;
  const minCost = chosen?.min_cost ?? featData?.min_cost ?? featData?.flat_cost;

  return {
    ready: !!data,
    feature: featData,
    modelsEnabled,
    chosenModel: chosen,
    durationOptions,
    resolutionOptions,
    minBilled: data?.min_billed_seconds ?? 5,
    costPerSec,
    minCost,
    notice: data?.notice,
  };
}
