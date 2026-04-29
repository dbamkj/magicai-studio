/* downloadHelper.ts — Cross-platform asset download helper for MagiCAi.
 *
 * Web:    Forces a real <a download> click so the browser saves the file
 *         (image / video / audio) to the user's Downloads folder.
 * Native: Downloads to a cache dir via expo-file-system, then writes to the
 *         device's Photos/Videos gallery via expo-media-library (asks for
 *         permission once, caches it).
 *
 * Usage:
 *   import { saveAssetToDevice } from '../src/downloadHelper';
 *   await saveAssetToDevice(url, 'magicai_cartoon_xxx.png', 'image');
 */
import { Alert, Platform } from 'react-native';

export type AssetKind = 'image' | 'video' | 'audio';

/**
 * Try to save the asset at `url` to the user's device.
 * Returns `true` on success, `false` (and shows an Alert) on failure.
 */
export async function saveAssetToDevice(
  url: string,
  fileName: string,
  kind: AssetKind = 'image',
): Promise<boolean> {
  if (!url) {
    Alert.alert('Nothing to save', 'No file URL was provided.');
    return false;
  }

  // ---------- WEB ----------
  if (Platform.OS === 'web') {
    try {
      // Fetch as blob first (works around CORS that blocks <a download> on
      // cross-origin URLs that don't return Content-Disposition).
      const resp = await fetch(url, { credentials: 'omit' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const blobUrl = (window as any).URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = blobUrl;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      // Clean up after a tick
      setTimeout(() => {
        try { document.body.removeChild(a); } catch (_e) {}
        try { (window as any).URL.revokeObjectURL(blobUrl); } catch (_e) {}
      }, 1500);
      return true;
    } catch (err: any) {
      // Fallback: open in new tab so user can right-click → save
      try { (window as any).open(url, '_blank'); } catch (_e) {}
      Alert.alert(
        'Download',
        `Could not auto-save (${String(err?.message || err)}). The asset opened in a new tab — long-press or right-click to save it.`,
      );
      return false;
    }
  }

  // ---------- NATIVE (iOS / Android) ----------
  try {
    const FileSystem = await import('expo-file-system');
    const MediaLibrary = await import('expo-media-library');

    // Ask for permission (cached after first grant).
    // `writeOnly: true` skips the AUDIO permission request that some
    // expo-media-library versions trigger by default — this avoids the
    // "READ_MEDIA_AUDIO not declared" Android crash on devices where the
    // host app didn't request audio access.
    let perm: any;
    try {
      perm = await (MediaLibrary as any).requestPermissionsAsync(true);
    } catch (_e) {
      // Older SDKs don't accept the writeOnly flag — fall back.
      perm = await MediaLibrary.requestPermissionsAsync();
    }
    if (!perm?.granted) {
      Alert.alert(
        'Permission needed',
        'MagiCAi needs Photos / Media access to save this file to your gallery. Please enable it in settings.',
      );
      return false;
    }

    // Download to cache.
    const cacheDir =
      (FileSystem as any).cacheDirectory ||
      (FileSystem as any).documentDirectory ||
      '';
    const safeName = fileName.replace(/[^\w.\-]/g, '_');
    const localUri = `${cacheDir}${safeName}`;
    const dl = await (FileSystem as any).downloadAsync(url, localUri);
    if (!dl?.uri) throw new Error('Download returned no URI');

    // Save into the gallery's MagiCAi album.
    const asset = await MediaLibrary.createAssetAsync(dl.uri);
    try {
      const albumName = 'MagiCAi';
      const existing = await MediaLibrary.getAlbumAsync(albumName);
      if (existing) {
        await MediaLibrary.addAssetsToAlbumAsync([asset], existing, false);
      } else {
        await MediaLibrary.createAlbumAsync(albumName, asset, false);
      }
    } catch (_e) {
      // Album write may fail on some Android versions — asset is still in
      // the gallery, so we treat that as success.
    }

    Alert.alert(
      kind === 'video' ? 'Video saved' : kind === 'audio' ? 'Audio saved' : 'Image saved',
      'Saved to your gallery in the "MagiCAi" album.',
    );
    return true;
  } catch (err: any) {
    Alert.alert(
      'Save failed',
      `Could not save to gallery: ${String(err?.message || err)}`,
    );
    return false;
  }
}

/**
 * Generate a sensible default filename for a given asset URL.
 * Falls back to "magicai_{kind}_{timestamp}.{ext}" if the URL has no name.
 */
export function suggestFileName(url: string, kind: AssetKind = 'image'): string {
  try {
    const last = url.split('?')[0].split('/').pop() || '';
    if (last && /\.[a-zA-Z0-9]{2,5}$/.test(last)) {
      return last;
    }
  } catch (_e) {}
  const ext = kind === 'video' ? 'mp4' : kind === 'audio' ? 'mp3' : 'png';
  const ts = Date.now();
  return `magicai_${kind}_${ts}.${ext}`;
}
