import { create } from 'zustand';
import { ExternalState } from './external-state';

export const externalState = new ExternalState();
export const useExternalControl = create<{ caption: string; taskLabel: string; refresh: () => void; captionSet: (text: string) => void }>((set) => ({
  caption: '', taskLabel: '',
  captionSet: (caption) => set({ caption }),
  refresh: () => {
    const tasks = externalState.running(Date.now());
    const task = tasks[tasks.length - 1];
    set({ taskLabel: task ? `${task.label || 'Working'}${task.progress == null ? '' : ` ${Math.round(task.progress * 100)}%`}${tasks.length > 1 ? ` (+${tasks.length - 1})` : ''}` : '' });
  },
}));
