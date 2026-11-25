import React from "react";
import { View, Text, StyleSheet } from "react-native";

/** 3D Universe is intentionally unavailable on Native while under development. */
export function SpatialNavigationScreen() {
  return (
    <View style={styles.container} accessibilityRole="summary">
      <Text style={styles.title}>3D Universe</Text>
      <Text style={styles.message}>Sedang dalam tahap pengembangan</Text>
      <Text style={styles.detail}>Fitur ini sementara tidak dapat diakses oleh siapa pun.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24, backgroundColor: "#0B1220" },
  title: { color: "#FFFFFF", fontSize: 22, fontWeight: "700", marginBottom: 12 },
  message: { color: "#B9D7FF", fontSize: 16, fontWeight: "600", textAlign: "center" },
  detail: { color: "#AAB7C8", fontSize: 13, textAlign: "center", marginTop: 8 },
});
