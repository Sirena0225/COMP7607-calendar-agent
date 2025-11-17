import React, { useState } from "react";
import { View, TextInput, Button, FlatList } from "react-native";
import ChatBubble from "../components/ChatBubble";
import { sendChat } from "../api/chatApi";

export default function AssistantScreen() {
  const [messages, setMessages] = useState<{ text: string; fromUser: boolean }[]>([]);
  const [input, setInput] = useState("");

  const handleSend = async () => {
    if (!input.trim()) return;

    const newMsgs = [...messages, { text: input, fromUser: true }];
    setMessages(newMsgs);

    const reply = await sendChat(input);
    setMessages([...newMsgs, { text: reply, fromUser: false }]);
    setInput("");
  };

  return (
    <View style={{ flex: 1, padding: 16, backgroundColor: "#f5f5f5" }}>
      <FlatList
        data={messages}
        renderItem={({ item }) => <ChatBubble message={item} />}
      />

      <View style={{ flexDirection: "row", marginTop: 8 }}>
        <TextInput
          style={{ flex: 1, borderWidth: 1, padding: 10, borderRadius: 8 }}
          placeholder="请输入指令..."
          value={input}
          onChangeText={setInput}
        />
        <Button title="发送" onPress={handleSend} />
      </View>
    </View>
  );
}


