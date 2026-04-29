/* Production T&C — Razorpay-mandatory legal pages.
 *
 * Single tabbed screen serving 6 documents:
 *   1. Terms of Service
 *   2. Privacy Policy (DPDP Act 2023 / GDPR-aligned)
 *   3. Refund & Cancellation Policy (REQUIRED for Razorpay live activation)
 *   4. Acceptable Use Policy (AI-generated content rules)
 *   5. Contact Us
 *   6. About Us
 *
 * Deep-linkable: /legal?doc=refund | privacy | terms | aup | contact | about
 */
import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  StatusBar, Pressable, Linking,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

type DocId = 'terms' | 'privacy' | 'refund' | 'aup' | 'contact' | 'about';

const DOCS: { id: DocId; label: string; icon: any }[] = [
  { id: 'terms',   label: 'Terms',    icon: 'document-text-outline' },
  { id: 'privacy', label: 'Privacy',  icon: 'shield-checkmark-outline' },
  { id: 'refund',  label: 'Refunds',  icon: 'cash-outline' },
  { id: 'aup',     label: 'AI Use',   icon: 'sparkles-outline' },
  { id: 'contact', label: 'Contact',  icon: 'mail-outline' },
  { id: 'about',   label: 'About',    icon: 'information-circle-outline' },
];

const COMPANY = 'MagiCAi Studio';
const SUPPORT_EMAIL = 'support@magicai.studio';
const LAST_UPDATED = 'June 2025';


export default function LegalScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ doc?: string }>();
  const [active, setActive] = useState<DocId>(
    (params?.doc && DOCS.some(d => d.id === params.doc)) ? (params.doc as DocId) : 'terms',
  );

  useEffect(() => {
    if (params?.doc && DOCS.some(d => d.id === params.doc)) setActive(params.doc as DocId);
  }, [params?.doc]);

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <StatusBar barStyle="light-content" />
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="chevron-back" size={22} color="#fff" /></TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Legal</Text>
          <Text style={s.headerSub}>Last updated · {LAST_UPDATED}</Text>
        </View>
      </View>

      {/* Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.tabRow}>
        {DOCS.map(d => (
          <Pressable
            key={d.id}
            onPress={() => setActive(d.id)}
            style={[s.tab, active === d.id && s.tabActive]}
          >
            <Ionicons name={d.icon} size={13} color={active === d.id ? '#fff' : '#94A3B8'} />
            <Text style={[s.tabTxt, active === d.id && { color: '#fff' }]}>{d.label}</Text>
          </Pressable>
        ))}
      </ScrollView>

      {/* Body */}
      <ScrollView style={{ flex: 1 }} contentContainerStyle={s.body}>
        {active === 'terms' && <Terms />}
        {active === 'privacy' && <Privacy />}
        {active === 'refund' && <Refund />}
        {active === 'aup' && <Aup />}
        {active === 'contact' && <Contact />}
        {active === 'about' && <About />}

        <View style={{ marginTop: 24, padding: 12, backgroundColor: '#1E293B', borderRadius: 10 }}>
          <Text style={s.foot}>Questions? Email{' '}
            <Text style={s.link} onPress={() => Linking.openURL(`mailto:${SUPPORT_EMAIL}`)}>
              {SUPPORT_EMAIL}
            </Text>
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}


/* ============ DOCS ============ */
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ marginBottom: 18 }}>
      <Text style={s.sectionTitle}>{title}</Text>
      <View style={{ gap: 6 }}>{children}</View>
    </View>
  );
}
function P({ children }: { children: React.ReactNode }) { return <Text style={s.p}>{children}</Text>; }
function Bullet({ children }: { children: React.ReactNode }) { return <Text style={s.bullet}>•  {children}</Text>; }


