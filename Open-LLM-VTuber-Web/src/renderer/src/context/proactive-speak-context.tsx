import { createContext, useContext, ReactNode } from 'react';

interface ProactiveSpeakSettings {
  allowButtonTrigger: boolean;
  allowProactiveSpeak: boolean;
  idleSecondsToSpeak: number;
}
interface ProactiveSpeakContextType {
  settings: ProactiveSpeakSettings;
  updateSettings: (settings: ProactiveSpeakSettings) => void;
}
// Autonomous schedules and event triggers belong to OpenClaw. Legacy saved settings
// cannot start UI timers, capture media or fabricate idle prompts in this desktop build.
const value: ProactiveSpeakContextType = {
  settings: { allowButtonTrigger: false, allowProactiveSpeak: false, idleSecondsToSpeak: 5 },
  updateSettings: () => {},
};
export const ProactiveSpeakContext = createContext<ProactiveSpeakContextType>(value);
export function ProactiveSpeakProvider({ children }: { children: ReactNode }) {
  return <ProactiveSpeakContext.Provider value={value}>{children}</ProactiveSpeakContext.Provider>;
}
export function useProactiveSpeak() { return useContext(ProactiveSpeakContext); }
