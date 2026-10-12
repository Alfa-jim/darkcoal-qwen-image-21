/* Execute the actual UI controller with a minimal DOM and mocked RunPod API. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const core = require('../playground-core.js');
const script = fs.readFileSync(path.join(__dirname, '../playground.js'), 'utf8');
const STORE = 'darkcoal-qwen21-playground-v1';
class Element {
  constructor() { this.value = ''; this.textContent = ''; this.children = []; this.events = {}; this.classList = {toggle(){},add(){},remove(){}}; }
  addEventListener(name, action) { this.events[name] = action; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute() {}
  click() { return this.events.click?.(); }
}
function harness(responses = [], persisted = new Map()) {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  for (const [id,value] of Object.entries({endpoint:'endpoint123',key:'fake-secret',prompt:'Test prompt',width:'1024',height:'1024',seed:'-1'})) get(id).value = value;
  const calls = [];
  const context = vm.createContext({
    window:{QwenPlayground:core},document:{getElementById:get,querySelectorAll:()=>[],createElement:()=>new Element()},
    localStorage:{getItem:key=>persisted.get(key),setItem:(key,value)=>persisted.set(key,value),removeItem:key=>persisted.delete(key)},
    URL:{createObjectURL:()=> 'blob:mock',revokeObjectURL(){}},Blob,Uint8Array,AbortController,
    atob:value=>Buffer.from(value,'base64').toString('binary'),
    setTimeout:(fn,delay)=> { if (delay !== 45000) queueMicrotask(fn); return 1; },clearTimeout(){},
    fetch:async(url,options)=> {
      calls.push({url,...options}); const response = responses.shift();
      if (response instanceof Error) throw response;
      if (!response) throw new Error('Unexpected API call');
      return {ok:true,json:async()=>response};
    }
  });
  vm.runInContext(script,context);
  return {context,elements,get,calls,persisted,run:code=>vm.runInContext(code,context)};
}
const png = Buffer.from([137,80,78,71,13,10,26,10,0]).toString('base64');
test('one async submission followed by status checks displays output and clears saved job', async () => {
  const h = harness([{id:'job-1'},{status:'IN_QUEUE'},{status:'IN_PROGRESS'},{status:'COMPLETED',executionTime:2000,output:{images:[{type:'base64',data:png}]}}]);
  await h.run('generate()');
  assert.equal(h.calls.filter(call=>call.url.endsWith('/run')).length,1);
  assert.equal(h.calls.length,4);
  assert.equal(h.get('output').children[0].src,'blob:mock');
  assert.equal(h.persisted.has(STORE+'-job'),false);
  assert.equal(h.get('generate').disabled,false);
  assert.equal(JSON.parse(h.calls[0].body).input.prompt,'Test prompt');
});
test('status transport error retains job and resume never resubmits', async () => {
  const h = harness([{id:'job-2'},new Error('Offline'),{status:'COMPLETED',output:{images:[{type:'base64',data:png}]}}]);
  await h.run('generate()');
  assert.equal(h.get('generate').disabled,true);
  assert.equal(JSON.parse(h.persisted.get(STORE+'-job')).id,'job-2');
  await h.run('poll()');
  assert.equal(h.calls.filter(call=>call.method==='POST').length,1);
  assert.equal(h.get('generate').disabled,false);
});
test('restoring a pending job does not auto-submit or poll on load', async () => {
  const persisted = new Map([[STORE+'-job',JSON.stringify({id:'saved',base:'https://api.runpod.ai/v2/endpoint123'})]]);
  const h = harness([],persisted);
  assert.equal(h.calls.length,0);
  assert.equal(h.get('generate').disabled,true);
  assert.equal(h.get('resume').disabled,false);
  assert.match(h.get('notice').textContent,/previous job/);
});
test('failed jobs and completed worker errors unlock generation', async () => {
  for (const response of [{status:'FAILED',error:'GPU OOM'},{status:'COMPLETED',output:{error:'Invalid image'}}]) {
    const h = harness([{id:'failed'},response]); await h.run('generate()');
    assert.equal(h.get('generate').disabled,false);
    assert.equal(h.persisted.has(STORE+'-job'),false);
    assert.match(h.get('notice').textContent,/GPU OOM|Invalid image/);
  }
});
test('uncertain submission is not retried', async () => {
  const h = harness([new Error('Network lost')]); await h.run('generate()');
  assert.equal(h.calls.length,1);
  assert.match(h.get('notice').textContent,/not retried/);
});
test('cancel uses the saved job endpoint and verifies terminal status', async () => {
  const persisted = new Map([[STORE+'-job',JSON.stringify({id:'saved',base:'https://api.runpod.ai/v2/old-endpoint'})]]);
  const h = harness([{status:'CANCELLED'},{status:'CANCELLED'}],persisted);
  await h.get('cancel').click();
  assert.equal(h.calls[0].url,'https://api.runpod.ai/v2/old-endpoint/cancel/saved');
  assert.equal(h.calls[0].method,'POST');
  assert.equal(h.get('generate').disabled,false);
});
test('forget key removes saved secret without discarding other settings', async () => {
  const h = harness(); h.run('save()'); await h.get('forget').click();
  const stored = JSON.parse(h.persisted.get(STORE));
  assert.equal(stored.key,''); assert.equal(stored.endpoint,'endpoint123');
});
