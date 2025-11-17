import React from "react";
import { View, Text } from "react-native";

export default function JsonViewer({ data }: { data: any }) {
  return (
    <View style={{ backgroundColor: "#222", padding: 10, borderRadius: 8 }}>
      <Text style={{ color: "white", fontFamily: "monospace" }}>
        {JSON.stringify(data, null, 2)}
      </Text>
    </View>
  );
}
