export const PET_LAYOUT_KEY = 'cyrene.pet.layout.v1';

export interface PetLayout {
  version: 1;
  matrix: number[];
}

interface LayoutStorage {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
}

export function isPetLayout(value: unknown): value is PetLayout {
  if (!value || typeof value !== 'object') return false;
  const layout = value as PetLayout;
  return layout.version === 1 && Array.isArray(layout.matrix)
    && layout.matrix.length === 16 && layout.matrix.every(Number.isFinite)
    && layout.matrix[0] > 0 && layout.matrix[0] <= 20
    && layout.matrix[5] > 0 && layout.matrix[5] <= 20
    && Math.abs(layout.matrix[12]) <= 100 && Math.abs(layout.matrix[13]) <= 100
    && layout.matrix[15] === 1;
}

export function readPetLayout(storage: LayoutStorage): PetLayout | null {
  try {
    const value: unknown = JSON.parse(storage.getItem(PET_LAYOUT_KEY) || 'null');
    return isPetLayout(value) ? value : null;
  } catch { return null; }
}

export function savePetLayout(storage: LayoutStorage, matrix: ArrayLike<number>): PetLayout | null {
  const layout: PetLayout = { version: 1, matrix: Array.from(matrix) };
  if (!isPetLayout(layout)) return null;
  const json = JSON.stringify(layout);
  try {
    if (storage.getItem(PET_LAYOUT_KEY) !== json) storage.setItem(PET_LAYOUT_KEY, json);
  } catch { return null; }
  return layout;
}
