const $ = (id) => document.getElementById(id);
const state = { suites: [], models: [], source: 'bundled', running: false };

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
  const missingFiles = state.source === 'custom' && (!$('character-file').files?.[0] || !$('tests-file').files?.[0]);
  const missingModel = provider() === 'ollama-native' && !state.models.length;
  $('run').disabled = state.running || missingFiles || missingModel;
  $('run').textContent = state.source === 'custom' ? 'Test my character' : (provider() === 'fixture' ? 'Run demo' : 'Test demo character');
  if(missingFiles) $('environment').textContent = 'Choose both JSON files to continue.';
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
  refreshRunState();
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
    $('weak-spots').innerHTML = '<div class="weak-card good"><strong>No obvious problems found.</strong><span>Nothing in this suite scored below 8/10.</span></div>';
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
    : 'This run found no obvious regression signals.';
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
      payload.custom_character = await readJsonFile($('character-file'),'character profile');
      payload.custom_tests = await readJsonFile($('tests-file'),'test suite');
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
