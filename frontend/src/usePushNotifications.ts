/**
 * usePushNotifications — Session 27g
 *
 * Registers the device's Expo push token with the backend (once per login)
 * and sets up a foreground-notification handler. Safe on web (no-op).
 *
 * Requires:
 *   expo-notifications, expo-device (added in Session 27g)
 *   magicai_jwt_v1 in localStorage (set by AuthContext)
 *
 * Usage in app/_layout.tsx or similar:
 *   usePushNotifications();
 */
import { useEffect, useRef } from 'react';
import { Platform, Alert } from 'react-native';
import axios from 'axios';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

export function usePushNotifications(userId?: string | null) {
  const registeredRef = useRef<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    if (Platform.OS === 'web') return;   // web = no-op (we use in-app bell instead)
    let cancelled = false;

    (async () => {
      try {
        // Skip on Expo Go (SDK 53 removed Android push notifs from Expo Go).
        // Avoids the noisy console error popup the user saw.
        try {
          const Constants = (await import('expo-constants')).default;
          if (Constants.appOwnership === 'expo') {
            // running inside Expo Go — silently no-op
            return;
          }
        } catch {}

        const Notifications = await import('expo-notifications');
        const Device = await import('expo-device');
        if (!Device.isDevice) {
          console.log('[push] not a real device — skip');
          return;
        }
        // Ask permission
        const { status: existingStatus } = await Notifications.getPermissionsAsync();
        let finalStatus = existingStatus;
        if (existingStatus !== 'granted') {
          const { status } = await Notifications.requestPermissionsAsync();
          finalStatus = status;
        }
        if (finalStatus !== 'granted') {
          console.log('[push] permission not granted');
          return;
        }
        // Get token
        const projectId = (await import('expo-constants')).default.expoConfig?.extra?.eas?.projectId
          || (await import('expo-constants')).default.easConfig?.projectId;
        const tokenRes = projectId
          ? await Notifications.getExpoPushTokenAsync({ projectId })
          : await Notifications.getExpoPushTokenAsync();
        const expoPushToken = tokenRes.data;
        if (cancelled || !expoPushToken) return;
        if (registeredRef.current === expoPushToken) return;
        // Register with backend
        const jwt = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem('magicai_jwt_v1') : null;
        if (!jwt) return;
        await axios.post(
          `${BACKEND_URL}/api/notifications/push-token`,
          { expo_push_token: expoPushToken, device: Platform.OS },
          { headers: { Authorization: `Bearer ${jwt}` }, timeout: 10000 },
        );
        registeredRef.current = expoPushToken;
        console.log('[push] registered:', expoPushToken.slice(0, 22) + '…');

        // Android notification channel
        if (Platform.OS === 'android') {
          await Notifications.setNotificationChannelAsync('default', {
            name: 'default',
            importance: Notifications.AndroidImportance.HIGH,
            vibrationPattern: [0, 250, 250, 250],
            lightColor: '#8B5CF6',
          });
        }

        // Foreground handler — show banner even when app is open
        Notifications.setNotificationHandler({
          handleNotification: async () => ({
            shouldShowBanner: true,
            shouldShowList: true,
            shouldPlaySound: true,
            shouldSetBadge: true,
          }),
        });
      } catch (e) {
        console.warn('[push] setup failed:', e);
      }
    })();

    return () => { cancelled = true; };
  }, [userId]);
}
