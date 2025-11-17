import React from "react";
import { View, Text } from "react-native";

export default function EventCard({ event }: { event: any }) {
  return (
    <View style={{
      padding: 12,
      backgroundColor: "white",
      borderRadius: 12,
      marginVertical: 6,
      elevation: 2
    }}>
      <Text style={{ fontWeight: "bold", fontSize: 16 }}>{event.title}</Text>
      <Text>开始：{event.start_time}</Text>
      <Text>结束：{event.end_time}</Text>
      {event.location ? <Text>地点：{event.location}</Text> : null}
    </View>
  );
}