function Terms() {
  return <>
    <Text style={s.h1}>Terms of Service</Text>
    <P>By accessing or using {COMPANY} (the "Service"), you agree to be bound by these Terms. If you do not agree, do not use the Service.</P>
    <Section title="1. Account">
      <P>You must be at least 13 years old to use {COMPANY}. You are responsible for keeping your credentials secure and for all activity on your account.</P>
    </Section>
    <Section title="2. Acceptable Use">
      <P>You will not use {COMPANY} to create, upload, or share content that violates our Acceptable Use Policy (see "AI Use" tab).</P>
    </Section>
    <Section title="3. Subscriptions, Credits & Billing">
      <Bullet>Credit packs are one-time purchases — credits never expire while the account is active.</Bullet>
      <Bullet>Tier upgrades (Starter, Creator, Pro) are one-time payments granting 30 days of premium access. There is no auto-renewal.</Bullet>
      <Bullet>All prices are in INR and inclusive of applicable GST. Payment processing is handled by Razorpay.</Bullet>
    </Section>
    <Section title="4. Intellectual Property">
      <Bullet>You retain ownership of content you upload.</Bullet>
      <Bullet>You own commercial rights to AI-generated outputs subject to your active subscription tier and our AI Use Policy.</Bullet>
      <Bullet>{COMPANY}, its name, branding, software and Service are owned by us; you may not copy, modify or reverse-engineer them.</Bullet>
    </Section>
    <Section title="5. Service Availability">
      <P>The Service is provided "as is" without warranty. We do not guarantee uninterrupted availability and may modify, suspend or discontinue features with reasonable notice.</P>
    </Section>
    <Section title="6. Limitation of Liability">
      <P>To the maximum extent permitted by law, {COMPANY}'s total liability for any claim arising out of the Service shall not exceed the amount you paid in the 30 days preceding the event.</P>
    </Section>
    <Section title="7. Termination">
      <P>We may suspend or terminate accounts that violate these Terms or our AUP. You may close your account at any time by emailing support.</P>
    </Section>
    <Section title="8. Governing Law">
      <P>These Terms are governed by the laws of India. Disputes shall be resolved in the courts of Patna, Bihar.</P>
    </Section>
    <Section title="9. Changes">
      <P>We may update these Terms; material changes will be notified in-app or by email at least 14 days in advance.</P>
    </Section>
  </>;
}


function Privacy() {
  return <>
    <Text style={s.h1}>Privacy Policy</Text>
    <P>This policy describes how {COMPANY} collects, uses and protects your personal information. We comply with India's Digital Personal Data Protection Act, 2023 ("DPDP Act") and the EU GDPR where applicable.</P>
    <Section title="1. Information We Collect">
      <Bullet>Account info: email, name, phone (optional), profile picture.</Bullet>
      <Bullet>Usage data: features used, generation history, device + IP for security.</Bullet>
      <Bullet>Content: images, audio and prompts you upload to generate reels (stored securely; you can delete anytime).</Bullet>
      <Bullet>Payment metadata: Razorpay handles your card/UPI details — we never store them.</Bullet>
    </Section>
    <Section title="2. How We Use Information">
      <Bullet>Deliver the Service (run AI generations, save your projects).</Bullet>
      <Bullet>Communicate updates, trial reminders, support replies.</Bullet>
      <Bullet>Improve AI quality (anonymized aggregates only — never your raw uploads without consent).</Bullet>
      <Bullet>Detect fraud, abuse and policy violations.</Bullet>
    </Section>
    <Section title="3. Sharing">
      <P>We never sell your data. We share strictly with these processors:</P>
      <Bullet>Razorpay — payment processing</Bullet>
      <Bullet>OpenAI / Google Gemini — AI text and image generation</Bullet>
      <Bullet>Magic Hour — premium AI video generation</Bullet>
      <Bullet>Pixabay — stock image/video search</Bullet>
      <Bullet>MongoDB Atlas — encrypted hosting</Bullet>
    </Section>
    <Section title="4. Data Retention">
      <P>Account data is retained while your account is active. Generated content is retained until you delete it. Inactive accounts are deleted after 24 months of inactivity (with a 30-day prior email notice).</P>
    </Section>
    <Section title="5. Your Rights">
      <Bullet>Access, correct, or delete your personal data anytime in Profile → Settings.</Bullet>
      <Bullet>Withdraw consent for AI training contributions in Profile → Privacy.</Bullet>
      <Bullet>Request data export: email {SUPPORT_EMAIL}.</Bullet>
    </Section>
    <Section title="6. Security">
      <P>All data in transit is TLS 1.2+ encrypted. Passwords are hashed with bcrypt. We perform regular security audits.</P>
    </Section>
    <Section title="7. Children">
      <P>The Service is not directed at children under 13. We delete any account discovered to be under 13.</P>
    </Section>
  </>;
}


