// Keyboard reactions are deliberately limited to this app's message input.
export const heldKeys = new Set<string>();
export const keyParameters: Record<string, string> = {
  tab: 'Param29', '1': 'Param30', '2': 'Param31', '3': 'Param32', '4': 'Param33',
  shift: 'Param34', q: 'Param35', w: 'Param36', e: 'Param37', r: 'Param38',
  ' ': 'Param39', a: 'Param40', s: 'Param41', d: 'Param42', f: 'Param43',
};

export const hiddenLayers: Record<string, number> = {
  Param24: 1, // Creator's watermark-hide preset.
  Param23: -1, Param25: -1, Param26: -1, Param27: -1, Param28: -1,
};

export function keyboardValues(): Record<string, number> {
  const values: Record<string, number> = {};
  Object.entries(keyParameters).forEach(([key, id]) => { values[id] = heldKeys.has(key) ? 1 : 0; });
  values.CatParamLeftHandDown = heldKeys.size ? 1 : 0;
  return values;
}
