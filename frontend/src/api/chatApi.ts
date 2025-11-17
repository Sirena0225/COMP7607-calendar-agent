import axios from 'axios';
const BASE='http://192.168.8.9:8000'; // 替换为展示机IP
export const sendChat = async(text: String)=>{
  const res = await axios.post(`${BASE}/api/chat`, {text});
  return res.data.reply;
};
