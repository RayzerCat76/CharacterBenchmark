const $ = (id) => document.getElementById(id);
const state = { suites: [], models: [], source: 'bundled', running: false, imported: null };

function escapeHtml(value){
  return String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;')
    .replaceAll('>','&gt;').replaceAll('"','&quot;');
}
function scoreClass(score){
  if(Number(score) >= 8) return 'score-good';
  if(Number(score) >= 5) return 'score-mid';
  return 'score-bad';
}
function provider(){
  return document.querySelector('input[name="provider"]:checked')?.value || 'fixture';
}
function setProvider(value){
  const input = document.querySelector(`input[name="provider"][value="${value}"]`);
  if(input){ input.checked = true; }
  updateProviderCards();
}
function refreshRunState(){
  const advancedReady = Boolean($('character-file').files?.[0] && $('tests-file').files?.[0]);
  const missingCharacter = state.source === 'custom' && !state.imported && !advancedReady;
  const missingModel = provider() === 'ollama-native' && !state.models.length;
  $('run').disabled = state.running || missingCharacter || missingModel;
  $('run').textContent = state.source === 'custom' ? 'Test my character' : (provider() === 'fixture' ? 'Run demo' : 'Test demo character');
  if(missingCharacter) $('environment').textContent = 'Drop a character card to continue.';
  else if(missingModel) $('environment').textContent = 'Ollama is not running or no local models were found.';
  else if(provider() === 'ollama-native') $('environment').textContent = `${state.models.length} local model${state.models.length === 1 ? '' : 's'} ready.`;
  else $('environment').textContent = 'Instant demo uses saved responses, so it runs immediately.';
}
function updateProviderCards(){
  document.querySelectorAll('.radio-card').forEach(card => {
    const input = card.querySelector('input');
    card.classList.toggle('selected', Boolean(input?.checked));
  });
  const ollama = provider() === 'ollama-native';
  $('model-field').classList.toggle('hidden', !ollama);
  if(ollama && !state.models.length){
    $('environment').textContent = 'Ollama is not running or no local models were found.';
  }else if(ollama){
    $('environment').textContent = `${state.models.length} local model${state.models.length === 1 ? '' : 's'} ready.`;
  }else{
    $('environment').textContent = 'Instant demo uses saved responses, so it runs immediately.';
  }
  refreshRunState();
}
function chooseSource(source){
  state.source = source;
  document.querySelectorAll('[data-source]').forEach(button => {
    button.classList.toggle('selected', button.dataset.source === source);
  });
  const custom = source === 'custom';
  $('bundled-fields').classList.toggle('hidden', custom);
  $('custom-fields').classList.toggle('hidden', !custom);
  $('instant-option').classList.toggle('disabled', custom);
  $('instant-option').querySelector('input').disabled = custom;
  if(custom) setProvider('ollama-native');
  else setProvider('fixture');
  updateProviderCards();
}
function updateSuiteDescription(){
  const suite = state.suites.find(x => x.id === $('suite').value);
  $('suite-description').textContent = suite ? suite.description : '';
}
async function readJsonFile(input, label){
  const file = input.files?.[0];
  if(!file) throw new Error(`Choose your ${label} JSON file.`);
  try{return JSON.parse(await file.text());}
  catch{throw new Error(`${label} is not valid JSON.`);}
}
function updateFileCard(input){
  const card = input.closest('.file-card');
  const small = card.querySelector('small');
  const file = input.files?.[0];
  card.classList.toggle('ready', Boolean(file));
  small.textContent = file ? file.name : (input.id === 'character-file' ? 'character.json' : 'tests.json');
  if(file){ clearImportedCard(false); }
  refreshRunState();
}

function clearImportedCard(resetInput=true){
  state.imported = null;
  $('card-preview').classList.add('hidden');
  $('card-drop').classList.remove('ready','dragging');
  if(resetInput) $('card-file').value = '';
  $('card-status').classList.remove('inline-error');
  $('card-status').textContent = 'The card stays on this computer. CharacterBench creates a starter regression suite from its existing fields.';
  refreshRunState();
}

function fileAsBase64(file){
  return new Promise((resolve,reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',',2)[1] || '');
    reader.onerror = () => reject(new Error('Could not read that character card.'));
    reader.readAsDataURL(file);
  });
}

