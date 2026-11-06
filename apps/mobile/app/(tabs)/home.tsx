import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { getMobileSupabaseClient, API_BASE_URL } from '../../lib/supabase';
import {
  getStudentScore,
  getStudentProfile,
  ScoreResponse,
  StudentProfile,
} from '@recruiting/shared';

export default function MobileHomeScreen() {
  const router = useRouter();
  const supabase = getMobileSupabaseClient();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scoreData, setScoreData] = useState<ScoreResponse | null>(null);
  const [profileData, setProfileData] = useState<StudentProfile | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (!session) {
          router.replace('/login');
          return;
        }

        const token = session.access_token;
        const [scoreRes, profRes] = await Promise.all([
          getStudentScore(API_BASE_URL, token),
          getStudentProfile(API_BASE_URL, token),
        ]);

        if (isMounted) {
          setScoreData(scoreRes);
          setProfileData(profRes);
          setLoading(false);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || 'Failed to load profile.');
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      isMounted = false;
    };
  }, [router, supabase]);

  if (loading) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#2563EB" />
        <Text style={styles.loadingText}>Loading readiness profile...</Text>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => router.push('/chat')}
        >
          <Text style={styles.actionButtonText}>Go to Chat</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  const score = scoreData?.score ?? 20;
  const breakdown = scoreData?.breakdown ?? [];
  const nextActions = scoreData?.next_best_actions ?? [];

  const student = profileData?.student;
  const education = profileData?.education ?? [];
  const internships = profileData?.internships ?? [];
  const jobs = profileData?.jobs ?? [];

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.headerTitle}>Student Dashboard</Text>
            <Text style={styles.headerSubtitle}>
              {student?.full_name ? `${student.full_name} • Batch ${student.batch_year}` : 'NextStop Recruiting'}
            </Text>
          </View>
          <TouchableOpacity
            style={styles.chatHeaderButton}
            onPress={() => router.push('/chat')}
          >
            <Text style={styles.chatHeaderButtonText}>Chat</Text>
          </TouchableOpacity>
        </View>

        {/* Score Card */}
        <View style={styles.scoreCard}>
          <Text style={styles.scoreCardLabel}>CAMPUS READINESS SCORE</Text>
          <View style={styles.scoreRow}>
            <Text style={styles.scoreNumber}>{score}</Text>
            <Text style={styles.scoreMax}>/ 100</Text>
          </View>
          <View style={styles.progressBarBg}>
            <View
              style={[
                styles.progressBarFill,
                { width: `${Math.min(100, Math.max(0, score))}%` },
              ]}
            />
          </View>
        </View>

        {/* Next Best Action Card */}
        {nextActions.length > 0 && (
          <View style={styles.nextActionCard}>
            <Text style={styles.nextActionLabel}>NEXT BEST ACTION</Text>
            <Text style={styles.nextActionText}>{nextActions[0]}</Text>
            <TouchableOpacity onPress={() => router.push('/chat')}>
              <Text style={styles.nextActionLink}>Complete now in chat →</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Why is my score N? */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>Why is my score {score}?</Text>
          {breakdown.map((item, idx) => (
            <View key={idx} style={styles.breakdownRow}>
              <View style={styles.breakdownLeft}>
                <Text style={styles.breakdownReason}>{item.reason}</Text>
                <Text style={styles.breakdownSource}>source: {item.source}</Text>
              </View>
              <Text style={styles.breakdownPoints}>+{item.points}</Text>
            </View>
          ))}
        </View>

        {/* Timeline */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>Profile Timeline</Text>
          <View style={styles.timeline}>
            {education.map((edu, idx) => (
              <View key={`edu-${idx}`} style={styles.timelineItem}>
                <View style={[styles.timelineDot, { backgroundColor: '#2563EB' }]} />
                <View style={styles.timelineBody}>
                  <Text style={styles.timelineHeading}>
                    {edu.degree || edu.level.toUpperCase()}
                    {edu.score_value ? ` (${edu.score_value} ${edu.score_scale || ''})` : ''}
                  </Text>
                  <Text style={styles.timelineSub}>
                    {edu.institution || edu.board_or_university || 'Education'}
                  </Text>
                </View>
              </View>
            ))}

            {internships.map((intn, idx) => (
              <View key={`int-${idx}`} style={styles.timelineItem}>
                <View style={[styles.timelineDot, { backgroundColor: '#7C3AED' }]} />
                <View style={styles.timelineBody}>
                  <Text style={styles.timelineHeading}>
                    {intn.role || 'Intern'} at {intn.company || 'Company'}
                  </Text>
                  <Text style={styles.timelineSub}>
                    {intn.start_date || ''} {intn.end_date ? `— ${intn.end_date}` : '— Ongoing'}
                  </Text>
                </View>
              </View>
            ))}

            {jobs.map((job, idx) => (
              <View key={`job-${idx}`} style={styles.timelineItem}>
                <View style={[styles.timelineDot, { backgroundColor: '#059669' }]} />
                <View style={styles.timelineBody}>
                  <Text style={styles.timelineHeading}>
                    {job.role || 'Role'} at {job.company || 'Company'}
                  </Text>
                  <Text style={styles.timelineSub}>
                    {job.start_date || ''} {job.end_date ? `— ${job.end_date}` : '— Present'}
                  </Text>
                </View>
              </View>
            ))}

            {education.length === 0 && internships.length === 0 && jobs.length === 0 && (
              <Text style={styles.emptyTimelineText}>
                No timeline records yet. Upload your resume or talk with the chat assistant!
              </Text>
            )}
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
    backgroundColor: '#F8FAFC',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#64748B',
  },
  errorText: {
    color: '#EF4444',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#0F172A',
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 2,
  },
  chatHeaderButton: {
    backgroundColor: '#2563EB',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  chatHeaderButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 13,
  },
  scoreCard: {
    backgroundColor: '#FFFFFF',
    padding: 18,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 14,
  },
  scoreCardLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#64748B',
    letterSpacing: 0.5,
  },
  scoreRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginVertical: 8,
  },
  scoreNumber: {
    fontSize: 48,
    fontWeight: '800',
    color: '#2563EB',
  },
  scoreMax: {
    fontSize: 16,
    color: '#94A3B8',
    marginLeft: 6,
    fontWeight: '600',
  },
  progressBarBg: {
    height: 8,
    backgroundColor: '#F1F5F9',
    borderRadius: 4,
    overflow: 'hidden',
    marginTop: 4,
  },
  progressBarFill: {
    height: 8,
    backgroundColor: '#2563EB',
    borderRadius: 4,
  },
  nextActionCard: {
    backgroundColor: '#EFF6FF',
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#DBEAFE',
    marginBottom: 14,
  },
  nextActionLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#1E40AF',
    letterSpacing: 0.5,
  },
  nextActionText: {
    fontSize: 14,
    color: '#1E293B',
    fontWeight: '500',
    marginTop: 4,
  },
  nextActionLink: {
    color: '#2563EB',
    fontSize: 12,
    fontWeight: '600',
    marginTop: 8,
  },
  sectionCard: {
    backgroundColor: '#FFFFFF',
    padding: 18,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 14,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0F172A',
    marginBottom: 12,
  },
  breakdownRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
  },
  breakdownLeft: {
    flex: 1,
    paddingRight: 10,
  },
  breakdownReason: {
    fontSize: 14,
    color: '#1E293B',
    fontWeight: '500',
  },
  breakdownSource: {
    fontSize: 11,
    color: '#94A3B8',
    marginTop: 2,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  breakdownPoints: {
    fontSize: 15,
    fontWeight: '700',
    color: '#059669',
  },
  timeline: {
    paddingLeft: 12,
    borderLeftWidth: 2,
    borderLeftColor: '#E2E8F0',
    marginLeft: 6,
  },
  timelineItem: {
    marginBottom: 16,
    position: 'relative',
  },
  timelineDot: {
    position: 'absolute',
    left: -19,
    top: 3,
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#FFFFFF',
  },
  timelineBody: {
    paddingLeft: 4,
  },
  timelineHeading: {
    fontSize: 14,
    fontWeight: '600',
    color: '#0F172A',
  },
  timelineSub: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 2,
  },
  emptyTimelineText: {
    fontSize: 13,
    color: '#94A3B8',
    fontStyle: 'italic',
  },
  actionButton: {
    backgroundColor: '#2563EB',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
  },
  actionButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 14,
  },
});
