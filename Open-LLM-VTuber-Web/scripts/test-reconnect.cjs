const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Module = require('node:module');
const timers = new Map(); let nextTimer = 0;
global.window = { setTimeout: (fn) => { timers.set(++nextTimer, fn); return nextTimer; }, clearTimeout: (id) => timers.delete(id) };
global.localStorage = { getItem: () => 'saved-ui-thread' };
const sockets = [];
class FakeSocket {
  static CONNECTING = 0; static OPEN = 1;
  readyState = 0; sent = [];
  constructor(url) { this.url = url; sockets.push(this); }
  send(message) { this.sent.push(JSON.parse(message)); }
  close() { this.readyState = 3; this.onclose?.(); }
  open() { this.readyState = 1; this.onopen?.(); }
}
global.WebSocket = FakeSocket;
const file = path.resolve(__dirname, '../src/renderer/src/services/websocket-service.tsx');
const copy = new Module(file);
copy.paths = Module._nodeModulePaths(path.dirname(file));
const originalRequire = copy.require.bind(copy);
copy.require = (id) => id === '@/components/ui/toaster' ? { toaster: { create() {} } } : originalRequire(id);
copy._compile(ts.transpileModule(fs.readFileSync(file,'utf8'), { compilerOptions: { module:ts.ModuleKind.CommonJS, target:ts.ScriptTarget.ES2022 } }).outputText,file);
const { wsService } = copy.exports;
wsService.connect('ws://pet'); const first=sockets[0]; first.open();
assert.equal(wsService.getCurrentState(),'OPEN');
assert.deepEqual(first.sent.find(m => m.type === 'resume-ui-session'), { type: 'resume-ui-session', history_uid: 'saved-ui-thread' });
assert.equal(first.sent.some(m => m.type === 'create-new-history'), false, 'reconnect resumes the same agent session instead of creating a new one');
const oldClose=first.onclose;
first.close(); assert.equal(timers.size,1);
const [id, retry]=[...timers][0]; timers.delete(id); retry();
assert.equal(sockets.length,2);
sockets[1].open(); oldClose();
assert.equal(wsService.getCurrentState(),'OPEN','late events from a retired socket must be ignored');
assert.equal(timers.size,0);
sockets[1].close(); assert.equal(timers.size,1);
wsService.disconnect(); assert.equal(timers.size,0,'explicit disconnect must cancel retry');
assert.equal(wsService.getCurrentState(),'CLOSED');
console.log('WebSocket reconnect, stale socket protection and explicit disconnect passed.');
