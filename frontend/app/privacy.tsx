/**
 * /privacy — DPDPA / GDPR Self-Service Privacy Center (Session 36)
 *
 * Lets a signed-in user:
 *   1. Export ALL their data (DSAR Article 15 / DPDPA Article 11)
 *   2. Permanently delete their account (Right to Erasure)
 *
 * Both flows hit the new POST /api/account/* endpoints created in Sprint 2.
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  Alert, Platform, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';
import { useAuth } from '../src/AuthContext';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export default function PrivacyCenter() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [exportResult, setExportResult] = useState<any | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  // Cross-platform alert — Alert.alert is a no-op on RN-Web, so we wire a
  // window.alert fallback so the user gets feedback on every platform.
  const crossAlert = (title: string, message: string) => {
    if (Platform.OS === 'web' && typeof window !== 'undefined' && window.alert) {
      window.alert(`${title}\n\n${message}`);
    } else {
      Alert.alert(title, message);
    }
  };

  const onExport = async () => {
    try {
      setExporting(true);
      setExportError(null);
      const token = await AsyncStorage.getItem('magicai_jwt_v1');
      const r = await axios.get(`${BACKEND_URL}/api/account/export-data`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = r.data || {};
      setExportResult(data.counts || {});
      crossAlert(
        'Your data is ready',
        `We collected:\n` +
        `• ${data.counts?.projects ?? 0} video projects\n` +
        `• ${data.counts?.audit_logs ?? 0} audit logs\n` +
        `• ${data.counts?.waitlist_entries ?? 0} waitlist entries\n` +
        `• ${data.counts?.notifications ?? 0} notifications\n\n` +
        `Per DPDPA 2023 / GDPR Art. 15, you have the right to receive this data.`,
      );
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Unknown error';
      setExportError(msg);
      crossAlert('Export failed', msg);
    } finally {
      setExporting(false);
    }
  };

  const onDelete = async () => {
    Alert.alert(
      'Delete account permanently?',
      'This cannot be undone. Your account will be anonymized and your subscription cancelled. ' +
      'We retain anonymized audit logs as required by law (DPDPA Art. 7(f)).',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete forever',
          style: 'destructive',
          onPress: async () => {
            try {
              setDeleting(true);
              const token = await AsyncStorage.getItem('magicai_jwt_v1');
              await axios.post(
                `${BACKEND_URL}/api/account/delete-account`, {},
                { headers: { Authorization: `Bearer ${token}` } },
              );
              await logout();
              Alert.alert(
                'Account deleted',
                'Your account has been permanently deleted. You will now be logged out.',
                [{ text: 'OK', onPress: () => router.replace('/login' as any) }],
              );
            } catch (e: any) {
              Alert.alert('Deletion failed', e?.response?.data?.detail || e?.message || 'Unknown error');
            } finally {
              setDeleting(false);
            }
          },
        },
      ],
    );
  };

  return (
    <View style={styles.root}>
      <AuroraBackground />
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <GlassHeader
          icon="shield-half"
          title="Privacy & My Data"
          subtitle="DPDPA 2023 · GDPR baseline"
          onBack={() => router.back()}
        />
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 120 }}
          showsVerticalScrollIndicator={false}
        >
          {/* Intro */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Ionicons name="information-circle" size={20} color="#7afcff" />
              <Text style={styles.cardTitle}>Your data, your rights</Text>
            </View>
            <Text style={styles.cardBody}>
              Under India's Digital Personal Data Protection Act 2023 (DPDPA) and
              the GDPR baseline we follow, you have full control over your data.
              {'\n\n'}
              You can export everything we hold about you, or permanently delete
              your account at any time.
            </Text>
          </View>

          {/* Export */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Ionicons name="download" size={20} color="#7affc7" />
              <Text style={styles.cardTitle}>Export my data</Text>
            </View>
            <Text style={styles.cardBody}>
              Get a JSON copy of your profile, video projects, notifications,
              and audit log entries. Useful for backup or transferring to
              another service.
            </Text>
            <TouchableOpacity onPress={onExport} disabled={exporting} activeOpacity={0.85}>
              <LinearGradient
                colors={['#22d3ee', '#7afcff']}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                style={styles.cta}
              >
                {exporting ? (
                  <ActivityIndicator color="#0a0418" />
                ) : (
                  <>
                    <Ionicons name="cloud-download" size={18} color="#0a0418" />
                    <Text style={[styles.ctaText, { color: '#0a0418' }]}>Export my data</Text>
                  </>
                )}
              </LinearGradient>
            </TouchableOpacity>
            {exportResult && (
              <Text style={styles.exportSummary}>
                ✓ Last export: {exportResult.projects ?? 0} projects · {exportResult.audit_logs ?? 0} audit rows
              </Text>
            )}
          </View>

          {/* Delete */}
          <View style={[styles.card, styles.dangerCard]}>
            <View style={styles.cardHeader}>
              <Ionicons name="warning" size={20} color="#EF4444" />
              <Text style={[styles.cardTitle, { color: '#EF4444' }]}>Delete my account</Text>
            </View>
            <Text style={styles.cardBody}>
              Permanently delete your account, subscription, and all associated
              data. Anonymized audit logs are kept as required by law.
              {'\n\n'}
              <Text style={{ color: '#FCA5A5' }}>This cannot be undone.</Text>
            </Text>
            <TouchableOpacity onPress={onDelete} disabled={deleting} activeOpacity={0.85}>
              <View style={[styles.cta, styles.dangerCta]}>
                {deleting ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <>
                    <Ionicons name="trash" size={18} color="#fff" />
                    <Text style={styles.ctaText}>Delete account forever</Text>
                  </>
                )}
              </View>
            </TouchableOpacity>
          </View>

          {/* Links */}
          <View style={styles.linksRow}>
            <TouchableOpacity onPress={() => Linking.openURL('https://www.meity.gov.in/sites/default/files/2023-08/The Digital Personal Data Protection Act, 2023.pdf').catch(() => {})}>
              <Text style={styles.link}>DPDPA 2023 (PDF)</Text>
            </TouchableOpacity>
            <Text style={{ color: '#475569' }}>·</Text>
            <TouchableOpacity onPress={() => Linking.openURL('https://gdpr-info.eu/').catch(() => {})}>
              <Text style={styles.link}>GDPR Reference</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#070314' },
  card: {
    marginTop: 14, padding: 16, borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
  },
  dangerCard: {
    borderColor: 'rgba(239,68,68,0.40)',
    backgroundColor: 'rgba(239,68,68,0.06)',
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  cardTitle: { color: '#fff', fontSize: 16, fontWeight: '800', letterSpacing: 0.2 },
  cardBody: { color: '#cbd2e8', fontSize: 13, lineHeight: 19, marginBottom: 12 },
  cta: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    paddingVertical: 12, borderRadius: 12,
  },
  dangerCta: { backgroundColor: '#EF4444' },
  ctaText: { color: '#fff', fontSize: 14, fontWeight: '800' },
  exportSummary: { color: '#7affc7', fontSize: 12, marginTop: 10, textAlign: 'center' },
  linksRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 10, marginTop: 18,
  },
  link: { color: '#7afcff', fontSize: 12, fontWeight: '600' },
});
