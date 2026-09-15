(() => {
  const STORAGE_KEY = 'characterbench.baseline.v1';
  const CHANGE_THRESHOLD = 1.0;
  let currentResult = null;
  let currentModelLabel = '';
  let pendingModelLabel = '';
  let currentDefinitionHashes = {};
  let pendingDefinitionHashes = {};
  let suppressComparison = false;

  function injectStyles(){
    const style = document.createElement('style');
    style.textContent = `
      .baseline-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:-2px 0 14px;padding:0 4px}
      .baseline-actions .hint{margin:0 0 0 4px}.baseline-clear{display:none}.baseline-clear.visible{display:inline-block}
      .baseline-panel{border-color:#2c4059}.baseline-panel h3{margin:0;font-size:18px}.baseline-panel>p{margin:4px 0 0;color:var(--muted);font-size:12px}
      .baseline-overall{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:17px 0 8px;padding:13px 14px;border:1px solid var(--line);border-radius:12px;background:#0b1523}
      .baseline-overall strong{font-size:13px}.baseline-overall span{font-size:15px;font-weight:800}
      .change-list{display:flex;flex-direction:column;gap:8px;margin-top:15px}.change-row{display:grid;grid-template-columns:1fr auto auto;gap:14px;align-items:center;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:#0b1523}
      .change-row strong,.change-row small{display:block}.change-row strong{font-size:13px}.change-row small{font-size:11px;color:var(--muted);margin-top:2px}.change-scores{font-size:13px;color:#d5dfeb;white-space:nowrap}.change-badge{font-size:11px;font-weight:800;border-radius:999px;padding:5px 8px;white-space:nowrap}
      .change-row.regression{border-color:#503840;background:#140f18}.change-row.regression .change-badge{color:var(--red);background:rgba(239,130,137,.10)}
      .change-row.improvement{border-color:#294536;background:rgba(115,214,160,.04)}.change-row.improvement .change-badge{color:var(--green);background:rgba(115,214,160,.09)}
      .comparison-note{margin-top:13px!important}.baseline-empty{margin-top:15px;padding:13px 14px;border:1px solid var(--line);border-radius:12px;background:#0b1523;color:#c7d3df;font-size:13px}
      @media(max-width:700px){.change-row{grid-template-columns:1fr auto}.change-badge{grid-column:1/-1;justify-self:start}.baseline-actions{align-items:flex-start}.baseline-actions .hint{width:100%;margin-left:0}}
    `;
    document.head.appendChild(style);
  }

  function ensureUi(){
    if(document.getElementById('baseline-actions')) return;
    const summary = document.querySelector('.result-summary');
    if(!summary) return;
    const actions = document.createElement('div');
    actions.id = 'baseline-actions';
    actions.className = 'baseline-actions';
    actions.innerHTML = `
      <button id="save-baseline" type="button" class="secondary-button">Save as baseline</button>
      <button id="clear-baseline" type="button" class="text-button baseline-clear">Clear baseline</button>
      <span id="baseline-status" class="hint">Save this run, change something, then run again.</span>`;
    const panel = document.createElement('section');
    panel.id = 'baseline-comparison';
    panel.className = 'panel baseline-panel hidden';
    summary.after(actions);
    actions.after(panel);
    document.getElementById('save-baseline').addEventListener('click', saveBaseline);
    document.getElementById('clear-baseline').addEventListener('click', clearBaseline);
  }

  function modelLabel(){
    if(typeof provider === 'function' && provider() === 'fixture') return 'Instant demo';
    const model = document.getElementById('model');
    return model?.value || 'Local model';
  }

  function testKey(test){
    return `${String(test?.test_id || '')}\n${String(test?.description || '')}`;
  }

  function hashText(text){
    let hash = 2166136261;
    for(let index = 0; index < text.length; index += 1){
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16).padStart(8, '0');
  }

  function captureDefinitionHashes(){
    const hashes = {};
    try{
      if(typeof state === 'undefined' || !state.imported || typeof selectedImportedTests !== 'function') return hashes;
      for(const test of selectedImportedTests()){
        const key = testKey({test_id:test.id, description:test.description});
        hashes[key] = hashText(JSON.stringify(test));
      }
    }catch{
      return {};
    }
    return hashes;
  }

  function compactResult(data, label=currentModelLabel || modelLabel(), definitionHashes=currentDefinitionHashes){
    return {
      version: 2,
      character: String(data?.character || 'Character'),
      overall: Number(data?.overall),
      model: label || 'Model',
      saved_at: new Date().toISOString(),
      tests: (data?.tests || []).map(test => {
        const key = testKey(test);
        return {
          key,
          test_id: String(test?.test_id || ''),
          category: String(test?.category || 'Check'),
          description: String(test?.description || ''),
          score: Number(test?.score),
          definition_hash: definitionHashes[key] || ''
        };
      })
    };
  }

  function loadBaseline(){
    try{
      const raw = localStorage.getItem(STORAGE_KEY);
      if(!raw) return null;
      const parsed = JSON.parse(raw);
      if(!parsed || !Array.isArray(parsed.tests)) return null;
      return parsed;
    }catch{
      return null;
    }
  }

  function saveBaseline(){
    if(!currentResult) return;
    const baseline = compactResult(currentResult, currentModelLabel, currentDefinitionHashes);
    try{
      localStorage.setItem(STORAGE_KEY, JSON.stringify(baseline));
      suppressComparison = true;
      renderBaselineControls(currentResult);
      renderComparison(currentResult);
    }catch{
      document.getElementById('baseline-status').textContent = 'This browser could not save a local baseline.';
    }
  }

  function clearBaseline(){
    try{ localStorage.removeItem(STORAGE_KEY); }catch{}
    suppressComparison = false;
    renderBaselineControls(currentResult);
    const panel = document.getElementById('baseline-comparison');
    if(panel) panel.classList.add('hidden');
  }

  function renderBaselineControls(data){
    ensureUi();
    const baseline = loadBaseline();
    const save = document.getElementById('save-baseline');
    const clear = document.getElementById('clear-baseline');
    const status = document.getElementById('baseline-status');
    if(!save || !clear || !status) return;
    if(!baseline){
      save.textContent = 'Save as baseline';
      clear.classList.remove('visible');
      status.textContent = 'A baseline will be saved locally as scores only — no prompts or model responses.';
      return;
    }
    save.textContent = baseline.character === String(data?.character || '') ? 'Replace baseline' : 'Save as new baseline';
    clear.classList.add('visible');
    const date = baseline.saved_at ? new Date(baseline.saved_at).toLocaleString([], {dateStyle:'medium', timeStyle:'short'}) : 'earlier';
    status.textContent = `Baseline: ${baseline.character} · ${baseline.model || 'model'} · ${date}`;
  }

  function compareResults(baseline, current){
    const oldMap = new Map((baseline.tests || []).map(test => [test.key || testKey(test), test]));
    const currentKeys = new Set();
    const matched = [];
    let newCount = 0;
    let definitionChangedCount = 0;
    for(const test of current.tests || []){
      const key = test.key || testKey(test);
      currentKeys.add(key);
      const old = oldMap.get(key);
      if(!old){ newCount += 1; continue; }
      if(old.definition_hash && test.definition_hash && old.definition_hash !== test.definition_hash){
        definitionChangedCount += 1;
        continue;
      }
      const delta = Number(test.score) - Number(old.score);
      matched.push({old, current:test, delta});
    }
    const missingCount = (baseline.tests || []).filter(test => !currentKeys.has(test.key || testKey(test))).length;
    const sameSet = newCount === 0 && missingCount === 0 && definitionChangedCount === 0 && matched.length === (baseline.tests || []).length;
    return {matched, newCount, missingCount, definitionChangedCount, sameSet};
  }

  function renderComparison(data){
    ensureUi();
    const panel = document.getElementById('baseline-comparison');
    const baseline = loadBaseline();
    if(!panel || !baseline || !data){ if(panel) panel.classList.add('hidden'); return; }
    panel.classList.remove('hidden');
    if(suppressComparison){
      panel.innerHTML = `<h3>Baseline saved</h3><div class="baseline-empty">Change the model, prompt, memory system, card or selected checks, then run CharacterBench again.</div>`;
      return;
    }
    if(baseline.character !== String(data.character || '')){
      panel.innerHTML = `<h3>Baseline belongs to another character</h3><div class="baseline-empty">The saved baseline is for <strong>${escapeHtml(baseline.character)}</strong>. Save this run as a new baseline if you want to compare this character instead.</div>`;
      return;
    }
    const current = compactResult(data, currentModelLabel, currentDefinitionHashes);
    const comparison = compareResults(baseline, current);
    const meaningful = comparison.matched.filter(item => Math.abs(item.delta) >= CHANGE_THRESHOLD)
      .sort((a,b) => a.delta - b.delta);
    const regressions = meaningful.filter(item => item.delta < 0).length;
    const improvements = meaningful.filter(item => item.delta > 0).length;
    let html = `<h3>Compared with baseline</h3><p>${escapeHtml(baseline.model || 'Baseline')} → ${escapeHtml(current.model || 'Current run')} · ${regressions} regression${regressions === 1 ? '' : 's'}, ${improvements} improvement${improvements === 1 ? '' : 's'}</p>`;
    if(comparison.sameSet){
      const delta = Number(current.overall) - Number(baseline.overall);
      const sign = delta > 0 ? '+' : '';
      html += `<div class="baseline-overall"><strong>Overall score</strong><span>${Number(baseline.overall).toFixed(1)} → ${Number(current.overall).toFixed(1)} <em class="${delta < 0 ? 'score-bad' : delta > 0 ? 'score-good' : ''}" style="font-style:normal">(${sign}${delta.toFixed(1)})</em></span></div>`;
    }else{
      html += `<div class="baseline-empty">The test set changed, so the overall scores are not compared. Matching unchanged checks are still compared below.</div>`;
    }
    if(meaningful.length){
      html += `<div class="change-list">${meaningful.map(item => {
        const direction = item.delta < 0 ? 'regression' : 'improvement';
        const arrow = item.delta < 0 ? '↓' : '↑';
        return `<div class="change-row ${direction}"><div><strong>${escapeHtml(item.current.category)}</strong><small>${escapeHtml(item.current.description)}</small></div><span class="change-scores">${Number(item.old.score).toFixed(1)} → ${Number(item.current.score).toFixed(1)}</span><span class="change-badge">${arrow} ${Math.abs(item.delta).toFixed(1)} ${direction}</span></div>`;
      }).join('')}</div>`;
    }else{
      html += `<div class="baseline-empty">No matching unchanged check changed by ${CHANGE_THRESHOLD.toFixed(1)} point or more.</div>`;
    }
    const notes = [];
    if(comparison.definitionChangedCount) notes.push(`${comparison.definitionChangedCount} check definition${comparison.definitionChangedCount === 1 ? '' : 's'} changed and ${comparison.definitionChangedCount === 1 ? 'was' : 'were'} not compared`);
    if(comparison.newCount) notes.push(`${comparison.newCount} new check${comparison.newCount === 1 ? '' : 's'} not in the baseline`);
    if(comparison.missingCount) notes.push(`${comparison.missingCount} baseline check${comparison.missingCount === 1 ? '' : 's'} not rerun`);
    if(notes.length) html += `<p class="comparison-note">${escapeHtml(notes.join(' · '))}</p>`;
    panel.innerHTML = html;
  }

  injectStyles();
  ensureUi();
  document.getElementById('run')?.addEventListener('click', () => {
    pendingModelLabel = modelLabel();
    pendingDefinitionHashes = captureDefinitionHashes();
  });
  const originalRenderResult = renderResult;
  renderResult = function(data){
    suppressComparison = false;
    currentResult = data;
    currentModelLabel = pendingModelLabel || modelLabel();
    currentDefinitionHashes = pendingDefinitionHashes;
    pendingModelLabel = '';
    pendingDefinitionHashes = {};
    originalRenderResult(data);
    renderBaselineControls(data);
    renderComparison(data);
  };
})();
