import axios from "axios";

const BASE_URL = "http://1192.168.8.9:8000";

export const getConversationState = async () => {
  const res = await axios.get(`${BASE_URL}/debug/conversation_state`);
  return res.data;
};

export const getAllDBEvents = async () => {
  const res = await axios.get(`${BASE_URL}/debug/calendar_events`);
  return res.data.events;
};
