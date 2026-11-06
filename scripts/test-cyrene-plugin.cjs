const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.resolve(__dirname, '../integrations/openclaw/cyrene-plugin/index.mjs'), 'utf8')
  .replace(/^import .*;\r?\n/gm, '').replace('export default definePluginEntry', 'return definePluginEntry');
const requests=[];
const plugin = new Function('readFile','definePluginEntry','fetch',source)(async()=> 'test-token',entry=>entry,async(url,options)=>{
  requests.push(JSON.parse(options.body));
  return { ok:true,json:async()=>({status:'accepted'}) };
});
const hooks={};
plugin.register({ pluginConfig:{tokenFile:'ignored'},registerTool(){},on:(name,fn)=>{hooks[name]=fn;},logger:{warn:message=>{throw new Error(message);}} });
(async()=>{
  const ctx={agentId:'cyrene',sessionKey:'test-session',runId:'test-run'};
  await hooks.before_agent_run({},ctx);
  await hooks.before_tool_call({toolName:'read'},ctx);
  await hooks.agent_end({success:false,error:'HTTP client disconnected'},ctx);
  assert.deepEqual(requests.map(r=>r.name),['task.start','task.progress','task.end']);
  assert.equal(requests[1].data.label,'Using read');
  assert.equal(requests[2].data.status,'cancelled');
  assert.equal(requests[2].data.label,'Cancelled');
  const before=requests.length;
  await hooks.before_agent_run({},{agentId:'other',runId:'other'});
  assert.equal(requests.length,before,'other agents cannot drive Cyrene lifecycle');
  await hooks.before_agent_run({},ctx);
  await hooks.agent_end({success:false,error:'upstream error'},ctx);
  assert.equal(requests.at(-1).data.status,'failed');
  await hooks.before_agent_run({},ctx);
  await hooks.agent_end({success:true},ctx);
  assert.equal(requests.at(-1).data.status,'completed');
  console.log('OpenClaw lifecycle scoping, progress, completion, failure and HTTP-disconnect cancellation passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
