import { Platform } from 'react-native';
import axios from 'axios';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

/**
 * Upload an image file to the backend, handling both web and native platforms.
 * On web, converts the URI to a Blob before uploading.
 * On native, uses the React Native FormData format.
 */
export async function uploadImageFile(
  uri: string,
  endpoint: string = '/api/upload-face-image',
  timeout: number = 30000
): Promise<any> {
  const fd = new FormData();
  const fileName = uri.split('/').pop() || 'image.jpg';
  const match = /\.(\w+)$/.exec(fileName);
  const mimeType = match ? `image/${match[1]}` : 'image/jpeg';

  if (Platform.OS === 'web') {
    // Web: fetch the URI (blob: or data: URL) and convert to File
    const response = await fetch(uri);
    const blob = await response.blob();
    const file = new File([blob], fileName, { type: mimeType });
    fd.append('file', file);
  } else {
    // Native: use React Native's FormData format
    fd.append('file', { uri, name: fileName, type: mimeType } as any);
  }

  const res = await axios.post(`${BACKEND_URL}${endpoint}`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout,
  });

  return res.data;
}

/**
 * Upload a video file to the backend, handling both web and native platforms.
 */
export async function uploadVideoFile(
  uri: string,
  timeout: number = 120000
): Promise<any> {
  const fd = new FormData();
  const fileName = uri.split('/').pop() || 'video.mp4';
  const match = /\.(\w+)$/.exec(fileName);
  const mimeType = match ? `video/${match[1]}` : 'video/mp4';

  if (Platform.OS === 'web') {
    const response = await fetch(uri);
    const blob = await response.blob();
    const file = new File([blob], fileName, { type: mimeType });
    fd.append('file', file);
  } else {
    fd.append('file', { uri, name: fileName, type: mimeType } as any);
  }

  const res = await axios.post(`${BACKEND_URL}/api/upload-video`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout,
  });

  return res.data;
}
