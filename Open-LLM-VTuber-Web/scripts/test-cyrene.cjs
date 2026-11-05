const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
function load(relative) {
  const filename = path.resolve(__dirname, '..', relative);
  const exports = {};
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  });
  vm.runInNewContext(compiled.outputText, { exports, require, Set, Infinity }, { filename });
  return exports;
}
const { PetActivity } = load('src/renderer/src/pet/activity.ts');
const pet = new PetActivity();
assert.equal(pet.tick(0), true, 'starts asleep');
pet.set('model', true, 10);
assert.equal(pet.tick(20000), false, 'stays awake under a stationary cursor');
pet.set('model', false, 20001);
assert.equal(pet.tick(25000), false, 'waits the full five seconds after leaving');
assert.equal(pet.tick(25001), true, 'returns to sleep at the deadline');
pet.set('panel', true, 26000);
pet.set('focus', true, 26001);
pet.set('panel', false, 26002);
assert.equal(pet.tick(40000), false, 'focused input keeps her awake after the mouse leaves');
pet.set('draft', true, 40001);
pet.set('focus', false, 40002);
assert.equal(pet.tick(50000), false, 'an unsent draft keeps the panel open');
pet.set('draft', false, 50001);
pet.set('conversation', true, 52000);
assert.equal(pet.tick(100000), false, 'speech/listening does not time out');
pet.set('conversation', false, 100001);
assert.equal(pet.tick(105001), true, 'sleeps after the conversation ends');
pet.set('model', true, 105002);
assert.equal(pet.sleeping, false, 'can wake again after sleeping');

const runtime = load('src/renderer/src/pet/cyrene-runtime.ts');
const config = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../Open-LLM-VTuber/frontend/cyrene-preview-config.json')));
assert.deepEqual(JSON.parse(JSON.stringify(runtime.keyParameters)), config.keyParameters, 'preserves the verified keyboard mapping');
runtime.heldKeys.add('q');
assert.equal(runtime.keyboardValues().Param35, 1);
assert.equal(runtime.keyboardValues().CatParamLeftHandDown, 1);
runtime.heldKeys.clear();
assert.equal(runtime.keyboardValues().Param35, 0);
assert.equal(runtime.keyboardValues().CatParamLeftHandDown, 0);
assert.equal(runtime.hiddenLayers.Param24, 1);
for (const id of ['Param23', 'Param25', 'Param26', 'Param27', 'Param28']) assert.equal(runtime.hiddenLayers[id], -1);
console.log('Cyrene checks passed: initial sleep, hover, timeout, focus, draft, speech, repeated wake, keyboard and hidden layers.');