function signalLabels(signals){
  const labels = [];
  if(signals?.description) labels.push('description');
  if(signals?.personality) labels.push('personality');
  if(signals?.scenario) labels.push('scenario');
  if(signals?.example_dialogue) labels.push('example dialogue');
  if(signals?.system_prompt) labels.push('system prompt');
  if(Number(signals?.lore_entries) > 0) labels.push(`${signals.lore_entries} lore ${Number(signals.lore_entries) === 1 ? 'entry' : 'entries'}`);
  return labels;
}

async function importCharacterCard(file){
  if(!file) return;
  clearImportedCard(false);
  $('card-drop').classList.add('loading-card');
  $('card-status').textContent = 'Reading character card…';
  try{
    const response = await fetch('/api/import-card',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({filename:file.name,data_base64:await fileAsBase64(file)})
    });
    const data = await response.json();
    if(!response.ok) throw new Error(data.error || 'CharacterBench could not read that card.');
    state.imported = data;
    $('card-name').textContent = data.preview?.name || 'Character ready';
    $('card-meta').textContent = `${data.preview?.test_count || 0} starter checks ready · ${data.format || 'character card'}`;
    const labels = signalLabels(data.preview?.signals);
    $('card-signals').textContent = labels.length ? `Found: ${labels.join(', ')}.` : 'Basic identity found.';
    $('card-preview').classList.remove('hidden');
    $('card-drop').classList.add('ready');
    $('card-status').textContent = data.preview?.warnings?.length ? data.preview.warnings.join(' ') : 'Starter tests use only information already present in the card.';
    $('character-file').value = ''; $('tests-file').value = '';
    document.querySelectorAll('.file-card').forEach(card => card.classList.remove('ready'));
  }catch(err){
    $('card-file').value = '';
    $('card-status').textContent = err.message || String(err);
    $('card-status').classList.add('inline-error');
  }finally{
    $('card-drop').classList.remove('loading-card');
    if(state.imported) $('card-status').classList.remove('inline-error');
    refreshRunState();
  }
}
async function loadState(){
  const response = await fetch('/api/state',{cache:'no-store'});
  if(!response.ok) throw new Error('Could not start CharacterBench locally.');
  const data = await response.json();
  state.suites = data.suites || [];
  state.models = data.models || [];
  $('version').textContent = `CharacterBench ${data.version}`;
  $('suite').innerHTML = state.suites.map(s => `<option value="${escapeHtml(s.id)}">${escapeHtml(s.name)}</option>`).join('');
  $('model').innerHTML = state.models.length
    ? state.models.map(m => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join('')
    : '<option value="">No local models found</option>';
  updateSuiteDescription();
  chooseSource('bundled');
  updateProviderCards();
}
function setLoading(on){
  state.running = on;
  $('run').disabled = on;
  $('loading').classList.toggle('hidden',!on);
  if(on){$('results').classList.add('hidden');$('error').classList.add('hidden');}
  else refreshRunState();
}
function renderCategories(categories){
  $('categories').innerHTML = Object.entries(categories || {}).map(([name,score]) => {
    const pct = Math.max(0,Math.min(100,Number(score)*10));
    return `<div class="category"><span class="category-name">${escapeHtml(name)}</span><div class="bar"><i style="width:${pct}%"></i></div><span class="category-score ${scoreClass(score)}">${Number(score).toFixed(1)}</span></div>`;
  }).join('');
}
function renderWeakSpots(tests){
  const weak = (tests || []).filter(t => Number(t.score) < 8).sort((a,b) => Number(a.score)-Number(b.score));
  $('issue-count').textContent = weak.length;
  if(!weak.length){
    $('weak-spots').innerHTML = `<div class="weak-card good"><strong>${state.imported ? 'No issues found in these starter checks.' : 'No obvious problems found.'}</strong><span>${state.imported ? 'Auto-generated checks are a starting point, not a complete character-quality judgment.' : 'Nothing in this suite scored below 8/10.'}</span></div>`;
    return weak;
  }
  const card = t => `<div class="weak-card"><strong>${escapeHtml(t.category)}<em>${Number(t.score).toFixed(1)}/10</em></strong><span>${escapeHtml(t.description)}</span></div>`;
  const top = weak.slice(0,3).map(card).join('');
  const rest = weak.slice(3);
  const more = rest.length ? `<details class="more-issues"><summary>Show ${rest.length} more ${rest.length === 1 ? 'issue' : 'issues'}</summary><div class="more-issues-list">${rest.map(card).join('')}</div></details>` : '';
  $('weak-spots').innerHTML = top + more;
  return weak;
}
function renderTests(tests){
  $('tests').innerHTML = (tests || []).map(t => {
    const reasons = (t.reasons || []).map(r => `<div class="reason">${escapeHtml(r)}</div>`).join('');
    return `<details class="test"><summary><span class="badge">${escapeHtml(t.category)}</span><span>${escapeHtml(t.description)}</span><span class="test-score ${scoreClass(t.score)}">${Number(t.score).toFixed(1)}</span></summary><div class="test-body"><p><strong>Test ID:</strong> ${escapeHtml(t.test_id)}</p><p><strong>Model response:</strong><br>${escapeHtml(t.response || '')}</p>${reasons}</div></details>`;
  }).join('');
}
function renderResult(data){
  $('result-title').textContent = `${data.character} test complete`;
  $('provider-label').textContent = data.provider || '';
  $('overall').textContent = Number(data.overall).toFixed(1);
  $('overall').className = scoreClass(data.overall);
  const weak = renderWeakSpots(data.tests);
  $('result-message').textContent = weak.length
    ? `${weak.length} ${weak.length === 1 ? 'area needs' : 'areas need'} a closer look.`
    : (state.imported ? 'This starter suite found no obvious regression signals.' : 'This run found no obvious regression signals.');
  $('issue-count').classList.toggle('no-issues', weak.length === 0);
  renderCategories(data.categories);
  renderTests(data.tests);
  $('results').classList.remove('hidden');
  $('results').scrollIntoView({behavior:'smooth',block:'start'});
}
async function run(){
  setLoading(true);
  try{
    if(provider() === 'ollama-native' && !state.models.length) throw new Error('Start Ollama and make sure at least one model is installed.');
    const payload = {suite:$('suite').value,provider:provider(),model:$('model').value};
    if(state.source === 'custom'){
      if(state.imported){
        payload.custom_character = state.imported.character;
        payload.custom_tests = state.imported.tests;
      }else{
        payload.custom_character = await readJsonFile($('character-file'),'character profile');
        payload.custom_tests = await readJsonFile($('tests-file'),'test suite');
      }
    }
    const response = await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data = await response.json();
    if(!response.ok) throw new Error(data.error || 'CharacterBench could not complete the run.');
    renderResult(data);
  }catch(err){
    $('error').textContent = err.message || String(err);
    $('error').classList.remove('hidden');
    $('error').scrollIntoView({behavior:'smooth',block:'center'});
  }finally{setLoading(false);}
}

document.querySelectorAll('[data-source]').forEach(button => button.addEventListener('click',() => chooseSource(button.dataset.source)));
document.querySelectorAll('input[name="provider"]').forEach(input => input.addEventListener('change',updateProviderCards));
$('suite').addEventListener('change',updateSuiteDescription);
$('card-file').addEventListener('change',() => importCharacterCard($('card-file').files?.[0]));
$('clear-card').addEventListener('click',() => clearImportedCard(true));
$('card-drop').addEventListener('dragover',event => { event.preventDefault(); $('card-drop').classList.add('dragging'); });
$('card-drop').addEventListener('dragleave',() => $('card-drop').classList.remove('dragging'));
$('card-drop').addEventListener('drop',event => {
  event.preventDefault(); $('card-drop').classList.remove('dragging');
  const file = event.dataTransfer?.files?.[0];
  if(file) importCharacterCard(file);
});
$('character-file').addEventListener('change',() => updateFileCard($('character-file')));
$('tests-file').addEventListener('change',() => updateFileCard($('tests-file')));
$('run').addEventListener('click',run);
$('run-again').addEventListener('click',() => {
  $('results').classList.add('hidden');
  $('error').classList.add('hidden');
  $('setup').scrollIntoView({behavior:'smooth',block:'start'});
});
loadState().catch(err => {
  $('environment').textContent = err.message;
  $('run').disabled = true;
});
