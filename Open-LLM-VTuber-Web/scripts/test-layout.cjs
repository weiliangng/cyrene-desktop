const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const vm = require('node:vm');
const filename = path.join(__dirname, '../src/renderer/src/pet/layout.ts');
const exportsObject = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, { exports: exportsObject });
const { PET_LAYOUT_KEY, isPetLayout, readPetLayout, savePetLayout } = exportsObject;
const data = new Map();
let writes = 0;
const storage = { getItem: key => data.get(key) ?? null, setItem: (key, value) => { data.set(key, value); writes++; } };
assert.equal(readPetLayout(storage), null);
const matrix = [0.42,0,0,0,0,0.42,0,0,0,0,1,0,1.2,-0.8,0,1];
assert.ok(savePetLayout(storage, new Float32Array(matrix)));
const restored = readPetLayout(storage);
assert.deepEqual(Array.from(restored.matrix), Array.from(new Float32Array(matrix)));
savePetLayout(storage, new Float32Array(matrix));
assert.equal(writes, 1, 'stationary layout does not repeatedly write storage');
assert.equal(isPetLayout({version:1,matrix:[1,2]}), false);
assert.equal(isPetLayout({version:1,matrix:[Infinity,...matrix.slice(1)]}), false);
assert.equal(isPetLayout({version:2,matrix}), false);
assert.equal(isPetLayout({version:1,matrix:[-1,...matrix.slice(1)]}), false);
data.set(PET_LAYOUT_KEY, '{broken');
assert.equal(readPetLayout(storage), null, 'corrupt preferences do not prevent startup');
console.log('Layout checks passed: exact Float32 position/scale round trip, unchanged-write suppression, and invalid/corrupt settings.');
