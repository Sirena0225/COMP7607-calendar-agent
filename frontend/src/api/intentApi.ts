import axios from "axios";
const BASE_URL = "http://192.168.8.9:8000";

export const parseIntent = async (text: string) => {
  const res = await axios.post(`${BASE_URL}/debug/parse_intent?text=${text}`);
  return res.data;
};
