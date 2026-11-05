const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../Open-LLM-VTuber');
const context = {console, process, require, Buffer, __dirname: path.join(root, 'frontend/libs'), setTimeout, clearTimeout, module: {exports: {}}, exports: {}};
context.window = {};
context.document = {currentScript: {src: 'http://127.0.0.1:12393/libs/live2dcubismcore.js'}};
vm.createContext(context);
const source = fs.readFileSync(path.join(root, 'frontend/libs/live2dcubismcore.js'), 'utf8');
vm.runInContext(source.replace('var _em = _em_module();', 'var _em = _em_module(); window.__cubismReady = _em;'), context);
async function verify() {
await new Promise(resolve => context.window.__cubismReady.then(() => resolve()));
const core = context.Live2DCubismCore;
const data = fs.readFileSync(path.join(root, 'live2d-models/cyrene/cyrene.moc3'));
const bytes = data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
const moc = core.Moc.fromArrayBuffer(bytes);
if (!moc) throw Error('Cubism could not load the model');
const model = core.Model.fromMoc(moc);
if (!model) throw Error('Cubism could not instantiate the model');
const config = JSON.parse(fs.readFileSync(path.join(root, 'frontend/cyrene-preview-config.json')));
const lookup = new Map(Array.from(model.parameters.ids, (name, i) => [name, i]));
const baseline = model.parameters.values.slice();
const animationIds = ['Param23', 'Param25', 'Param26', 'Param27', 'Param28'];
for (const id of animationIds) {
  if (model.parameters.defaultValues[lookup.get(id)] !== -1) throw Error(`Unexpected hidden state for ${id}`);
  model.parameters.values[lookup.get(id)] = 0;
}
model.update();
const zeroStateOpacities = Array.from(model.drawables.opacities);
model.parameters.values.set(baseline);
model.update();
const overlayIndices = zeroStateOpacities.map((value, index) => ({value, index}))
  .filter(({value, index}) => value > 0.01 && model.drawables.opacities[index] < 0.01)
  .map(({index}) => index);
if (overlayIndices.length === 0) throw Error('No animation overlay geometry detected for regression check');
const expressionChecks = [];
for (const name of config.expressions) {
  model.parameters.values.set(baseline);
  const expression = JSON.parse(fs.readFileSync(path.join(root, 'live2d-models/cyrene', name + '.exp3.json')));
  for (const parameter of expression.Parameters) {
    const index = lookup.get(parameter.Id);
    if (index === undefined) throw Error(`Unknown expression parameter ${parameter.Id}`);
    const value = parameter.Blend === 'Add' ? baseline[index] + parameter.Value : parameter.Value;
    model.parameters.values[index] = Math.min(model.parameters.maximumValues[index], Math.max(model.parameters.minimumValues[index], value));
  }
  model.update();
  const finite = model.drawables.vertexPositions.every(vertices => vertices.every(Number.isFinite));
  if (!finite) throw Error(`Non-finite model vertices for ${name}`);
  for (const id of animationIds) {
    if (model.parameters.values[lookup.get(id)] !== -1) throw Error(`Animation overlay parameter ${id} active in ${name}`);
  }
  if (overlayIndices.some(index => model.drawables.opacities[index] > 0.01)) throw Error(`Animation overlay visible in ${name}`);
  expressionChecks.push(name);
}
for (const parameter of [...Object.values(config.keyParameters), 'CatParamLeftHandDown', 'ParamMouthOpenY']) {
  if (!lookup.has(parameter)) throw Error(`Missing interactive parameter ${parameter}`);
}
const html = fs.readFileSync(path.join(root, 'frontend/cyrene-preview.html'), 'utf8');
new vm.Script(html.match(/<script>([\s\S]*?)<\/script>/)[1]);
const report = {loadedWithInstalledCubismCore: true, parameters: model.parameters.count, drawables: model.drawables.count,
                facialPresetsValidated: expressionChecks, keyboardParametersValidated: true, previewJavaScriptSyntax: true,
                hiddenAnimationOverlayPieces: overlayIndices.length, animationHiddenAcrossFacialPresets: true};
fs.writeFileSync(path.join(root, 'cyrene-core-verification.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report));
model.release();
moc._release();
}
verify().catch(error => { console.error(error.stack); process.exitCode = 1; });
