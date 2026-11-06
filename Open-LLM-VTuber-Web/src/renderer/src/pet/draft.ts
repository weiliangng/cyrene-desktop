import { create } from 'zustand';

// Paths are inserted visibly into the editable draft. No upload, file read or automatic send.
export function appendFilePaths(text: string, paths: string[]) {
  const unique = [...new Set(paths.filter((path) => typeof path === 'string' && path.length > 0))];
  return unique.length ? `${text}${text && !text.endsWith('\n') ? '\n' : ''}${unique.map((path) => JSON.stringify(path)).join('\n')}` : text;
}

export const useDraft = create<{ text: string; setText: (text: string) => void; addPaths: (paths: string[]) => void }>((set) => ({
  text: '',
  setText: (text) => set({ text }),
  addPaths: (paths) => set((state) => ({ text: appendFilePaths(state.text, paths) })),
}));
