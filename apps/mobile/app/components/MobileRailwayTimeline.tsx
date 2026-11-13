import React from "react";
import { View, Text, StyleSheet, ActivityIndicator } from "react-native";
import { Feather } from "@expo/vector-icons";
import { TimelineStation } from "@recruiting/shared";

interface MobileRailwayTimelineProps {
  stations: TimelineStation[];
  isLoading?: boolean;
}

export function MobileRailwayTimeline({
  stations,
  isLoading = false,
}: MobileRailwayTimelineProps) {
  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="small" color="#4F46E5" />
        <Text style={styles.loadingText}>Loading railway route...</Text>
      </View>
    );
  }

  if (!stations || stations.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        <View style={styles.emptyIconBadge}>
          <Feather name="compass" size={26} color="#4F46E5" />
        </View>
        <Text style={styles.emptyTitle}>Your Route Has Not Started</Text>
        <Text style={styles.emptySubtitle}>
          Chat with the assistant to record your 10th, 12th, college details,
          and internships. Each milestone adds a station to your journey.
        </Text>
      </View>
    );
  }

  function getStationIconName(kind: string): keyof typeof Feather.glyphMap {
    switch (kind) {
      case "school_10":
      case "school_12":
        return "book-open";
      case "college":
        return "award";
      case "internship":
        return "briefcase";
      case "job":
        return "layers";
      case "pre_verify_done":
      case "pre_verify_pending":
        return "shield";
      case "reference_done":
      case "reference_pending":
        return "check-circle";
      default:
        return "map-pin";
    }
  }

  function formatStationYears(station: TimelineStation): string {
    if (station.is_future) {
      return "Next milestone";
    }
    if (station.start_year && station.end_year) {
      return `${station.start_year} — ${station.end_year}`;
    }
    if (station.start_year && !station.end_year) {
      return `${station.start_year} — Present`;
    }
    return station.subtitle || "";
  }

  return (
    <View style={styles.container}>
      {/* Railway Track spine */}
      <View style={styles.trackLine} />

      {stations.map((station, idx) => {
        const isCurrent = !!station.is_current;
        const isFuture = !!station.is_future;

        return (
          <View key={station.id || `station-${idx}`} style={styles.stationRow}>
            {/* Station Node Indicator */}
            <View
              style={[
                styles.nodeCircle,
                isCurrent
                  ? styles.nodeCircleCurrent
                  : isFuture
                    ? styles.nodeCircleFuture
                    : styles.nodeCirclePast,
              ]}
            >
              <Feather
                name={getStationIconName(station.kind)}
                size={14}
                color={isCurrent ? "#ffffff" : isFuture ? "#94a3b8" : "#4f46e5"}
              />
            </View>

            {/* Station Content */}
            <View
              style={[
                styles.card,
                isCurrent && styles.cardCurrent,
                isFuture && styles.cardFuture,
              ]}
            >
              <View style={styles.cardHeader}>
                <View style={{ flex: 1 }}>
                  <Text
                    style={[
                      styles.stationTitle,
                      isCurrent && styles.stationTitleCurrent,
                      isFuture && styles.stationTitleFuture,
                    ]}
                  >
                    {station.title}
                  </Text>
                  {station.subtitle ? (
                    <Text style={styles.stationSubtitle}>
                      {station.subtitle}
                    </Text>
                  ) : null}
                </View>

                {isCurrent && (
                  <View style={styles.currentBadge}>
                    <View style={styles.currentDot} />
                    <Text style={styles.currentBadgeText}>You are here</Text>
                  </View>
                )}
              </View>

              {/* Station Years / Subtitle */}
              <View style={styles.yearsRow}>
                <Feather
                  name="calendar"
                  size={11}
                  color="#64748b"
                  style={{ marginRight: 4 }}
                />
                <Text style={styles.yearsText}>
                  {formatStationYears(station)}
                </Text>
              </View>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: "relative",
    paddingLeft: 4,
    paddingVertical: 4,
  },
  trackLine: {
    position: "absolute",
    left: 20,
    top: 16,
    bottom: 16,
    width: 3,
    backgroundColor: "#E2E8F0",
    borderRadius: 2,
  },
  stationRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 16,
    gap: 12,
  },
  nodeCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    zIndex: 2,
  },
  nodeCirclePast: {
    backgroundColor: "#EEF2FF",
    borderColor: "#4F46E5",
  },
  nodeCircleCurrent: {
    backgroundColor: "#4F46E5",
    borderColor: "#312E81",
    shadowColor: "#4F46E5",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 3,
  },
  nodeCircleFuture: {
    backgroundColor: "#F8FAFC",
    borderColor: "#CBD5E1",
  },
  stationIcon: {
    fontSize: 16,
  },
  card: {
    flex: 1,
    backgroundColor: "#FFFFFF",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: 12,
  },
  cardCurrent: {
    borderColor: "#818CF8",
    backgroundColor: "#F5F3FF",
    borderWidth: 1.5,
  },
  cardFuture: {
    borderStyle: "dashed",
    borderColor: "#CBD5E1",
    backgroundColor: "#F8FAFC",
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 8,
  },
  stationTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F172A",
    flexShrink: 1,
  },
  stationTitleCurrent: {
    color: "#4338CA",
  },
  stationTitleFuture: {
    color: "#64748B",
  },
  stationSubtitle: {
    fontSize: 11,
    color: "#64748B",
    marginTop: 2,
  },
  currentBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#4F46E5",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    gap: 4,
  },
  currentDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#FFFFFF",
  },
  currentBadgeText: {
    color: "#FFFFFF",
    fontSize: 10,
    fontWeight: "700",
  },
  yearsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: "#F1F5F9",
  },
  yearsText: {
    fontSize: 11,
    color: "#475569",
    fontWeight: "500",
  },
  sourceBadge: {
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 6,
  },
  sourceText: {
    fontSize: 9,
    color: "#64748B",
    fontFamily: "monospace",
  },
  loadingContainer: {
    padding: 24,
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  loadingText: {
    fontSize: 12,
    color: "#64748B",
  },
  emptyContainer: {
    padding: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F8FAFC",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderStyle: "dashed",
  },
  emptyIconBadge: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: "#EEF2FF",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
  },
  emptyTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#1E293B",
  },
  emptySubtitle: {
    fontSize: 11,
    color: "#64748B",
    textAlign: "center",
    marginTop: 4,
    lineHeight: 16,
  },
});
