/* Shared browser/Node helpers. No credentials are included in request JSON. */
(function (root) {
  'use strict';
  function endpoint(value) {
    value = value.trim();
    if (/^[a-zA-Z0-9_-]+$/.test(value)) value = 'https://api.runpod.ai/v2/' + value;
    let url;
    try { url = new URL(value); } catch { throw new Error('Enter a RunPod endpoint ID or API URL.'); }
    if (url.origin !== 'https://api.runpod.ai' || url.username || url.password || url.search || url.hash ||
        !/^\/v2\/[a-zA-Z0-9_-]+(?:\/(?:run|runsync))?\/?$/.test(url.pathname)) {
      throw new Error('Use https://api.runpod.ai/v2/YOUR_ENDPOINT_ID (a /run or /runsync suffix is also accepted).');
    }
    return url.origin + url.pathname.replace(/\/(run|runsync)\/?$/, '').replace(/\/$/, '');
  }
  function compilePrompt(prompt, refs) {
    if (!prompt.trim() || prompt.length > 16384) throw new Error('Write a prompt of 1–16,384 characters.');
    const result = prompt.replace(/@picture\s*(\d+)\b/gi, (_, id) => {
      const index = refs.findIndex(ref => ref.id === Number(id));
      if (index < 0) throw new Error('@picture' + id + ' has no uploaded image. Add it or change the mention.');
      return 'Picture ' + (index + 1);
    });
    if (/@picture\b/i.test(result)) throw new Error('Complete the reference mention, for example @picture1.');
    return result;
  }
  function payload(settings, refs) {
    if (refs.length > 10) throw new Error('You can upload at most ten reference images.');
    const input = {prompt: compilePrompt(settings.prompt, refs)};
    for (const key of ['width', 'height']) {
      const n = Number(settings[key]);
      if (!Number.isInteger(n) || n < 256 || n > 2048 || n % 32) throw new Error(key + ' must be 256–2048, in multiples of 32.');
      input[key] = n;
    }
    const seed = Number(settings.seed);
    if (String(settings.seed).trim() === '' || !Number.isSafeInteger(seed) || seed < -1) throw new Error('Seed must be -1 (random) or a nonnegative safe integer.');
    input.seed = seed;
    input.images = refs.map(ref => ({name: 'picture' + ref.id, image: ref.data}));
    const body = {input};
    if (new TextEncoder().encode(JSON.stringify(body)).length > 9_500_000) throw new Error('References exceed the request budget. Remove an image or use smaller files.');
    return body;
  }
  const api = {endpoint, compilePrompt, payload};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.QwenPlayground = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
