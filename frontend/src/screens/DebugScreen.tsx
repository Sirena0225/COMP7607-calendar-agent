import React, { useState } from "react";
import { View, Text, TextInput, Button, FlatList } from "react-native";
import { parseIntent } from "../api/intentApi";
import { getConversationState, getAllDBEvents } from "../api/debugApi";
import JsonViewer from "../components/JsonViewer";
import EventCard from "../components/EventCard";

export default function DebugScreen() {
  const [intentResult, setIntentResult] = useState<any>(null);
  const [convState, setConvState] = useState<any>(null);
  const [dbEvents, setDbEvents] = useState<any[]>([]);
  const [input, setInput] = useState("");

  const handleParse = async () => {
    const res = await parseIntent(input);
    setIntentResult(res);
  };

  const loadConv = async () => {
    setConvState(await getConversationState());
  };

  const loadEvents = async () => {
    setDbEvents(await getAllDBEvents());
  };

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <Text style={{ fontWeight: "bold", fontSize: 18 }}>意图解析</Text>

      <TextInput
        style={{ borderWidth: 1, padding: 8, marginTop: 8 }}
        placeholder="输入一句话：如 '明天下午 3 点开会'"
        value={input}
        onChangeText={setInput}
      />

      <Button title="解析意图" onPress={handleParse} />

      {intentResult && (
        <View style={{ marginTop: 12 }}>
          <JsonViewer data={intentResult} />
        </View>
      )}

      <View style={{ marginTop: 20 }}>
        <Button title="查看对话上下文" onPress={loadConv} />
        {convState && <JsonViewer data={convState} />}
      </View>

      <View style={{ marginTop: 20 }}>
        <Button title="查看数据库事件" onPress={loadEvents} />
        <FlatList
          data={dbEvents}
          renderItem={({ item }) => <EventCard event={item} />}
        />
      </View>
    </View>
  );
}