function Refund() {
  return <>
    <Text style={s.h1}>Refund & Cancellation Policy</Text>
    <P>This policy explains when and how you can get a refund for purchases on {COMPANY}.</P>
    <Section title="1. Credit Packs">
      <Bullet>Unused credit packs are refundable within 7 days of purchase, on request to {SUPPORT_EMAIL}.</Bullet>
      <Bullet>Partially used credit packs are non-refundable.</Bullet>
      <Bullet>Credits never expire while your account is active.</Bullet>
    </Section>
    <Section title="2. Tier Upgrades (Manual Subscriptions)">
      <Bullet>Tier upgrades grant 30 days of premium access. Once activated they are non-refundable except under section 3 below.</Bullet>
      <Bullet>There is no auto-debit or auto-renewal — you manually renew when you want.</Bullet>
      <Bullet>You can downgrade to Free at any time. Your tier remains active until the paid period ends.</Bullet>
    </Section>
    <Section title="3. Failed Generations — Auto Refund">
      <P>If a paid generation (AI video, lipsync, faceswap, multishot, etc.) fails on our side, the credits are <Text style={{ color: '#10B981', fontWeight: '700' }}>automatically refunded to your wallet within 60 seconds</Text>. No action required from you.</P>
      <P>If you believe credits weren't refunded, email {SUPPORT_EMAIL} with your project ID and we'll resolve within 48 hours.</P>
    </Section>
    <Section title="4. Service Outages">
      <P>If the Service is unavailable for &gt;24 hours during your active premium period, you may request a pro-rata extension by emailing support.</P>
    </Section>
    <Section title="5. How to Request a Refund">
      <P>Email {SUPPORT_EMAIL} with:</P>
      <Bullet>Your account email</Bullet>
      <Bullet>The Razorpay order ID (visible in Profile → Transactions)</Bullet>
      <Bullet>Reason for refund</Bullet>
      <P>We respond within 48 business hours. Approved refunds are processed via Razorpay and reach your bank/UPI within 5-7 business days.</P>
    </Section>
    <Section title="6. Chargebacks">
      <P>Please contact us before initiating a bank chargeback. Unjustified chargebacks may result in account suspension.</P>
    </Section>
  </>;
}


