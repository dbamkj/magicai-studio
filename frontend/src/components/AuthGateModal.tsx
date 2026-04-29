/* AuthGateModal — reusable guest auth prompt.
 *
 * Presents a consistent "Log in to create magic" modal across every screen
 * that needs to block a guest action (Home, Inspiration/Trending, Marketplace,
 * Create-Wizard, etc). Previously each screen showed a raw Alert with HTTP
 * error text ("Authentication required") which was inconsistent + ugly.
 *
 * Usage:
 *   const [gateOpen, setGateOpen] = useState(false);
 *   const [gateReason, setGateReason] = useState('');
 *   // …
 *   if (!user) { setGateReason('Use this template'); setGateOpen(true); return; }
 *
 *   <AuthGateModal
 *     visible={gateOpen}
 *     onClose={() => setGateOpen(false)}
 *     reason={gateReason}   // "Use this template", "Generate concepts", …
 *     nextRoute={currentPath} // optional — where to come back after login
 *   />
 */
import React from 'react';
import {
  Modal, View, Text, TouchableOpacity, StyleSheet, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

type Props = {
  visible: boolean;
  onClose: () => void;
  /** Short human label — shown in the subtitle, e.g. "Use this template" */
  reason?: string;
  /** Where to send the user after a successful login */
  nextRoute?: string;
};

export default function AuthGateModal({ visible, onClose, reason, nextRoute }: Props) {
  const router = useRouter();

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent
      onRequestClose={onClose}
    >
      <View style={s.overlay}>
        <View style={s.card}>
          <View style={s.iconWrap}>
            <Ionicons name="sparkles" size={30} color="#FBBF24" />
          </View>
          <Text style={s.title}>Log in to create magic</Text>
          <Text style={s.sub}>
            {reason
              ? `${reason} requires a free MagiCAi account.`
              : 'Create your free MagiCAi account to unlock AI tools, Avatar Studio, templates and more.'}
          </Text>
          <TouchableOpacity
            style={s.primary}
            activeOpacity={0.88}
            onPress={() => {
              onClose();
              router.push({
                pathname: '/login',
                params: { mode: 'login', next: nextRoute || '' },
              } as any);
            }}
          >
            <Ionicons name="log-in-outline" size={18} color="#0B1120" />
            <Text style={s.primaryText}>Login</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={s.secondary}
            activeOpacity={0.85}
            onPress={() => {
              onClose();
              router.push({
                pathname: '/login',
                params: { mode: 'register', next: nextRoute || '' },
              } as any);
            }}
          >
            <Text style={s.secondaryText}>New here? Create an account</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.close} onPress={onClose} activeOpacity={0.7}>
            <Text style={s.closeText}>Maybe later</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: {
    flex: 1, justifyContent: 'center', alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.78)', paddingHorizontal: 24,
  },
  card: {
    width: '100%', maxWidth: 380,
    backgroundColor: '#1E1B4B',
    borderRadius: 22, paddingVertical: 26, paddingHorizontal: 22,
    borderWidth: 1, borderColor: 'rgba(167,139,250,0.35)',
    alignItems: 'center',
    ...Platform.select({
      web: { boxShadow: '0 20px 50px rgba(0,0,0,0.6)' as any },
      default: { shadowColor: '#000', shadowOpacity: 0.45, shadowRadius: 24, shadowOffset: { width: 0, height: 16 } },
    }),
  },
  iconWrap: {
    width: 62, height: 62, borderRadius: 31,
    backgroundColor: 'rgba(251,191,36,0.16)',
    borderWidth: 1, borderColor: 'rgba(251,191,36,0.42)',
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 14,
  },
  title: { color: '#fff', fontSize: 20, fontWeight: '900', textAlign: 'center', letterSpacing: 0.2 },
  sub: {
    color: 'rgba(203,213,225,0.85)',
    fontSize: 13.5, fontWeight: '500', textAlign: 'center',
    marginTop: 8, marginBottom: 20, lineHeight: 20,
  },
  primary: {
    width: '72%',                 // narrower button per user feedback
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#FBBF24', paddingVertical: 13, borderRadius: 14,
  },
  primaryText: { color: '#0B1120', fontSize: 15.5, fontWeight: '900', letterSpacing: 0.3 },
  secondary: {
    width: '72%', marginTop: 10,
    borderWidth: 1, borderColor: 'rgba(167,139,250,0.55)',
    paddingVertical: 12, borderRadius: 14, alignItems: 'center',
  },
  secondaryText: { color: '#C4B5FD', fontSize: 13, fontWeight: '700' },
  close: { marginTop: 14, paddingVertical: 6 },
  closeText: { color: 'rgba(148,163,184,0.8)', fontSize: 13, fontWeight: '500' },
});
