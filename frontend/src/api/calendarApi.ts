import axios from 'axios';
const BASE='http://192.168.8.9:8000'; // 替换为展示机IP
export const getEvents = async()=>{
  const res = await axios.get(`${BASE}/debug/calendar_events`);
  return res.data.events;
};
