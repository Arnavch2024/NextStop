import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Linking,
  ActivityIndicator,
} from "react-native";
import { Feather } from "@expo/vector-icons";
import { ContactCard } from "@recruiting/shared";

interface MobileContactCardProps {
  contact: ContactCard;
  isSaved: boolean;
  isBusy?: boolean;
  onSave?: (contactId: string) => void;
  onRemove?: (contactId: string) => void;
  onDraft: (contact: ContactCard) => void;
  showRemoveOnly?: boolean;
}

export function MobileContactCard({
  contact,
  isSaved,
  isBusy = false,
  onSave,
  onRemove,
  onDraft,
  showRemoveOnly = false,
}: MobileContactCardProps) {
  const isUnverified = contact.unverified !== false;

  function handleOpenSource() {
    if (contact.source_url) {
      Linking.openURL(contact.source_url).catch(() => {});
    }
  }

  return (
    <View style={styles.card}>
      {/* Top row: Name & verification status badge */}
      <View style={styles.headerRow}>
        <View style={{ flex: 1 }}>
          <Text style={styles.name}>{contact.name}</Text>
          <Text style={styles.title}>
            {contact.title || "Recruiter"}
            {contact.company_name ? ` at ${contact.company_name}` : ""}
            {contact.college_name ? ` (${contact.college_name})` : ""}
          </Text>
          {contact.location ? (
            <View style={styles.locationRow}>
              <Feather
                name="map-pin"
                size={11}
                color="#64748b"
                style={{ marginRight: 4 }}
              />
              <Text style={styles.location}>{contact.location}</Text>
            </View>
          ) : null}
        </View>

        <View
          style={[
            styles.badge,
            isUnverified ? styles.badgeAmber : styles.badgeGreen,
          ]}
        >
          <Text
            style={[
              styles.badgeText,
              isUnverified ? styles.badgeTextAmber : styles.badgeTextGreen,
            ]}
          >
            {isUnverified ? "Unverified, check source" : "Verified"}
          </Text>
        </View>
      </View>

      {/* Source badges */}
      {contact.sources && contact.sources.length > 0 && (
        <View style={styles.sourcesRow}>
          {contact.sources.map((src, i) => {
            const label =
              src.source === "seed"
                ? "Seed"
                : src.source === "resume"
                  ? "Resume"
                  : src.source === "user_said"
                    ? "User said"
                    : "Web";
            const domain = src.domain;
            const dateStr = src.fetched_at?.slice(0, 10);

            return (
              <View key={i} style={styles.sourceTag}>
                <Text style={styles.sourceTagText}>
                  {label}
                  {domain ? ` (${domain})` : ""}
                  {dateStr ? ` • ${dateStr}` : ""}
                </Text>
              </View>
            );
          })}
        </View>
      )}

      {/* Meta date & source URL */}
      <View style={styles.metaRow}>
        {contact.source_url ? (
          <TouchableOpacity onPress={handleOpenSource} style={styles.sourceBtn}>
            <Text style={styles.sourceLink}>Source</Text>
            <Feather
              name="external-link"
              size={10}
              color="#4f46e5"
              style={{ marginLeft: 3 }}
            />
          </TouchableOpacity>
        ) : null}
        {contact.source_published_date ? (
          <Text style={styles.metaDate}>
            As of: {contact.source_published_date.slice(0, 10)}
          </Text>
        ) : null}
      </View>

      {/* Actions Row */}
      <View style={styles.actionsRow}>
        {/* Draft message action */}
        <TouchableOpacity
          style={styles.draftBtn}
          onPress={() => onDraft(contact)}
        >
          <Feather
            name="edit-3"
            size={12}
            color="#4338ca"
            style={{ marginRight: 5 }}
          />
          <Text style={styles.draftBtnText}>Draft outreach</Text>
        </TouchableOpacity>

        {/* Save / Remove action */}
        {showRemoveOnly ? (
          <TouchableOpacity
            style={styles.removeBtn}
            onPress={() => onRemove && onRemove(contact.id)}
            disabled={isBusy}
          >
            {isBusy ? (
              <ActivityIndicator size="small" color="#dc2626" />
            ) : (
              <View style={{ flexDirection: "row", alignItems: "center" }}>
                <Feather
                  name="trash-2"
                  size={12}
                  color="#b91c1c"
                  style={{ marginRight: 4 }}
                />
                <Text style={styles.removeBtnText}>Remove</Text>
              </View>
            )}
          </TouchableOpacity>
        ) : isSaved ? (
          <View style={styles.savedGroup}>
            <View style={styles.savedBadge}>
              <Feather
                name="check"
                size={11}
                color="#059669"
                style={{ marginRight: 3 }}
              />
              <Text style={styles.savedBadgeText}>Saved</Text>
            </View>
            <TouchableOpacity
              style={styles.removeSmallBtn}
              onPress={() => onRemove && onRemove(contact.id)}
              disabled={isBusy}
            >
              {isBusy ? (
                <ActivityIndicator size="small" color="#dc2626" />
              ) : (
                <Text style={styles.removeSmallText}>Remove</Text>
              )}
            </TouchableOpacity>
          </View>
        ) : (
          <TouchableOpacity
            style={styles.saveBtn}
            onPress={() => onSave && onSave(contact.id)}
            disabled={isBusy}
          >
            {isBusy ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <View style={{ flexDirection: "row", alignItems: "center" }}>
                <Feather
                  name="bookmark"
                  size={12}
                  color="#ffffff"
                  style={{ marginRight: 4 }}
                />
                <Text style={styles.saveBtnText}>Save</Text>
              </View>
            )}
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 12,
    padding: 12,
    marginVertical: 4,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 8,
  },
  name: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0f172a",
  },
  title: {
    fontSize: 12,
    color: "#475569",
    marginTop: 2,
  },
  locationRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 2,
  },
  location: {
    fontSize: 11,
    color: "#64748b",
  },
  badge: {
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 6,
    borderWidth: 1,
  },
  badgeAmber: {
    backgroundColor: "#fffbeb",
    borderColor: "#fde68a",
  },
  badgeGreen: {
    backgroundColor: "#ecfdf5",
    borderColor: "#a7f3d0",
  },
  badgeText: {
    fontSize: 9,
    fontWeight: "600",
  },
  badgeTextAmber: {
    color: "#92400e",
  },
  badgeTextGreen: {
    color: "#065f46",
  },
  sourcesRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 4,
    marginTop: 8,
  },
  sourceTag: {
    backgroundColor: "#f1f5f9",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  sourceTagText: {
    fontSize: 9,
    color: "#475569",
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 8,
  },
  sourceBtn: {
    flexDirection: "row",
    alignItems: "center",
  },
  sourceLink: {
    fontSize: 10,
    color: "#4f46e5",
    fontWeight: "600",
    textDecorationLine: "underline",
  },
  metaDate: {
    fontSize: 10,
    color: "#64748b",
  },
  actionsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 6,
    borderTopWidth: 1,
    borderTopColor: "#f1f5f9",
    paddingTop: 8,
    marginTop: 8,
  },
  draftBtn: {
    backgroundColor: "#eef2ff",
    borderWidth: 1,
    borderColor: "#c7d2fe",
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  draftBtnText: {
    fontSize: 11,
    fontWeight: "600",
    color: "#4338ca",
  },
  saveBtn: {
    backgroundColor: "#4f46e5",
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  saveBtnText: {
    fontSize: 11,
    fontWeight: "600",
    color: "#ffffff",
  },
  savedGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  savedBadge: {
    backgroundColor: "#ecfdf5",
    borderWidth: 1,
    borderColor: "#a7f3d0",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  savedBadgeText: {
    fontSize: 10,
    fontWeight: "600",
    color: "#059669",
  },
  removeSmallBtn: {
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  removeSmallText: {
    fontSize: 10,
    color: "#dc2626",
    fontWeight: "500",
  },
  removeBtn: {
    backgroundColor: "#fef2f2",
    borderWidth: 1,
    borderColor: "#fecaca",
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  removeBtnText: {
    fontSize: 11,
    fontWeight: "600",
    color: "#b91c1c",
  },
});