function Aup() {
  return <>
    <Text style={s.h1}>Acceptable Use Policy</Text>
    <P>{COMPANY} is a creative AI tool. To keep it safe and inclusive, you agree not to use it for the following:</P>
    <Section title="❌ Strictly Prohibited">
      <Bullet>Sexually explicit content, nudity, or content involving minors</Bullet>
      <Bullet>Content depicting real people (celebrities, politicians, private individuals) without their explicit consent</Bullet>
      <Bullet>Defamatory, harassing, threatening, or bullying content</Bullet>
      <Bullet>Hate speech targeting any community based on religion, caste, race, gender or orientation</Bullet>
      <Bullet>Election misinformation, deepfakes designed to mislead voters or impersonate officials</Bullet>
      <Bullet>Self-harm, suicide promotion, or violent extremism</Bullet>
      <Bullet>Copyrighted material you do not own and do not have a license for</Bullet>
      <Bullet>Phishing, scams, or fraudulent commercial promotions</Bullet>
      <Bullet>Automated scraping or bulk-resale of {COMPANY} outputs without a commercial license</Bullet>
    </Section>
    <Section title="✓ Encouraged">
      <Bullet>Original creative reels, music videos, devotional content, comedy, and storytelling</Bullet>
      <Bullet>Promotional content for your own brand, products or services</Bullet>
      <Bullet>Educational explainers, reactions, and commentary</Bullet>
    </Section>
    <Section title="Disclosure">
      <P>For content shared publicly on social media, you must disclose AI-generated origin where required by local law (e.g. India's Information Technology Rules, 2021 amendments).</P>
    </Section>
    <Section title="Reporting & Enforcement">
      <P>Anyone may report a violation via the in-app flag button or email {SUPPORT_EMAIL}. Confirmed violations may result in content removal, credits forfeiture, or account suspension.</P>
    </Section>
  </>;
}


function Contact() {
  return <>
    <Text style={s.h1}>Contact Us</Text>
    <Section title="Customer Support">
      <P>Email: <Text style={s.link} onPress={() => Linking.openURL(`mailto:${SUPPORT_EMAIL}`)}>{SUPPORT_EMAIL}</Text></P>
      <P>Response time: within 48 business hours (Mon-Fri, IST).</P>
    </Section>
    <Section title="Refund Requests">
      <P>Send to {SUPPORT_EMAIL} with subject line "Refund Request — &lt;your order ID&gt;".</P>
    </Section>
    <Section title="Press / Partnerships">
      <P>partnerships@magicai.studio</P>
    </Section>
    <Section title="Business Address">
      <P>{COMPANY}{'\n'}Bhawanipur, Bihar, India</P>
    </Section>
    <Section title="Grievance Officer (per IT Rules, 2021)">
      <P>Name: Grievance Officer{'\n'}Email: grievance@magicai.studio{'\n'}Response: within 15 days</P>
    </Section>
  </>;
}


function About() {
  return <>
    <Text style={s.h1}>About {COMPANY}</Text>
    <P>{COMPANY} is a creator-first AI video studio that turns simple ideas into share-ready reels in seconds.</P>
    <Section title="What we do">
      <Bullet>⚡ Quick Reels powered by Pixabay stock video — free for everyone</Bullet>
      <Bullet>🎨 AI-generated cartoons, divine reels, multishot stories</Bullet>
      <Bullet>🎬 Magic Hour cinematic AI for premium tier users</Bullet>
      <Bullet>📚 24+ curated quick-reel templates across 8 categories</Bullet>
    </Section>
    <Section title="Our mission">
      <P>To democratize cinematic-quality content creation for the next 100 million Indian creators.</P>
    </Section>
    <Section title="Built with">
      <P>OpenAI · Google Gemini · Magic Hour · Pixabay · Razorpay · Expo · FastAPI · MongoDB</P>
    </Section>
  </>;
}


/* === styles === */
const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0B1120' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, gap: 10 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#1E293B', alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: '#fff', fontSize: 20, fontWeight: '800' },
  headerSub: { color: '#94A3B8', fontSize: 11, marginTop: 2 },

  tabRow: { paddingHorizontal: 16, gap: 8, paddingVertical: 8 },
  tab: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 14, backgroundColor: '#1E293B', borderWidth: 1, borderColor: '#334155' },
  tabActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  tabTxt: { color: '#94A3B8', fontWeight: '700', fontSize: 12 },

  body: { padding: 16, paddingBottom: 60 },
  h1: { color: '#fff', fontSize: 24, fontWeight: '900', marginBottom: 14 },
  sectionTitle: { color: '#fff', fontSize: 14, fontWeight: '800', marginTop: 8, marginBottom: 4 },
  p: { color: '#CBD5E1', fontSize: 13, lineHeight: 19 },
  bullet: { color: '#CBD5E1', fontSize: 13, lineHeight: 19, paddingLeft: 6 },
  link: { color: '#A78BFA', textDecorationLine: 'underline' },
  foot: { color: '#94A3B8', fontSize: 12, textAlign: 'center' },
});
