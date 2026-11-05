// Compare against the exact release to distinguish pre-existing SDK errors from regressions.
const ts = require('typescript');
const path = require('node:path');
const fs = require('node:fs');
const root = path.resolve(__dirname, '..');
const snapshot = JSON.parse(fs.readFileSync(path.join(__dirname, 'upstream-v1.2.1.json'), 'utf8'));
const originals = new Map(Object.entries(snapshot).map(([p, content]) => [path.resolve(root, p).toLowerCase(), content]));
function check(baseline) {
  const config = ts.readConfigFile(path.join(root, 'tsconfig.web.json'), ts.sys.readFile);
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, root);
  const host = ts.createCompilerHost(parsed.options);
  const read = host.readFile;
  if (baseline) host.readFile = p => originals.get(path.resolve(p).toLowerCase()) ?? read(p);
  const program = ts.createProgram(parsed.fileNames, { ...parsed.options, noEmit: true, incremental: false }, host);
  return ts.getPreEmitDiagnostics(program).map(d => ({
    file: path.relative(root, d.file?.fileName || root), code: d.code,
    message: ts.flattenDiagnosticMessageText(d.messageText, '\n'),
  }));
}
const baseline = check(true);
const current = check(false);
const counts = new Map();
baseline.forEach(d => { const key = JSON.stringify(d); counts.set(key, (counts.get(key) || 0) + 1); });
const added = current.filter(d => { const key = JSON.stringify(d); const count = counts.get(key) || 0; if (count) { counts.set(key, count - 1); return false; } return true; });
const report = { upstreamErrors: baseline.length, currentErrors: current.length, newErrors: added };
fs.writeFileSync(path.join(root, 'cyrene-typecheck.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
process.exitCode = added.length ? 1 : 0;
