import { create } from 'zustand';
import { PetActivity, ActivitySource } from './activity';

const activity = new PetActivity();

export const usePetActivity = create<{
  sleeping: boolean;
  setActivity: (source: ActivitySource, active: boolean) => void;
  tick: () => void;
  sleep: () => void;
}>((set) => ({
  sleeping: true,
  sleep: () => { activity.sleep(); set({ sleeping: true }); },
  setActivity: (source, active) => {
    activity.set(source, active, performance.now());
    set({ sleeping: activity.sleeping });
  },
  tick: () => set({ sleeping: activity.tick(performance.now()) }),
}));
