import Ionicons from '@expo/vector-icons/Ionicons';
import { Tabs } from 'expo-router';

import { useTheme } from '@/lib/use-theme';

export default function TabsLayout() {
  const t = useTheme();
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: t.primary, tabBarInactiveTintColor: t.textSecondary }}>
      <Tabs.Screen
        name="index"
        options={{
          title: 'Agenda',
          headerShown: false,
          tabBarIcon: ({ color, size }) => <Ionicons name="calendar" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="pacientes"
        options={{
          title: 'Pacientes',
          tabBarIcon: ({ color, size }) => <Ionicons name="paw" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="internados"
        options={{
          title: 'Internados',
          tabBarIcon: ({ color, size }) => <Ionicons name="bed" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="perfil"
        options={{
          title: 'Mi cuenta',
          tabBarIcon: ({ color, size }) => <Ionicons name="person-circle" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
