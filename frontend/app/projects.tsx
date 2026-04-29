import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, FlatList,
  RefreshControl, Alert, ActivityIndicator, Linking, Modal, ScrollView,
  Share as RNShare, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as FileSystem from 'expo-file-system';
import * as MediaLibrary from 'expo-media-library';
import axios from 'axios';
import { useAuth } from '../src/AuthContext';
import { useTheme } from '../src/ThemeContext';
import { useTierGuard } from '../src/useTierGuard';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';
import { LinearGradient } from 'expo-linear-gradient';
import FreeVsProToggle from '../src/components/FreeVsProToggle';
import BottomTabBar from '../src/components/BottomTabBar';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

interface Segment { index: number; character_index: number; text: string; result_url: string; }
interface Project {
  id: string; name: string; type: string; status: string; result_url?: string;
  result_segments?: Segment[]; error_message?: string; progress?: number;
  created_at: string; aspect_ratio?: string; face_count?: number; sound_effect?: string;
  // Sprint 1: versioning
  parent_id?: string | null;
  version?: number;
  action?: 'original' | 'edit' | 'recreate' | 'regenerate';
  input_payload?: any;
  endpoint?: string;
}

const IMAGE_TYPES = ['headswap', 'bodyswap', 'imagegen', 'faceswap_img', 'multi_bodyswap', 'multi_headswap'];
const isImageType = (type: string) => IMAGE_TYPES.includes(type);
const typeLabel = (t: string) => {
  const map: Record<string, string> = { lipsync: 'Lip Sync', faceswap: 'Face Swap', faceswap_img: 'Face Swap (Image)', headswap: 'Head Swap', bodyswap: 'Body Swap', imagegen: 'AI Image', videogen: 'AI Video', redub: 'Re-dub', multi_bodyswap: 'Multi Body Swap', multi_headswap: 'Multi Head Swap' };
  return map[t] || t;
};

