import { readFile } from 'node:fs/promises';
import { definePluginEntry } from 'openclaw/plugin-sdk/plugin-entry';

export default definePluginEntry({
  id: 'cyrene', name: 'Cyrene Desktop', description: 'Control the local Cyrene desktop companion and report agent activity.',
  register(api) {
    const config = api.pluginConfig ?? {};
    const baseUrl = config.baseUrl ?? 'http://127.0.0.1:12393/api/cyrene';
    const tasks = new Map();
    const runs = new Map();
    async function request(path, body) {
      const token = (await readFile(config.tokenFile, 'utf8')).trim();
      const response = await fetch(baseUrl + path, {
        method: body === undefined ? 'GET' : 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(4000),
      });
      if (!response.ok) throw new Error(`Cyrene ${response.status}: ${(await response.text()).slice(0, 500)}`);
      return response.json();
    }
    const command = (name, data, request_id) => request('/commands', { name, data, source: 'openclaw', request_id });
    const result = (value) => ({ content: [{ type: 'text', text: JSON.stringify(value) }], details: value });
    api.registerTool({
      name: 'cyrene_state', label: 'Cyrene status',
      description: 'Read the actual desktop connection, readiness, expressions, layout, current tasks and event cursor.',
      parameters: { type: 'object', properties: {}, additionalProperties: false },
      async execute() { return result(await request('/state')); },
    });
    api.registerTool({
      name: 'cyrene_control', label: 'Control Cyrene',
      description: 'Control the desktop UI. Wake/sleep is application-owned; expression.set never wakes the pet, sleep is reserved, and task transitions override expressions. Commands: expression.set {name,duration_ms?}; subtitle.set {text,duration_ms?}; speech.say {text,expression?,speak?}; task.start/progress/end {task_id,label?,progress? (0..1),status?}; pet.wake/sleep; ui.visibility {visible}; layout.set {matrix}; interrupt. Use subtitles for notifications. Ordinary chat is already displayed by the app, so do not speak it again with this tool. A receipt means accepted, not necessarily applied; read events for acknowledgements.',
      parameters: { type: 'object', properties: {
        name: { type: 'string', enum: ['expression.set', 'subtitle.set', 'speech.say', 'task.start', 'task.progress', 'task.end', 'ui.visibility', 'layout.set', 'interrupt'] },
        data: { type: 'object', additionalProperties: true },
        request_id: { type: 'string', description: 'Optional idempotency key; reuse only for retrying the same command.' },
      }, required: ['name', 'data'], additionalProperties: false },
      async execute(_id, params) { return result(await command(params.name, params.data, params.request_id)); },
    });
    api.registerTool({
      name: 'cyrene_events', label: 'Cyrene events',
      description: 'Read recent pet acknowledgements, input/output and task events after a cursor. No recursive agent invocation.',
      parameters: { type: 'object', properties: { after: { type: 'integer', minimum: 0 } }, additionalProperties: false },
      async execute(_id, params) { return result(await request(`/events?after=${params.after ?? 0}`)); },
    });
    const scope = (ctx) => ctx.agentId === (config.agentId ?? 'cyrene');
    const safe = async (fn) => { try { await fn(); } catch (error) { api.logger.warn(`Cyrene activity hook: ${error.message}`); } };
    api.on('before_agent_run', async (_event, ctx) => {
      if (!scope(ctx)) return;
      const id = `openclaw:${ctx.runId ?? crypto.randomUUID()}`;
      const key = ctx.sessionKey ?? ctx.sessionId ?? id;
      tasks.set(key, id);
      if (ctx.runId) runs.set(ctx.runId, id);
      await safe(() => command('task.start', { task_id: id, label: 'Thinking', timeout_ms: 300000 }, `${id}:start`));
    });
    api.on('before_tool_call', async (event, ctx) => {
      if (!scope(ctx)) return;
      const id = runs.get(ctx.runId) ?? tasks.get(ctx.sessionKey ?? ctx.sessionId);
      if (id) await safe(() => command('task.progress', { task_id: id, label: `Using ${event.toolName}`, timeout_ms: 300000 }));
    });
    api.on('agent_end', async (event, ctx) => {
      if (!scope(ctx)) return;
      const key = ctx.sessionKey ?? ctx.sessionId;
      const id = runs.get(event.runId ?? ctx.runId) ?? tasks.get(key);
      if (!id) return;
      tasks.delete(key); runs.delete(event.runId ?? ctx.runId);
      const status = /abort|cancel|client disconnected/i.test(String(event.error ?? '')) ? 'cancelled' : event.success === false ? 'failed' : 'completed';
      await safe(() => command('task.end', { task_id: id, status, label: status === 'cancelled' ? 'Cancelled' : status === 'failed' ? 'Task failed' : 'Done' }, `${id}:end`));
    });
  },
});
