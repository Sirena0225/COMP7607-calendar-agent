import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import AssistantScreen from "../screens/AssistantScreen";
import CalendarScreen from "../screens/CalendarScreen";
import DebugScreen from "../screens/DebugScreen";

const Tab = createBottomTabNavigator();

export default function BottomTabs() {
  return (
    <Tab.Navigator screenOptions={{ headerShown: true }}>
      <Tab.Screen name="智能助手" component={AssistantScreen} />
      <Tab.Screen name="日历" component={CalendarScreen} />
      <Tab.Screen name="调试工具" component={DebugScreen} />
    </Tab.Navigator>
  );
}
