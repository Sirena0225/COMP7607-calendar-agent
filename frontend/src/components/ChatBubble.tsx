import React from "react";
import { View, Text } from "react-native";

export default function ChatBubble({ message }: { message: { text: string; fromUser: boolean } }) {
  return (
    <View
      style={{
        alignSelf: message.fromUser ? "flex-end" : "flex-start",
        backgroundColor: message.fromUser ? "#4e9bff" : "#e0e0e0",
        padding: 10,
        marginVertical: 4,
        maxWidth: "75%",
        borderRadius: 12,
      }}
    >
      <Text style={{ color: message.fromUser ? "white" : "black" }}>{message.text}</Text>
    </View>
  );
}