export default function ProjectsScreen() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const tier = useTierGuard();
  const { isDark } = useTheme();
  const titleColor = isDark ? '#FFFFFF' : '#0F0C29';
  const [projects, setProjects] = useState<Project[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [detailModal, setDetailModal] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [merging, setMerging] = useState(false);
  // Sprint 1 — versioning state
  const [versions, setVersions] = useState<Project[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [rerunning, setRerunning] = useState<null | 'recreate' | 'regenerate'>(null);

  // Load versions family whenever a project is selected
  useEffect(() => {
    if (!selectedProject) { setVersions([]); return; }
    (async () => {
      try {
        setVersionsLoading(true);
        const r = await axios.get(`${BACKEND_URL}/api/project/${selectedProject.id}/versions`);
        setVersions(r.data?.versions || []);
      } catch (e) { setVersions([selectedProject]); }
      finally { setVersionsLoading(false); }
    })();
  }, [selectedProject?.id]);

  const switchToVersion = (v: Project) => {
    setSelectedProject(v);
  };

  const doRerun = async (action: 'recreate' | 'regenerate') => {
    if (!selectedProject) return;
    try {
      setRerunning(action);
      const r = await axios.post(`${BACKEND_URL}/api/project/${selectedProject.id}/rerun`, { action });
      // Reload all projects so the new version appears in the list
      await fetchProjects();
      // Fetch versions again so the chips update
      try {
        const vr = await axios.get(`${BACKEND_URL}/api/project/${selectedProject.id}/versions`);
        setVersions(vr.data?.versions || []);
      } catch (e) {}
      Alert.alert(
        action === 'recreate' ? 'Recreating…' : 'Regenerating…',
        `New version v${r.data.version} started. Check back in ~1-2 minutes.`,
      );
    } catch (e: any) {
      Alert.alert('Failed', e.response?.data?.detail || String(e));
    } finally { setRerunning(null); }
  };

  const doEdit = () => {
    if (!selectedProject) return;
    const ep = selectedProject.endpoint || '';
    const payload = selectedProject.input_payload || {};
    // Map each endpoint to its creation screen path + pass inputs via query
    let screen = '';
    if (ep.endsWith('/generate-video')) screen = '/videogen';
    else if (ep.endsWith('/generate-image')) screen = '/imagegen';
    else if (ep.endsWith('/create-image-to-video')) screen = '/videogen';
    else if (ep.endsWith('/create-video-to-video')) screen = '/videogen';
    else if (ep.endsWith('/create-multishot')) screen = '/multishot';
    else if (ep.endsWith('/create-lipsync')) screen = '/lipsync';
    else if (ep.endsWith('/create-faceswap')) screen = '/faceswap';
    else if (ep.endsWith('/create-headswap')) screen = '/headswap';
    else if (ep.endsWith('/create-bodyswap')) screen = '/headswap';
    else if (ep.endsWith('/create-multi-swap')) screen = '/multiswap';
    else if (ep.endsWith('/create-talking-avatar')) screen = '/avatar';
    else if (ep.endsWith('/animate-image')) screen = '/avatar';  // re-use avatar screen (motion-only works too)
    else {
      Alert.alert('Not editable', 'This project type doesn\'t support Edit yet. Try Recreate/Regenerate instead.');
      return;
    }
    setDetailModal(false);
    router.push({
      pathname: screen as any,
      params: {
        edit_of: selectedProject.id,
        prefill: JSON.stringify(payload),
      },
    });
  };

  const fetchProjects = async () => {
    try { const r = await axios.get(`${BACKEND_URL}/api/projects`); setProjects(r.data); }
    catch (e) {}
    finally { setLoading(false); setRefreshing(false); }
  };
  useEffect(() => {
    fetchProjects();
    const i = setInterval(fetchProjects, 5000);
    return () => clearInterval(i);
  }, []);
  const onRefresh = useCallback(() => { setRefreshing(true); fetchProjects(); }, []);

  const handleProjectPress = async (p: Project) => {
    try { const r = await axios.get(`${BACKEND_URL}/api/project/${p.id}`); setSelectedProject(r.data); setDetailModal(true); }
    catch (e) { Alert.alert('Error', 'Failed to load'); }
  };

  const resolveUrl = (url: string) => {
    if (!url) return url;
    if (url.startsWith('/api/')) return `${BACKEND_URL}${url}`;
    return url;
  };
  const openResult = (url: string) => Linking.openURL(resolveUrl(url)).catch(() => Alert.alert('Error', 'Could not open'));

  const downloadResult = async (url: string, name: string, isImage: boolean) => {
    // 🔒 Tier gate — Free users see Upgrade alert; Starter+ get the download
    if (!tier.requireFeature('download_to_gallery', 'Asset download to gallery')) {
      return;
    }
    try {
      setDownloading(true);
      const resolvedUrl = resolveUrl(url);
      const fn = `${name.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.${isImage ? 'png' : 'mp4'}`;

      // ===== WEB branch =====
      if (Platform.OS === 'web') {
        try {
          // Try native fetch + blob download (works for CORS-enabled URLs)
          const proxyUrl = `${BACKEND_URL}/api/download-video?url=${encodeURIComponent(resolvedUrl)}`;
          const resp = await fetch(proxyUrl);
          if (!resp.ok) throw new Error(`Proxy fetch failed ${resp.status}`);
          const blob = await resp.blob();
          if (blob.size < 100) throw new Error('Empty file');
          const href = URL.createObjectURL(blob);
          // Trigger browser download
          const a = document.createElement('a');
          a.href = href; a.download = fn; a.rel = 'noopener';
          document.body.appendChild(a); a.click(); a.remove();
          setTimeout(() => URL.revokeObjectURL(href), 10000);
          Alert.alert('Downloaded!', `${isImage ? 'Image' : 'Video'} downloaded to your device.`);
        } catch (e: any) {
          // Fallback: open URL in new tab
          try { window.open(resolvedUrl, '_blank', 'noopener,noreferrer'); } catch {}
          Alert.alert('Browser Download', `Opened in new tab. Right-click → Save ${isImage ? 'Image' : 'Video'} As...`);
        }
        return;
      }

      // ===== NATIVE branch =====
      if (isImage) {
        // For images, use MediaLibrary save on native
        const { status } = await MediaLibrary.requestPermissionsAsync();
        if (status !== 'granted') { Alert.alert('Permission needed', 'Please enable photo library access to save images.'); return; }
        const fileUri = `${FileSystem.documentDirectory}${fn}`;
        const res = await FileSystem.downloadAsync(resolvedUrl, fileUri);
        if (res.status >= 200 && res.status < 400) {
          const info = await FileSystem.getInfoAsync(res.uri);
          if (!info.exists || (info.size || 0) < 100) throw new Error('Empty download');
          const asset = await MediaLibrary.createAssetAsync(res.uri);
          try { await MediaLibrary.createAlbumAsync('MagiCAi Studio', asset, false); } catch (e) {}
          Alert.alert('Saved!', 'Image saved to Photos → MagiCAi Studio album.');
          return;
        }
        throw new Error(`HTTP ${res.status}`);
      }

      // Video save
      const { status } = await MediaLibrary.requestPermissionsAsync();
      if (status !== 'granted') { Alert.alert('Permission needed', 'Please enable photo library access to save videos.'); return; }
      const fileUri = `${FileSystem.documentDirectory}${fn}`;
      let savedAsset: any = null;
      try {
        const res = await FileSystem.downloadAsync(resolvedUrl, fileUri);
        if (res.status >= 200 && res.status < 400) {
          const info = await FileSystem.getInfoAsync(res.uri);
          if (info.exists && (info.size || 0) > 1000) {
            savedAsset = await MediaLibrary.createAssetAsync(res.uri);
          }
        }
      } catch (e) { /* fall through to proxy */ }

      if (!savedAsset) {
        // Try backend proxy (avoids Magic Hour CDN CORS issues)
        const proxyUrl = `${BACKEND_URL}/api/download-video?url=${encodeURIComponent(resolvedUrl)}`;
        const proxyUri = fileUri + '_p.mp4';
        const res2 = await FileSystem.downloadAsync(proxyUrl, proxyUri);
        if (res2.status < 200 || res2.status >= 400) throw new Error(`Proxy HTTP ${res2.status}`);
        const info2 = await FileSystem.getInfoAsync(res2.uri);
        if (!info2.exists || (info2.size || 0) < 1000) throw new Error('Downloaded file empty');
        savedAsset = await MediaLibrary.createAssetAsync(res2.uri);
      }

      try { await MediaLibrary.createAlbumAsync('MagiCAi Studio', savedAsset, false); } catch (e) {}
      Alert.alert('Saved!', 'Video saved to Photos → MagiCAi Studio album.');
    } catch (e: any) {
      console.error('Download failed:', e);
      Alert.alert('Save Failed', `Could not save to gallery: ${e?.message || e}. You can try Open/Share as a workaround.`);
    } finally { setDownloading(false); }
  };

  const deleteProject = async (id: string) => {
    try { await axios.delete(`${BACKEND_URL}/api/project/${id}`); setDetailModal(false); fetchProjects(); }
    catch (e) { Alert.alert('Error'); }
  };

  const shareResult = async (url: string, projectName: string, isImage: boolean) => {
    try {
      await RNShare.share({
        message: `Check out my ${isImage ? 'image' : 'video'} "${projectName}" created with MagiCAi Studio!\n\n${url}`,
        url: url,
        title: projectName,
      });
    } catch (e) {}
  };

  const mergeSegments = async (projectId: string) => {
    try {
      setMerging(true);
      const r = await axios.post(`${BACKEND_URL}/api/merge-segments/${projectId}`);
      Alert.alert('Merged!', 'All segments merged into one video.', [
        { text: 'Open', onPress: () => openResult(`${BACKEND_URL}${r.data.merged_url}`) },
        { text: 'OK' },
      ]);
      // Refresh project detail
      const updated = await axios.get(`${BACKEND_URL}/api/project/${projectId}`);
      setSelectedProject(updated.data);
    } catch (e: any) {
      Alert.alert('Merge Failed', e.response?.data?.detail || 'Could not merge segments');
    } finally { setMerging(false); }
  };

  const saveAllSegments = async (segments: any[], projectName: string) => {
    try {
      setDownloading(true);
      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        if (seg.result_url) {
          await downloadResult(seg.result_url, `${projectName}_seg${i+1}`, false);
        }
      }
    } catch (e) {} finally { setDownloading(false); }
  };

  const sc = (s: string) => ({ completed: '#10B981', processing: '#F59E0B', failed: '#EF4444' }[s] || '#6B7280');
  const si = (s: string): any => ({ completed: 'checkmark-circle', processing: 'time', failed: 'close-circle' }[s] || 'ellipse');
  const tc = (t: string) => ({ lipsync: '#8B5CF6', faceswap: '#EC4899', headswap: '#F97316', bodyswap: '#06B6D4' }[t] || '#8B5CF6');
  const ti = (t: string): any => ({ lipsync: 'mic', faceswap: 'people', headswap: 'person', bodyswap: 'body' }[t] || 'videocam');

  const renderProject = ({ item }: { item: Project & { _versionCount?: number } }) => (
    <TouchableOpacity testID={`project-${item.id}`} style={st.card} onPress={() => handleProjectPress(item)} activeOpacity={0.7}>
      {/* Version count badge — shows only if there are 2+ versions in the family */}
      {item._versionCount && item._versionCount > 1 ? (
        <View style={st.vBadge}>
          <Ionicons name="layers" size={10} color="#fff" />
          <Text style={st.vBadgeT}>{item._versionCount} versions</Text>
        </View>
      ) : null}
      <View style={st.cardH}>
        <View style={[st.cardIc, { backgroundColor: `${tc(item.type)}20` }]}><Ionicons name={ti(item.type)} size={22} color={tc(item.type)} /></View>
        <View style={st.cardInfo}>
          <Text style={st.cardName} numberOfLines={1}>{item.name}</Text>
          <Text style={st.cardType}>{typeLabel(item.type)}{item.face_count && item.face_count > 1 ? ` (${item.face_count})` : ''}{item.aspect_ratio ? ` · ${item.aspect_ratio}` : ''}</Text>
        </View>
        <Ionicons name="chevron-forward" size={20} color="#475569" />
      </View>
      {item.status === 'processing' && (
        <View style={st.prog}><View style={st.progBar}><View style={[st.progFill, { width: `${item.progress || 10}%` }]} /></View><Text style={st.progT}>{item.progress || 10}%</Text></View>
      )}
      <View style={st.cardF}>
        <View style={[st.badge, { backgroundColor: `${sc(item.status)}20` }]}><Ionicons name={si(item.status)} size={14} color={sc(item.status)} /><Text style={[st.badgeT, { color: sc(item.status) }]}>{item.status.charAt(0).toUpperCase() + item.status.slice(1)}</Text></View>
        <Text style={st.cardDate}>{new Date(item.created_at).toLocaleDateString()}</Text>
      </View>
    </TouchableOpacity>
  );

  // Filter chips
  const [filter, setFilter] = useState<'all' | 'video' | 'image' | 'avatar'>('all');
  const filteredProjects = useCallback(() => {
    if (filter === 'all') return projects;
    if (filter === 'video') return projects.filter(p => !isImageType(p.type) && !['cartoon_avatar','headswap'].includes(p.type));
    if (filter === 'image') return projects.filter(p => isImageType(p.type));
    if (filter === 'avatar') return projects.filter(p => ['cartoon_avatar','headswap','faceswap_img'].includes(p.type));
    return projects;
  }, [projects, filter]);

  if (loading) return (<AuroraBackground><SafeAreaView style={st.container}><View style={st.loadC}><ActivityIndicator size="large" color="#A78BFA" /><Text style={st.loadT}>Loading your library...</Text></View></SafeAreaView></AuroraBackground>);

  const isImg = selectedProject ? isImageType(selectedProject.type) : false;

  return (
    <AuroraBackground>
    <SafeAreaView style={st.container}>
      {/* Premium glass header */}
      <GlassHeader
        icon="folder-open"
        title="Library"
        subtitle={`Your creations · ${projects.length} project${projects.length === 1 ? '' : 's'}`}
        onBack={() => router.back()}
        right={
          <TouchableOpacity testID="projects-refresh-btn" onPress={fetchProjects} style={st.hBtn}>
            <Ionicons name="refresh" size={20} color="#fff" />
          </TouchableOpacity>
        }
      />

      {/* Filter chips */}
      <View style={st.chipRow}>
        {(['all','video','image','avatar'] as const).map(k => (
          <TouchableOpacity
            key={k}
            onPress={() => setFilter(k)}
            style={[st.chip, filter === k && st.chipActive]}
            activeOpacity={0.85}
          >
            <Ionicons
              name={k === 'all' ? 'apps' : k === 'video' ? 'videocam' : k === 'image' ? 'image' : 'person'}
              size={13}
              color={filter === k ? '#0B1120' : '#A78BFA'}
            />
            <Text style={[st.chipTxt, filter === k && st.chipTxtActive]}>
              {k === 'all' ? 'All' : k === 'video' ? 'Videos' : k === 'image' ? 'Images' : 'Avatars'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      {/* Group projects by parent_id: show only roots (parent_id=null) in main list.
          Compute version counts per root for the badge. */}
      {(() => null)()}
      <FlatList
        data={(() => {
          const visible = filteredProjects();
          // Compute family roots (projects with no parent_id) + their version counts
          const counts: Record<string, number> = {};
          visible.forEach(p => { const root = p.parent_id || p.id; counts[root] = (counts[root] || 0) + 1; });
          // Sort children versions per root and pick the latest as the "face" of the family
          const latestByRoot: Record<string, Project> = {};
          visible.forEach(p => {
            const root = p.parent_id || p.id;
            const cur = latestByRoot[root];
            if (!cur || (p.version || 1) > (cur.version || 1)) latestByRoot[root] = p;
          });
          const grouped = Object.entries(latestByRoot).map(([root, proj]) => ({
            ...proj,
            _versionCount: counts[root] || 1,
            _rootId: root,
          }));
          // Sort by created_at of the latest version, newest first
          return grouped.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
        })()}
        renderItem={({ item }) => renderProject({ item: item as any })}
        keyExtractor={i => i.id}
        contentContainerStyle={st.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#8B5CF6" />}
        ListEmptyComponent={
          <View style={st.empty}><Ionicons name="folder-open-outline" size={64} color="#475569" /><Text style={st.emptyT}>No projects yet</Text>
            <View style={st.emptyBtns}>
              <TouchableOpacity style={[st.emptyBtn, { backgroundColor: '#8B5CF6' }]} onPress={() => router.push('/lipsync')}><Ionicons name="mic" size={18} color="#fff" /><Text style={st.emptyBtnT}>Lip Sync</Text></TouchableOpacity>
              <TouchableOpacity style={[st.emptyBtn, { backgroundColor: '#EC4899' }]} onPress={() => router.push('/faceswap')}><Ionicons name="swap-horizontal" size={18} color="#fff" /><Text style={st.emptyBtnT}>Face Swap</Text></TouchableOpacity>
            </View>
          </View>
        }
      />
      <Modal visible={detailModal} animationType="slide" transparent>
        <View style={st.mo}><View style={st.mc}>
          <View style={st.mh}><Text style={st.mt} numberOfLines={1}>{selectedProject?.name}</Text><TouchableOpacity testID="close-modal" onPress={() => setDetailModal(false)}><Ionicons name="close" size={28} color="#fff" /></TouchableOpacity></View>
          {selectedProject && (
            <ScrollView style={st.mb}>
              <View style={st.dr}><Text style={st.dl}>Type</Text><Text style={st.dv}>{typeLabel(selectedProject.type)}</Text></View>
              <View style={st.dr}><Text style={st.dl}>Status</Text><View style={[st.badge, { backgroundColor: `${sc(selectedProject.status)}20` }]}><Ionicons name={si(selectedProject.status)} size={14} color={sc(selectedProject.status)} /><Text style={[st.badgeT, { color: sc(selectedProject.status) }]}>{selectedProject.status.charAt(0).toUpperCase() + selectedProject.status.slice(1)}</Text></View></View>
              {selectedProject.aspect_ratio && <View style={st.dr}><Text style={st.dl}>Aspect</Text><Text style={st.dv}>{selectedProject.aspect_ratio}</Text></View>}
              {selectedProject.error_message && (<View style={st.errBox}><Ionicons name="warning" size={18} color="#EF4444" /><Text style={st.errT}>{selectedProject.error_message}</Text></View>)}
              {selectedProject.result_segments && selectedProject.result_segments.length > 0 && (
                <View style={st.segSection}><Text style={st.segTitle}>Segments ({selectedProject.result_segments.length})</Text>
                  {selectedProject.result_segments.map((seg: any, idx: number) => (
                    <View key={idx} style={st.segCard}><View style={st.segInfo}><View style={st.segBadge}><Text style={st.segBadgeT}>Char {seg.character_index + 1}</Text></View><Text style={st.segText} numberOfLines={2}>{seg.text}</Text></View>
                      <View style={st.segActions}><TouchableOpacity style={st.segPlayBtn} onPress={() => openResult(seg.result_url)}><Ionicons name="play" size={16} color="#fff" /></TouchableOpacity><TouchableOpacity style={st.segDlBtn} onPress={() => downloadResult(seg.result_url, `${selectedProject.name}_seg${idx+1}`, false)}><Ionicons name="download" size={16} color="#10B981" /></TouchableOpacity></View>
                    </View>))}
                  {/* Merge & Save All buttons */}
                  {selectedProject.result_segments.length >= 2 && (
                    <View style={st.segBulkActions}>
                      <TouchableOpacity style={st.mergeBtn} onPress={() => mergeSegments(selectedProject.id)} disabled={merging}>
                        {merging ? <ActivityIndicator size="small" color="#fff" /> : <><Ionicons name="git-merge" size={18} color="#fff" /><Text style={st.mergeBtnT}>Merge All Segments</Text></>}
                      </TouchableOpacity>
                      <TouchableOpacity style={st.saveAllBtn} onPress={() => saveAllSegments(selectedProject.result_segments!, selectedProject.name)} disabled={downloading}>
                        <Ionicons name="download" size={18} color="#fff" /><Text style={st.saveAllBtnT}>Save All Videos</Text>
                      </TouchableOpacity>
                    </View>
                  )}
                  {(selectedProject as any).merged_url && (
                    <TouchableOpacity style={st.mergedCard} onPress={() => openResult(`${BACKEND_URL}${(selectedProject as any).merged_url}`)}>
                      <Ionicons name="film" size={22} color="#8B5CF6" />
                      <View style={{ flex: 1 }}><Text style={st.mergedTitle}>Merged Video Ready</Text><Text style={st.mergedSub}>Tap to preview</Text></View>
                      <TouchableOpacity style={st.mergedDl} onPress={() => downloadResult(`${BACKEND_URL}${(selectedProject as any).merged_url}`, `${selectedProject.name}_merged`, false)}><Ionicons name="download" size={18} color="#10B981" /></TouchableOpacity>
                    </TouchableOpacity>
                  )}
                </View>
              )}
              {selectedProject.result_url && (
                <>
                  <View style={{ marginBottom: 14, marginTop: 6 }}>
                    <FreeVsProToggle
                      mediaUrl={selectedProject.result_url}
                      mediaType={isImg ? 'image' : 'video'}
                      userIsPro={!!user && user.subscription_tier !== 'free'}
                      aspectRatio={isImg ? 1 : (selectedProject.aspect_ratio === '16:9' ? 16 / 9 : 9 / 16)}
                      onUpgrade={() => { setDetailModal(false); router.push('/buy?tab=tier' as any); }}
                      onDownload={() => downloadResult(selectedProject.result_url!, selectedProject.name, isImg)}
                    />
                  </View>
                  <View style={st.actions}>
                  <TouchableOpacity testID="open-result-btn" style={st.playBtn} onPress={() => openResult(selectedProject.result_url!)}>
                    <Ionicons name={isImg ? 'image' : 'play-circle'} size={22} color="#fff" /><Text style={st.playBtnT}>{isImg ? 'Open Image' : 'Open Video'}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity testID="download-result-btn" style={[st.dlBtn, downloading && { backgroundColor: '#059669' }]} onPress={() => downloadResult(selectedProject.result_url!, selectedProject.name, isImg)} disabled={downloading}>
                    {downloading ? <ActivityIndicator size="small" color="#fff" /> : (<><Ionicons name="download" size={22} color="#fff" /><Text style={st.dlBtnT}>{isImg ? 'Save Image' : 'Save Video'}</Text></>)}
                  </TouchableOpacity>
                  <TouchableOpacity testID="share-result-btn" style={st.shareBtn} onPress={() => shareResult(selectedProject.result_url!, selectedProject.name, isImg)}>
                    <Ionicons name="share-social" size={22} color="#fff" /><Text style={st.shareBtnT}>Share to Social Media</Text>
                  </TouchableOpacity>
                </View>
                </>
              )}

              {/* Sprint 1: Versions bar + Edit/Recreate/Regenerate */}
              {versions.length > 1 && (
                <View style={st.versionsBar}>
                  <Text style={st.versionsTitle}>Versions</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                    {versions.map((v) => (
                      <TouchableOpacity
                        key={v.id}
                        style={[st.versionChip, selectedProject.id === v.id && st.versionChipActive]}
                        onPress={() => switchToVersion(v)}
                      >
                        <Text style={[st.versionChipT, selectedProject.id === v.id && { color: '#fff' }]}>v{v.version || 1}</Text>
                        <Text style={[st.versionChipSub, selectedProject.id === v.id && { color: '#FED7AA' }]}>{v.action || 'original'}</Text>
                        {v.status === 'processing' && <ActivityIndicator size="small" color="#F97316" style={{ marginLeft: 4 }} />}
                        {v.status === 'failed' && <Ionicons name="alert-circle" size={12} color="#EF4444" style={{ marginLeft: 4 }} />}
                      </TouchableOpacity>
                    ))}
                  </ScrollView>
                </View>
              )}

              {selectedProject.input_payload && selectedProject.endpoint && (
                <View style={st.versionActions}>
                  <TouchableOpacity
                    style={st.vActBtn}
                    onPress={doEdit}
                  >
                    <Ionicons name="create" size={18} color="#A78BFA" />
                    <Text style={st.vActBtnT}>Edit</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={st.vActBtn}
                    onPress={() => doRerun('recreate')}
                    disabled={rerunning !== null}
                  >
                    {rerunning === 'recreate'
                      ? <ActivityIndicator size="small" color="#10B981" />
                      : <Ionicons name="refresh" size={18} color="#10B981" />}
                    <Text style={[st.vActBtnT, { color: '#10B981' }]}>Recreate</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={st.vActBtn}
                    onPress={() => doRerun('regenerate')}
                    disabled={rerunning !== null}
                  >
                    {rerunning === 'regenerate'
                      ? <ActivityIndicator size="small" color="#F97316" />
                      : <Ionicons name="sparkles" size={18} color="#F97316" />}
                    <Text style={[st.vActBtnT, { color: '#F97316' }]}>Regenerate</Text>
                  </TouchableOpacity>
                </View>
              )}
              {selectedProject.input_payload && (
                <Text style={st.vHint}>Edit: change inputs & rerun · Recreate: identical replay · Regenerate: new random variation</Text>
              )}

              <TouchableOpacity testID="delete-project-btn" style={st.delBtn} onPress={() => Alert.alert('Delete?', '', [{ text: 'Cancel' }, { text: 'Delete', style: 'destructive', onPress: () => deleteProject(selectedProject.id) }])}>
                <Ionicons name="trash" size={18} color="#EF4444" /><Text style={st.delBtnT}>Delete</Text>
              </TouchableOpacity>
            </ScrollView>
          )}
        </View></View>
      </Modal>
    </SafeAreaView>
    <BottomTabBar active="library" />
    </AuroraBackground>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  loadC: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16 }, loadT: { color: '#94A3B8', fontSize: 14 },
  // Premium glass header
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingTop: 6, paddingBottom: 10 },
  hBtn: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  titleWrap: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1, marginHorizontal: 12 },
  glyph: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', overflow: 'hidden', borderWidth: 1, borderColor: 'rgba(255,255,255,0.22)' },
  hTitle: { fontSize: 19, fontWeight: '900', color: '#fff', letterSpacing: 0.3 },
  hSub: { fontSize: 11, color: '#A78BFA', fontWeight: '700', marginTop: 1 },
  // Filter chips row
  chipRow: { flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 8, gap: 8, alignItems: 'center', flexShrink: 0, minHeight: 44 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 18, backgroundColor: 'rgba(168,139,250,0.18)', borderWidth: 1, borderColor: 'rgba(168,139,250,0.45)' },
  chipActive: { backgroundColor: '#FBBF24', borderColor: '#FBBF24' },
  chipTxt: { color: '#E2D7FA', fontSize: 12, fontWeight: '800', letterSpacing: 0.3 },
  chipTxtActive: { color: '#0B1120' },
  list: { padding: 16, paddingTop: 8, paddingBottom: 110 },
  // Frosted glass cards
  card: { backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: 16, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  cardH: { flexDirection: 'row', alignItems: 'center', marginBottom: 10 },
  cardIc: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  cardInfo: { flex: 1 }, cardName: { fontSize: 15, fontWeight: '700', color: '#fff', marginBottom: 2 }, cardType: { fontSize: 12, color: '#94A3B8' },
  prog: { flexDirection: 'row', alignItems: 'center', marginBottom: 10, gap: 8 },
  progBar: { flex: 1, height: 6, backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 3 }, progFill: { height: 6, backgroundColor: '#F59E0B', borderRadius: 3 },
  progT: { color: '#F59E0B', fontSize: 12, fontWeight: '700', width: 36 },
  cardF: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  badge: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10, gap: 4 },
  badgeT: { fontSize: 11, fontWeight: '700' }, cardDate: { fontSize: 11, color: '#64748B' },
  empty: { alignItems: 'center', paddingVertical: 60 }, emptyT: { fontSize: 18, fontWeight: '800', color: '#E2E8F0', marginTop: 16 },
  emptyBtns: { flexDirection: 'row', gap: 12, marginTop: 24 },
  emptyBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 12, paddingVertical: 12, paddingHorizontal: 18 }, emptyBtnT: { color: '#fff', fontSize: 14, fontWeight: '700' },
  mo: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-end' },
  mc: { backgroundColor: '#1E293B', borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '80%', paddingBottom: 40 },
  mh: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 20, borderBottomWidth: 1, borderBottomColor: '#334155' },
  mt: { fontSize: 20, fontWeight: 'bold', color: '#fff', flex: 1, marginRight: 12 }, mb: { padding: 20 },
  dr: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#334155' },
  dl: { fontSize: 14, color: '#94A3B8' }, dv: { fontSize: 14, color: '#E2E8F0', fontWeight: '600' },
  errBox: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: '#EF444420', borderRadius: 10, padding: 12, marginTop: 10, gap: 8 },
  errT: { color: '#FCA5A5', fontSize: 13, flex: 1 },
  segSection: { marginTop: 16 }, segTitle: { fontSize: 16, fontWeight: '700', color: '#E2E8F0', marginBottom: 10 },
  segCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0F172A', borderRadius: 10, padding: 12, marginBottom: 8 },
  segInfo: { flex: 1 }, segBadge: { backgroundColor: '#8B5CF630', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2, alignSelf: 'flex-start', marginBottom: 4 },
  segBadgeT: { color: '#8B5CF6', fontSize: 12, fontWeight: '600' }, segText: { color: '#94A3B8', fontSize: 13 },
  segActions: { flexDirection: 'row', gap: 8, marginLeft: 8 },
  segPlayBtn: { backgroundColor: '#8B5CF6', borderRadius: 8, width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  segDlBtn: { backgroundColor: '#10B98120', borderRadius: 8, width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  actions: { gap: 10, marginTop: 16 },
  playBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#8B5CF6', borderRadius: 12, padding: 16 },
  playBtnT: { color: '#fff', fontSize: 16, fontWeight: 'bold' },
  dlBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#10B981', borderRadius: 12, padding: 16 },
  dlBtnT: { color: '#fff', fontSize: 16, fontWeight: 'bold' },
  shareBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#3B82F6', borderRadius: 12, padding: 16 },
  shareBtnT: { color: '#fff', fontSize: 16, fontWeight: 'bold' },
  delBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#EF444420', borderRadius: 12, padding: 14, marginTop: 12 },
  delBtnT: { color: '#EF4444', fontSize: 15, fontWeight: '600' },
  // Sprint 1 — versioning
  versionsBar: { marginTop: 14, marginBottom: 4 },
  versionsTitle: { color: '#94A3B8', fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 },
  versionChip: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#1E293B', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, marginRight: 8, borderWidth: 1, borderColor: '#334155' },
  versionChipActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  versionChipT: { color: '#E2E8F0', fontSize: 13, fontWeight: '700' },
  versionChipSub: { color: '#64748B', fontSize: 10, fontWeight: '600', marginLeft: 6, textTransform: 'capitalize' },
  versionActions: { flexDirection: 'row', gap: 8, marginTop: 10 },
  vActBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#1E293B', borderRadius: 10, paddingVertical: 11, borderWidth: 1, borderColor: '#334155' },
  vActBtnT: { color: '#A78BFA', fontSize: 13, fontWeight: '700' },
  vHint: { color: '#64748B', fontSize: 11, marginTop: 6, textAlign: 'center' },
  // Library grouping (v-badge on parent cards)
  vBadge: { position: 'absolute', top: 8, right: 8, backgroundColor: '#8B5CF6', borderRadius: 10, paddingHorizontal: 8, paddingVertical: 3, flexDirection: 'row', alignItems: 'center', gap: 3 },
  vBadgeT: { color: '#fff', fontSize: 10, fontWeight: '700' },
  segBulkActions: { marginTop: 10, gap: 8 },
  mergeBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#8B5CF6', borderRadius: 10, padding: 14 },
  mergeBtnT: { color: '#fff', fontSize: 14, fontWeight: '700' },
  saveAllBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#10B981', borderRadius: 10, padding: 14 },
  saveAllBtnT: { color: '#fff', fontSize: 14, fontWeight: '700' },
  mergedCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#8B5CF610', borderRadius: 10, padding: 12, marginTop: 10, borderWidth: 1, borderColor: '#8B5CF640' },
  mergedTitle: { color: '#8B5CF6', fontSize: 14, fontWeight: '700' },
  mergedSub: { color: '#94A3B8', fontSize: 12 },
  mergedDl: { padding: 8 },
});
