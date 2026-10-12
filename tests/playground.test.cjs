const {test} = require('node:test');
const assert = require('node:assert/strict');
const {endpoint, compilePrompt, payload} = require('../playground-core.js');
test('normalize endpoint IDs and run/runSync URLs while restricting credential destination', () => {
  assert.equal(endpoint('my-endpoint'), 'https://api.runpod.ai/v2/my-endpoint');
  assert.equal(endpoint('https://api.runpod.ai/v2/abc/runsync/'), 'https://api.runpod.ai/v2/abc');
  for (const value of ['https://evil.test/v2/a', 'http://api.runpod.ai/v2/a', 'https://api.runpod.ai.evil.test/v2/a', 'https://api.runpod.ai/v2/a?x=1']) assert.throws(() => endpoint(value));
});
test('space-tolerant mentions translate into the native ordered references', () => {
  const refs = [{id: 1}, {id: 2}];
  assert.equal(compilePrompt("@picture1 is the character; follow @picture 2's pose.", refs), "Picture 1 is the character; follow Picture 2's pose.");
  assert.equal(compilePrompt('@PICTURE2 and @picture1', refs), 'Picture 2 and Picture 1');
});
test('removal preserves reference identities and missing mentions block submission', () => {
  assert.equal(compilePrompt('@picture3', [{id: 1}, {id: 3}]), 'Picture 2');
  assert.throws(() => compilePrompt('@picture2', [{id: 1}, {id: 3}]), /no uploaded image/);
  assert.throws(() => compilePrompt('@picture', []), /Complete/);
});
test('payload matches worker contract, preserves order, and excludes credentials and sampling knobs', () => {
  const value = payload({prompt:'@picture3', width:'1024', height:'768', seed:'-1', key:'secret', endpoint:'abc'}, [{id:3, data:'abc'}]);
  assert.deepEqual(value, {input:{prompt:'Picture 1', width:1024, height:768, seed:-1, images:[{name:'picture3', image:'abc'}]}});
  assert.equal(JSON.stringify(value).includes('secret'), false);
});
test('reject invalid dimensions, unsafe seeds, reference count and oversized RunPod payloads', () => {
  const s = {prompt:'A portrait', width:'1024', height:'1024', seed:'42'};
  for (const width of ['255','1025','2049']) assert.throws(() => payload({...s,width}, []));
  for (const seed of ['', '-2', '1.5', '9007199254740993']) assert.throws(() => payload({...s,seed}, []));
  assert.throws(() => payload(s, Array.from({length:11}, (_,i) => ({id:i+1,data:'a'}))), /ten/);
  assert.throws(() => payload(s, [{id:1,data:'a'.repeat(9_500_000)}]), /budget/);
});
