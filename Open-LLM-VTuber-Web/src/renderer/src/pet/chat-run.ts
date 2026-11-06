import { create } from 'zustand';

type Phase = 'idle' | 'running' | 'stopping';
const retired = new Set<string>();
export const useChatRun = create<{
  phase: Phase; id: string | null;
  start: (id: string) => boolean;
  stop: (id?: string | null) => boolean;
  finish: (id?: string | null) => boolean;
  reset: () => void;
}>((set, get) => ({
  phase: 'idle', id: null,
  start: (id) => {
    if (retired.has(id)) return false;
    const state = get();
    if (state.id && state.id !== id) return false;
    set({ id, phase: state.phase === 'stopping' ? 'stopping' : 'running' });
    return true;
  },
  stop: (id) => {
    if (id && (retired.has(id) || (get().id && get().id !== id))) return false;
    set({ phase: 'stopping' }); return true;
  },
  finish: (id) => {
    const current = get();
    if (id && (retired.has(id) || (current.id && current.id !== id))) return false;
    if (!id && current.id) return false;
    if (id) { retired.add(id); if (retired.size > 256) retired.delete(retired.values().next().value!); }
    set({ phase: 'idle', id: null });
    return true;
  },
  reset: () => { const id = get().id; if (id) retired.add(id); set({ phase: 'idle', id: null }); },
}));
