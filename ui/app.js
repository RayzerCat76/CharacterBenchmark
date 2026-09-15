const $ = (id) => document.getElementById(id);
const state = { suites: [], models: [] };

function scoreClass(score){
  if(score >= 8) return 'score-good';
  if(score >= 5) return 'score-mid';
  return 'score-bad';
}

function escapeHtml(value){
  return String(value ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;')
    .replaceAll('>','&gt;').replaceAll('"','&quot;');
}

function setLoading(on){
  $('run').disabled = on;
  $('loading').classList.toggle('hidden', !on);
  if(on){
    $('empty-state').classList.add('hidden');
    $('results').classList.add('hidden');
    $('error').classList.add('hidden');
  }
}

function updateSuiteDescription(){
  const suite = state.suites.find(x => x.id === $('suite').value);
  $('suite-description').textContent = suite ? suite.description : '';
}

function updateSource(){
  const custom = $('source').value === 'custom';
  $('bundled-fields').classList.toggle('hidden', custom);
  $('custom-fields').classList.toggle('hidden', !custom);
  if(custom){
    $('provider').value = 'ollama-native';
    $('provider').querySelector('option[value="fixture"]').disabled = true;
  }else{
    $('provider').querySelector('option[value="fixture"]').disabled = false;
  }
  updateProvider();
}

async function readJsonFile(input, label){
  const file = input.files && input.files[0];
  if(!file) throw new Error(`Choose a ${label} JSON file.`);
  try{ return JSON.parse(await file.text()); }
  catch{ throw new Error(`${label} is not valid JSON.`); }
}

function updateProvider(){
  const ollama = $('provider').value === 'ollama-native';
  $('model-field').classList.toggle('hidden', !ollama);
  if(ollama && !state.models.length){
    $('environment').textContent = 'Ollama is not reachable. Start Ollama or use the offline demo.';
  } else if(ollama){
    $('environment').textContent = `${state.models.length} local Ollama model(s) detected.`;
  } else {
    $('environment').textContent = 'Offline demo: no model provider is contacted.';
  }
}

async function loadState(){
  const response = await fetch('/api/state', {cache:'no-store'});
  if(!response.ok) throw new Error('Could not load local CharacterBench state.');
  const data = await response.json();
  state.suites = data.suites || [];
  state.models = data.models || [];
  $('version').textContent = data.version;
  $('suite').innerHTML = state.suites.map(s => `<option value="${escapeHtml(s.id)}">${escapeHtml(s.name)}</option>`).join('');
  $('model').innerHTML = state.models.length
    ? state.models.map(m => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join('')
    : '<option value="">No local models found</option>';
  updateSuiteDescription();
  updateSource();
}
function renderCategories(categories){
  const entries = Object.entries(categories || {});
  $('categories').innerHTML = entries.map(([name,score]) => {
    const pct = Math.max(0, Math.min(100, Number(score) * 10));
    return `<div class="category"><span class="category-name">${escapeHtml(name)}</span><div class="bar"><i style="width:${pct}%"></i></div><span class="category-score ${scoreClass(score)}">${Number(score).toFixed(1)}</span></div>`;
  }).join('');
}

function renderWeakSpots(tests){
  const weak = (tests || []).filter(t => Number(t.score) < 8);
  $('weak-spots').innerHTML = weak.length ? weak.map(t => `
    <div class="weak-card">
      <strong>${escapeHtml(t.test_id)} · ${Number(t.score).toFixed(1)}/10</strong>
      <span>${escapeHtml(t.category)} — ${escapeHtml(t.description)}</span>
    </div>`).join('') : '<div class="weak-card"><strong class="score-good">No tests below 8/10.</strong><span>This run showed no obvious regression signals in the current suite.</span></div>';
}

function renderTests(tests){
  $('tests').innerHTML = (tests || []).map(t => {
    const reasons = (t.reasons || []).map(r => `<div class="reason">${escapeHtml(r)}</div>`).join('');
    const response = escapeHtml(t.response || '');
    return `<details class="test"><summary><span class="badge">${escapeHtml(t.category)}</span><span>${escapeHtml(t.test_id)}</span><span class="test-score ${scoreClass(t.score)}">${Number(t.score).toFixed(1)}</span></summary><div class="test-body"><p>${escapeHtml(t.description)}</p><p><strong>Final response</strong><br>${response}</p>${reasons}</div></details>`;
  }).join('');
}
function renderResult(data){
  $('result-title').textContent = `${data.character} report`;
  $('provider-label').textContent = data.provider || '';
  $('overall').textContent = Number(data.overall).toFixed(1);
  $('overall').className = scoreClass(data.overall);
  renderCategories(data.categories);
  renderWeakSpots(data.tests);
  renderTests(data.tests);
  $('results').classList.remove('hidden');
}

async function run(){
  setLoading(true);
  try{
    const payload = {
      suite: $('suite').value,
      provider: $('provider').value,
      model: $('model').value
    };
    if($('source').value === 'custom'){
      payload.custom_character = await readJsonFile($('character-file'), 'character');
      payload.custom_tests = await readJsonFile($('tests-file'), 'tests');
    }
    const response = await fetch('/api/run', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    });
    const data = await response.json();
    if(!response.ok) throw new Error(data.error || 'CharacterBench run failed.');
    renderResult(data);
  }catch(err){
    $('error').textContent = err.message || String(err);
    $('error').classList.remove('hidden');
  }finally{
    setLoading(false);
  }
}

$('source').addEventListener('change', updateSource);
$('suite').addEventListener('change', updateSuiteDescription);
$('provider').addEventListener('change', updateProvider);
$('run').addEventListener('click', run);
loadState().catch(err => {
  $('environment').textContent = err.message;
  $('run').disabled = true;
});
