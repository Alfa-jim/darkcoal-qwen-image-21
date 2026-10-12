'use strict';
const $ = id => document.getElementById(id);
const core = window.QwenPlayground;
const STORE = 'darkcoal-qwen21-playground-v1';
const JOB_STORE = STORE + '-job';
const fields = ['endpoint', 'key', 'prompt', 'width', 'height', 'seed'];
let refs = [], nextRef = 1, uploading = false, busy = false, job = null, pollToken = 0, outputURL = null;
function notice(message, error = false) {
  $('notice').textContent = message; $('notice').classList.toggle('error', error);
}
function readStorage(key) {
  try { return JSON.parse(localStorage.getItem(key) || 'null'); }
  catch { return null; }
}
function writeStorage(key, value) {
  try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, JSON.stringify(value)); return true; }
  catch { $('saved').textContent = 'Browser storage is unavailable. Settings will last for this tab only.'; return false; }
}
function settings() { return Object.fromEntries(fields.map(id => [id, $(id).value])); }
function save() {
  if (writeStorage(STORE, settings())) $('saved').textContent = 'Settings saved in this browser.';
  previewPrompt();
}
const stored = readStorage(STORE);
if (stored && typeof stored === 'object') for (const id of fields) if (typeof stored[id] === 'string') $(id).value = stored[id];
for (const id of fields) $(id).addEventListener('input', save);
function controls() {
  $('generate').disabled = busy || uploading || !!job;
  $('export').disabled = busy || uploading;
  $('add').disabled = busy || uploading || !!job || refs.length >= 10;
  $('jobActions').hidden = !job;
  $('resume').disabled = busy || !job;
  $('cancel').disabled = !job || !job.id;
  for (const button of document.querySelectorAll('.remove')) button.disabled = busy || !!job;
  $('jobLabel').textContent = job ? 'Job ' + job.id + ' · ' + job.base.split('/').pop() : '';
}
function previewPrompt() {
  try { $('compiled').textContent = $('prompt').value.trim() ? core.compilePrompt($('prompt').value, refs) : 'Your translated prompt will appear here.'; }
  catch (e) { $('compiled').textContent = e.message; }
}
function insertMention(id) {
  const input = $('prompt');
  const prefix = input.value.slice(0, input.selectionStart);
  const match = prefix.match(/@(?:picture\s*\d*)?$/i);
  const start = match ? input.selectionStart - match[0].length : input.selectionStart;
  input.setRangeText('@picture' + id + ' ', start, input.selectionEnd, 'end');
  input.focus(); $('mentions').hidden = true; save();
}
function mentionButton(ref) {
  const button = document.createElement('button'); button.type = 'button'; button.className = 'mention';
  button.textContent = '@picture' + ref.id; button.addEventListener('click', () => insertMention(ref.id)); return button;
}
function suggestions() {
  const prefix = $('prompt').value.slice(0, $('prompt').selectionStart);
  const match = prefix.match(/@(?:picture\s*(\d*))?$/i);
  $('mentions').replaceChildren();
  const matches = match ? refs.filter(ref => !match[1] || String(ref.id).startsWith(match[1])) : [];
  for (const ref of matches) $('mentions').append(mentionButton(ref));
  $('mentions').hidden = !matches.length;
}
$('prompt').addEventListener('input', suggestions);
$('prompt').addEventListener('click', suggestions);
$('prompt').addEventListener('keydown', event => {
  if (event.key === 'Escape') $('mentions').hidden = true;
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !$('generate').disabled) { event.preventDefault(); generate(); }
});
function renderRefs() {
  $('references').replaceChildren(); $('dropHint').hidden = refs.length > 0;
  $('refCount').textContent = refs.length + ' / 10 references';
  for (const ref of refs) {
    const box = document.createElement('div'); box.className = 'reference';
    const img = document.createElement('img'); img.src = ref.data; img.alt = 'Reference picture ' + ref.id;
    const row = document.createElement('div'); row.className = 'refline'; row.append(mentionButton(ref));
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'remove'; remove.textContent = '×';
    remove.setAttribute('aria-label', 'Remove picture ' + ref.id); remove.disabled = busy || !!job;
    remove.addEventListener('click', () => { refs = refs.filter(item => item.id !== ref.id); renderRefs(); }); row.append(remove);
    const name = document.createElement('span'); name.className = 'filename'; name.textContent = ref.filename; name.title = ref.filename;
    box.append(img, row, name); $('references').append(box);
  }
  previewPrompt(); suggestions(); controls();
}
async function prepareImage(file) {
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) throw new Error(file.name + ': use PNG, JPEG or WebP.');
  if (file.size > 40 * 1024 * 1024) throw new Error(file.name + ': file is over 40 MB. Resize it first.');
  const bitmap = await createImageBitmap(file, {imageOrientation: 'from-image'});
  try {
    if (bitmap.width * bitmap.height > 20_000_000) throw new Error(file.name + ': image exceeds 20 megapixels. Resize it first.');
    const scale = Math.min(1, 1024 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas'); canvas.width = Math.max(1, Math.round(bitmap.width * scale)); canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const ctx = canvas.getContext('2d', {willReadFrequently: true}); ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    let alpha = false; for (let i = 3; i < pixels.length; i += 4) if (pixels[i] !== 255) { alpha = true; break; }
    const data = canvas.toDataURL(alpha ? 'image/png' : 'image/jpeg', .88);
    const bytes = refs.reduce((n, ref) => n + ref.data.length, data.length);
    if (bytes > 9_300_000) throw new Error('Reference pictures are too large together. Remove one or use a smaller file.');
    return {id: nextRef++, filename: file.name, data};
  } finally { bitmap.close(); }
}
async function addFiles(files) {
  if (busy || uploading || job) { notice('Finish the current job before changing references.', true); return; }
  if (refs.length + files.length > 10) { notice('Up to ten pictures are supported. Choose fewer files.', true); return; }
  uploading = true; controls(); notice('Preparing reference pictures…');
  const errors = [];
  for (const file of files) {
    try { refs.push(await prepareImage(file)); } catch (e) { errors.push(e.message); }
  }
  uploading = false; renderRefs(); notice(errors.length ? errors.join(' ') : 'Pictures ready. Click a label to mention it in your prompt.', !!errors.length);
}
$('add').addEventListener('click', () => $('files').click());
$('files').addEventListener('change', async () => { await addFiles(Array.from($('files').files)); $('files').value = ''; });
for (const name of ['dragenter', 'dragover']) $('drop').addEventListener(name, event => { event.preventDefault(); $('drop').classList.add('drag'); });
$('drop').addEventListener('dragleave', () => $('drop').classList.remove('drag'));
$('drop').addEventListener('drop', event => { event.preventDefault(); $('drop').classList.remove('drag'); addFiles(Array.from(event.dataTransfer.files)); });
$('showKey').addEventListener('click', () => {
  const reveal = $('key').type === 'password'; $('key').type = reveal ? 'text' : 'password'; $('showKey').textContent = reveal ? 'Hide' : 'Show'; $('showKey').setAttribute('aria-label', reveal ? 'Hide API key' : 'Show API key');
});
$('forget').addEventListener('click', () => { $('key').value = ''; save(); $('saved').textContent = 'Saved API key removed.'; });
for (const button of document.querySelectorAll('[data-size]')) button.addEventListener('click', () => { [$('width').value, $('height').value] = button.dataset.size.split(','); save(); });
function connection(base = null) {
  const key = $('key').value.trim(); if (!key) throw new Error('Enter your RunPod API key.');
  return {base: base || core.endpoint($('endpoint').value), key};
}
async function api(base, path, key, method = 'GET', body) {
  const headers = {Authorization: 'Bearer ' + key}; if (body) headers['Content-Type'] = 'application/json';
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch(base + path, {method, headers, body: body ? JSON.stringify(body) : undefined, signal: controller.signal, redirect: 'error'});
    if (!response.ok) throw new Error('RunPod HTTP ' + response.status + (response.status === 401 || response.status === 403 ? ': check your API key and endpoint access.' : response.status === 404 ? ': endpoint or job not found.' : '. Try checking the job status again.'));
    return await response.json();
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Request timed out.');
    if (e instanceof TypeError) throw new Error('Could not reach RunPod. Check your connection; if your browser blocks local files, use the local server in the README.');
    throw e;
  } finally { clearTimeout(timer); }
}
$('health').addEventListener('click', async () => {
  $('health').disabled = true;
  try { const {base, key} = connection(); const health = await api(base, '/health', key); notice('Connected. Workers: ' + JSON.stringify(health.workers || {}) + '.'); }
  catch (e) { notice(e.message, true); } finally { $('health').disabled = false; }
});
function saveJob(value) { job = value; writeStorage(JOB_STORE, value); controls(); }
function displayOutput(output) {
  if (output && output.error) throw new Error('Worker: ' + String(output.error));
  const image = output && output.images && output.images[0];
  if (!image || image.type !== 'base64' || typeof image.data !== 'string') throw new Error('Job finished without the expected base64 image.');
  const raw = atob(image.data.replace(/^data:image\/png;base64,/, ''));
  const bytes = Uint8Array.from(raw, c => c.charCodeAt(0));
  if (bytes.length < 8 || ![137,80,78,71,13,10,26,10].every((value, i) => bytes[i] === value)) throw new Error('Worker returned invalid PNG data.');
  if (outputURL) URL.revokeObjectURL(outputURL);
  outputURL = URL.createObjectURL(new Blob([bytes], {type: 'image/png'}));
  const img = document.createElement('img'); img.src = outputURL; img.alt = 'Generated image'; $('output').replaceChildren(img);
  const link = document.createElement('a'); link.className = 'download'; link.href = outputURL; link.download = 'qwen21-' + (job ? job.id : Date.now()) + '.png'; link.textContent = 'Download PNG'; $('downloads').replaceChildren(link);
}
async function poll() {
  if (busy || !job) return;
  const current = {...job}, token = ++pollToken;
  busy = true; controls();
  try {
    const {key} = connection(current.base);
    const deadline = Date.now() + 30 * 60 * 1000;
    while (token === pollToken && job) {
      const data = await api(current.base, '/status/' + encodeURIComponent(current.id), key);
      if (token !== pollToken) return;
      const status = data.status;
      $('state').textContent = status || 'Checking';
      if (status === 'COMPLETED') {
        try { displayOutput(data.output); }
        catch (error) { saveJob(null); throw error; }
        notice('Image ready.' + (typeof data.executionTime === 'number' ? ' Generation took ' + (data.executionTime / 1000).toFixed(1) + ' seconds.' : ''));
        saveJob(null); return;
      }
      if (['FAILED', 'CANCELLED', 'TIMED_OUT'].includes(status)) {
        saveJob(null); throw new Error('Job ' + status.toLowerCase().replace('_', ' ') + (data.error ? ': ' + String(data.error) : '.'));
      }
      if (!['IN_QUEUE', 'IN_PROGRESS'].includes(status)) throw new Error('Unexpected job status. Resume the status check or inspect RunPod.');
      notice(status === 'IN_QUEUE' ? 'Queued. Your worker may be loading the models; the first request can take a few minutes.' : 'Generating your image…');
      if (Date.now() >= deadline) throw new Error('Status checks paused after 30 minutes. The job may still be running; resume checking or cancel it.');
      await new Promise(resolve => setTimeout(resolve, 2500));
    }
  } catch (e) { notice(e.message + (job ? ' Your job ID is saved. Resume checking; this will not submit a second job.' : ''), true); }
  finally { if (token === pollToken) { busy = false; controls(); } }
}
async function generate() {
  if (busy || uploading || job) return;
  let body, conn;
  try { body = core.payload(settings(), refs); conn = connection(); } catch (e) { notice(e.message, true); return; }
  save(); busy = true; renderRefs(); $('state').textContent = 'Submitting'; notice('Sending your request…');
  try {
    const accepted = await api(conn.base, '/run', conn.key, 'POST', body);
    if (typeof accepted.id !== 'string' || !accepted.id) throw new Error('RunPod did not return a job ID.');
    saveJob({id: accepted.id, base: conn.base, created: Date.now()}); busy = false; await poll();
  } catch (e) {
    $('state').textContent = 'Check RunPod';
    notice(e.message + ' Submission was not retried. Check the RunPod Requests tab before generating again; the request may have been accepted.', true);
  } finally { busy = false; renderRefs(); }
}
$('generate').addEventListener('click', generate);
$('resume').addEventListener('click', poll);
$('cancel').addEventListener('click', async () => {
  if (!job) return;
  $('cancel').disabled = true;
  try {
    const current = {...job}, {key} = connection(current.base);
    await api(current.base, '/cancel/' + encodeURIComponent(current.id), key, 'POST');
    notice('Cancellation requested. Checking the final job status…');
    if (!busy) await poll();
  } catch (e) { notice('Could not confirm cancellation: ' + e.message + ' You can cancel it in RunPod.', true); }
  finally { controls(); }
});
$('export').addEventListener('click', () => {
  try {
    const body = core.payload(settings(), refs); const url = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a'); link.href = url; link.download = 'qwen21-request.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    notice('Request JSON saved. It contains your prompt and images, with no API key.');
  } catch (e) { notice(e.message, true); }
});
const pending = readStorage(JOB_STORE);
if (pending && typeof pending.id === 'string' && typeof pending.base === 'string') {
  try { core.endpoint(pending.base); job = pending; notice('A previous job is saved. Resume its status check to retrieve the result.'); } catch { writeStorage(JOB_STORE, null); }
}
renderRefs();
