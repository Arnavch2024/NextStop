import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { getMobileSupabaseClient } from '../lib/supabase';
import { ProfileRole } from '@recruiting/shared';

interface RoleCard {
  role: ProfileRole;
  title: string;
  badge: string;
  desc: string;
}

const ROLES: RoleCard[] = [
  {
    role: 'student',
    title: 'Student',
    badge: 'Batch 2027 / 2028',
    desc: 'Mumbai college student discovering placements & self-reporting details.',
  },
  {
    role: 'placement_officer',
    title: 'Placement Officer',
    badge: 'Placement Cell',
    desc: 'Managing college profile, departments, and cohort student records.',
  },
  {
    role: 'company',
    title: 'Company',
    badge: 'Hiring Org',
    desc: 'Register hiring company details and recruiting coordinators.',
  },
  {
    role: 'recruiter',
    title: 'Recruiter',
    badge: 'Talent Acquisition',
    desc: 'Recruiter connecting student talent with top hiring organizations.',
  },
];

export default function OnboardingScreen() {
  const router = useRouter();
  const supabase = getMobileSupabaseClient();

  const [loadingRole, setLoadingRole] = useState<ProfileRole | null>(null);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace('/login');
        return;
      }
      setUserId(session.user.id);
    });
  }, [router, supabase]);

  async function handleSelect(role: ProfileRole) {
    if (!userId) return;
    setLoadingRole(role);

    try {
      const { error } = await supabase
        .from('profiles')
        .upsert({
          id: userId,
          role,
          updated_at: new Date().toISOString(),
        });

      if (error) throw error;
      router.replace('/chat');
    } catch (err) {
      setLoadingRole(null);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <Text style={styles.badge}>Step 1 of 1</Text>
        <Text style={styles.title}>Choose Your Role</Text>
        <Text style={styles.subtitle}>
          One tap sets your profile. Everything else is conversational.
        </Text>
      </View>

      <View style={styles.grid}>
        {ROLES.map((r) => {
          const isLoading = loadingRole === r.role;
          return (
            <TouchableOpacity
              key={r.role}
              style={styles.card}
              onPress={() => handleSelect(r.role)}
              disabled={loadingRole !== null}
            >
              <View style={styles.cardTop}>
                <Text style={styles.cardTitle}>{r.title}</Text>
                <Text style={styles.cardBadge}>{r.badge}</Text>
              </View>
              <Text style={styles.cardDesc}>{r.desc}</Text>

              <View style={styles.cardBottom}>
                {isLoading ? (
                  <ActivityIndicator size="small" color="#4f46e5" />
                ) : (
                  <Text style={styles.selectText}>Select &rarr;</Text>
                )}
              </View>
            </TouchableOpacity>
          );
        })}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 24,
    backgroundColor: '#f8fafc',
    flexGrow: 1,
    justifyContent: 'center',
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
  },
  badge: {
    color: '#4f46e5',
    backgroundColor: '#eef2ff',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    fontSize: 11,
    fontWeight: '700',
    overflow: 'hidden',
  },
  title: {
    fontSize: 26,
    fontWeight: '800',
    color: '#0f172a',
    marginTop: 8,
  },
  subtitle: {
    fontSize: 13,
    color: '#64748b',
    marginTop: 4,
    textAlign: 'center',
  },
  grid: {
    gap: 14,
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  cardTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#0f172a',
  },
  cardBadge: {
    fontSize: 11,
    color: '#475569',
    backgroundColor: '#f1f5f9',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
    overflow: 'hidden',
  },
  cardDesc: {
    fontSize: 13,
    color: '#64748b',
    lineHeight: 18,
  },
  cardBottom: {
    marginTop: 12,
    alignItems: 'flex-end',
  },
  selectText: {
    color: '#4f46e5',
    fontSize: 13,
    fontWeight: '700',
  },
});
