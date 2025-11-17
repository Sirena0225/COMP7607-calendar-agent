import React, { useEffect, useState } from "react";
import { View, FlatList } from "react-native";
import { Calendar } from "react-native-calendars";
import { getEvents } from "../api/calendarApi";
import EventCard from "../components/EventCard";

export default function CalendarScreen() {
  const [events, setEvents] = useState<any[]>([]);
  const [selectedDate, setSelectedDate] = useState("");

  useEffect(() => {
    load();
  }, []);

  const load = async () => {
    const res = await getEvents();
    setEvents(res);
  };

  const eventsForDay = events.filter(
    (e) => e.start_time.split("T")[0] === selectedDate
  );

  return (
    <View style={{ flex: 1, padding: 12 }}>
      <Calendar onDayPress={(d) => setSelectedDate(d.dateString)} />

      <FlatList
        data={eventsForDay}
        renderItem={({ item }) => <EventCard event={item} />}
      />
    </View>
  );
}
