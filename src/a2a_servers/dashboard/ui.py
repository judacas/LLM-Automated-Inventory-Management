"""Serve the developer dashboard HTML page."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route

# ---------------------------------------------------------------------------
# Embedded dashboard HTML — no build step, no external dependencies.
# ---------------------------------------------------------------------------

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A2A Agent Dashboard</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #f5f5f5; color: #222; }
  header {
    background: #1a1a2e; color: #eee; padding: 12px 24px;
    display: flex; align-items: center; gap: 16px;
  }
  header h1 { font-size: 1.2rem; flex: 1; }
  .btn {
    padding: 6px 14px; border: none; border-radius: 4px;
    cursor: pointer; font-size: 0.85rem;
  }
  .btn-primary { background: #4a90e2; color: #fff; }
  .btn-primary:hover { background: #357abd; }
  .btn-danger  { background: #e74c3c; color: #fff; }
  .btn-danger:hover  { background: #c0392b; }
  .btn-secondary { background: #aaa; color: #fff; }
  .btn-secondary:hover { background: #888; }
  .btn-success { background: #27ae60; color: #fff; }
  .btn-success:hover { background: #1e8449; }
  .layout { display: flex; height: calc(100vh - 50px); }
  .sidebar {
    width: 280px; min-width: 220px; background: #fff;
    border-right: 1px solid #ddd; overflow-y: auto; padding: 12px;
  }
  .sidebar h2 { font-size: 0.9rem; color: #555; margin-bottom: 8px; text-transform: uppercase; letter-spacing: .05em; }
  .agent-item {
    padding: 8px 10px; border-radius: 4px; cursor: pointer;
    margin-bottom: 4px; border: 1px solid transparent;
  }
  .agent-item:hover { background: #f0f4ff; border-color: #ccd; }
  .agent-item.active { background: #e8efff; border-color: #4a90e2; }
  .agent-item .slug { font-weight: 600; font-size: 0.9rem; }
  .agent-item .name { font-size: 0.78rem; color: #666; }
  .main { flex: 1; overflow-y: auto; padding: 20px; }
  .card {
    background: #fff; border-radius: 6px; padding: 20px;
    border: 1px solid #ddd; margin-bottom: 16px;
  }
  .card h2 { font-size: 1rem; margin-bottom: 16px; color: #333; border-bottom: 1px solid #eee; padding-bottom: 8px; }
  label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 4px; margin-top: 12px; }
  input[type=text], textarea, select {
    width: 100%; padding: 7px 10px; border: 1px solid #ccc;
    border-radius: 4px; font-size: 0.9rem; font-family: inherit;
  }
  input[type=text]:focus, textarea:focus { outline: none; border-color: #4a90e2; }
  textarea { resize: vertical; }
  .checkbox-row { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
  .checkbox-row input { width: auto; }
  .hint { font-size: 0.75rem; color: #888; margin-top: 3px; }
  .row-btns { display: flex; gap: 8px; margin-top: 16px; }
  #status-bar {
    padding: 8px 16px; border-radius: 4px; margin-bottom: 12px;
    font-size: 0.85rem; display: none;
  }
  .status-ok  { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; display: block !important; }
  .status-err { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; display: block !important; }
  .status-info { background: #cce5ff; color: #004085; border: 1px solid #b8daff; display: block !important; }
  .skills-hint { font-size: 0.8rem; color: #666; margin-top: 4px; }
  .empty-state { color: #888; font-style: italic; font-size: 0.9rem; padding: 12px 0; }
  .tag-list { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
  .tag { background: #e8efff; color: #4a90e2; padding: 2px 7px; border-radius: 10px; font-size: 0.75rem; }
  fieldset { border: 1px solid #ddd; border-radius: 4px; padding: 10px; margin-top: 12px; }
  legend { font-size: 0.8rem; font-weight: 600; color: #555; padding: 0 6px; }
</style>
</head>
<body>

<header>
  <h1>🤖 A2A Agent Dashboard</h1>
  <button class="btn btn-success" onclick="reloadAgents()">⟳ Reload Agents</button>
  <button class="btn btn-primary" onclick="showNewForm()">+ New Agent</button>
</header>

<div id="status-bar"></div>

<div class="layout">
  <!-- Sidebar: agent list -->
  <div class="sidebar">
    <h2>Agents</h2>
    <div id="agent-list"><p class="empty-state">Loading…</p></div>
  </div>

  <!-- Main: view / add / edit panel -->
  <div class="main" id="main-panel">
    <div class="card">
      <h2>Welcome</h2>
      <p>Select an agent from the sidebar to view or edit it, or click <strong>+ New Agent</strong> to add one.</p>
    </div>
  </div>
</div>

<script>
/* -------------------------------------------------------------------------
   State
   ---------------------------------------------------------------------- */
let agents = [];        // current agent list from API
let editingSlug = null; // null = new agent, string = editing existing

/* -------------------------------------------------------------------------
   Bootstrap
   ---------------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', loadAgents);

/* -------------------------------------------------------------------------
   API helpers
   ---------------------------------------------------------------------- */
const API = '/dashboard/api';

async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  const data = await res.json();
  return { ok: res.ok, status: res.status, data };
}

/* -------------------------------------------------------------------------
   Status bar
   ---------------------------------------------------------------------- */
function showStatus(msg, type = 'ok') {
  const bar = document.getElementById('status-bar');
  bar.textContent = msg;
  bar.className = `status-${type}`;
}
function clearStatus() {
  const bar = document.getElementById('status-bar');
  bar.className = '';
  bar.style.display = 'none';
}

/* -------------------------------------------------------------------------
   Load / display agents
   ---------------------------------------------------------------------- */
async function loadAgents() {
  const { ok, data } = await apiFetch('/agents');
  if (!ok) { showStatus('Failed to load agents: ' + (data.error || '?'), 'err'); return; }
  agents = data;
  renderSidebar();
}

function renderSidebar() {
  const el = document.getElementById('agent-list');
  if (!agents.length) {
    el.innerHTML = '<p class="empty-state">No agents configured.</p>';
    return;
  }
  el.innerHTML = agents.map(a => `
    <div class="agent-item ${editingSlug === a.slug ? 'active' : ''}"
         onclick="selectAgent('${a.slug}')">
      <div class="slug">${esc(a.slug)}</div>
      <div class="name">${esc(a.public_name)}</div>
    </div>
  `).join('');
}

/* -------------------------------------------------------------------------
   View / edit an existing agent
   ---------------------------------------------------------------------- */
async function selectAgent(slug) {
  const { ok, data } = await apiFetch(`/agents/${slug}`);
  if (!ok) { showStatus('Error loading agent: ' + (data.error || '?'), 'err'); return; }
  editingSlug = slug;
  renderSidebar();
  renderEditForm(data);
}

function renderEditForm(agent) {
  const c = agent.config;
  const skillsJson = JSON.stringify(c.skills, null, 2);
  const prompts = (c.smoke_tests?.prompts || []).join('\n');

  document.getElementById('main-panel').innerHTML = `
    <div class="card">
      <h2>Edit Agent — <code>${esc(agent.slug)}</code></h2>
      <p class="hint">File: ${esc(agent.source_path)}</p>
      ${agentForm(c, { slug: agent.slug, filename: agent.filename, isNew: false, skillsJson, prompts })}
      <div class="row-btns">
        <button class="btn btn-primary" onclick="saveAgent()">💾 Save</button>
        <button class="btn btn-danger"  onclick="deleteAgent('${esc(agent.slug)}')">🗑 Delete</button>
        <button class="btn btn-secondary" onclick="cancelForm()">Cancel</button>
      </div>
    </div>
  `;
}

/* -------------------------------------------------------------------------
   New agent form
   ---------------------------------------------------------------------- */
function showNewForm() {
  editingSlug = null;
  renderSidebar();
  const defaultSkills = JSON.stringify([{
    id: "primary_capability",
    name: "Primary Capability",
    description: "Describe the main thing this agent can do.",
    tags: ["replace", "these"],
    examples: ["Example request 1"]
  }], null, 2);

  document.getElementById('main-panel').innerHTML = `
    <div class="card">
      <h2>New Agent</h2>
      ${agentForm({}, { isNew: true, skillsJson: defaultSkills, prompts: '' })}
      <div class="row-btns">
        <button class="btn btn-primary" onclick="saveAgent()">💾 Create Agent</button>
        <button class="btn btn-secondary" onclick="cancelForm()">Cancel</button>
      </div>
    </div>
  `;
}

function cancelForm() {
  editingSlug = null;
  renderSidebar();
  document.getElementById('main-panel').innerHTML = `
    <div class="card"><h2>Welcome</h2>
    <p>Select an agent from the sidebar, or click <strong>+ New Agent</strong>.</p></div>`;
}

/* -------------------------------------------------------------------------
   Shared form template
   ---------------------------------------------------------------------- */
function agentForm(c, { slug = '', filename = '', isNew = false, skillsJson = '[]', prompts = '' } = {}) {
  const a = c.a2a || {};
  const f = c.foundry || {};
  return `
    ${isNew ? `
      <label for="f-filename">Filename <span style="color:red">*</span></label>
      <input id="f-filename" type="text" value="${esc(filename)}"
        placeholder="my_agent.toml (must end with _agent.toml to be auto-discovered)">
    ` : `
      <input type="hidden" id="f-filename" value="${esc(filename)}">
      <input type="hidden" id="f-slug" value="${esc(slug)}">
    `}

    <fieldset><legend>A2A settings</legend>
      <label for="f-name">Name <span style="color:red">*</span></label>
      <input id="f-name" type="text" value="${esc(a.name||'')}" placeholder="My Agent">

      <label for="f-description">Description <span style="color:red">*</span></label>
      <textarea id="f-description" rows="2">${esc(a.description||'')}</textarea>

      <label for="f-version">Version <span style="color:red">*</span></label>
      <input id="f-version" type="text" value="${esc(a.version||'1.0.0')}">

      <label for="f-health_message">Health message <span style="color:red">*</span></label>
      <input id="f-health_message" type="text" value="${esc(a.health_message||'')}">

      <label for="f-slug-override">Slug override <span style="color:#888">(optional)</span></label>
      <input id="f-slug-override" type="text" value="${esc(a.slug||'')}"
        placeholder="Derived from filename if left blank">

      <label for="f-input_modes">Default input modes</label>
      <input id="f-input_modes" type="text"
        value="${esc((a.default_input_modes||['text']).join(', '))}"
        placeholder="text">
      <p class="hint">Comma-separated, e.g. <code>text, file</code></p>

      <label for="f-output_modes">Default output modes</label>
      <input id="f-output_modes" type="text"
        value="${esc((a.default_output_modes||['text']).join(', '))}"
        placeholder="text">

      <div class="checkbox-row">
        <input type="checkbox" id="f-streaming" ${a.streaming !== false ? 'checked' : ''}>
        <label for="f-streaming" style="margin:0">Streaming</label>
      </div>
    </fieldset>

    <fieldset><legend>Foundry settings</legend>
      <label for="f-foundry_agent">Foundry agent name <span style="color:red">*</span></label>
      <input id="f-foundry_agent" type="text" value="${esc(f.agent_name||'')}"
        placeholder="My-Foundry-Agent-Name">
    </fieldset>

    <fieldset><legend>Skills (JSON)</legend>
      <p class="skills-hint">Edit the list of skill objects.
        Each skill needs <code>id</code>, <code>name</code>, <code>description</code>,
        <code>tags</code> (array), and <code>examples</code> (array).</p>
      <textarea id="f-skills" rows="10" style="font-family:monospace;font-size:0.82rem">${esc(skillsJson)}</textarea>
    </fieldset>

    <fieldset><legend>Smoke test prompts <span style="color:#888">(optional)</span></legend>
      <p class="hint">One prompt per line.</p>
      <textarea id="f-prompts" rows="4">${esc(prompts)}</textarea>
    </fieldset>
  `;
}

/* -------------------------------------------------------------------------
   Collect form data and POST / PUT
   ---------------------------------------------------------------------- */
async function saveAgent() {
  clearStatus();

  const filename = document.getElementById('f-filename')?.value.trim() || '';
  const name     = document.getElementById('f-name')?.value.trim() || '';
  const desc     = document.getElementById('f-description')?.value.trim() || '';
  const version  = document.getElementById('f-version')?.value.trim() || '';
  const health   = document.getElementById('f-health_message')?.value.trim() || '';
  const slugOvr  = document.getElementById('f-slug-override')?.value.trim() || '';
  const inModes  = (document.getElementById('f-input_modes')?.value || 'text')
                    .split(',').map(s => s.trim()).filter(Boolean);
  const outModes = (document.getElementById('f-output_modes')?.value || 'text')
                    .split(',').map(s => s.trim()).filter(Boolean);
  const streaming = document.getElementById('f-streaming')?.checked ?? true;
  const foundryName = document.getElementById('f-foundry_agent')?.value.trim() || '';
  const skillsRaw   = document.getElementById('f-skills')?.value || '[]';
  const promptsRaw  = document.getElementById('f-prompts')?.value || '';

  // Parse skills
  let skills;
  try { skills = JSON.parse(skillsRaw); }
  catch (e) { showStatus('Skills JSON is invalid: ' + e.message, 'err'); return; }

  const prompts = promptsRaw.split('\n').map(s => s.trim()).filter(Boolean);

  const a2a = { name, description: desc, version, health_message: health,
                default_input_modes: inModes, default_output_modes: outModes,
                streaming };
  if (slugOvr) a2a.slug = slugOvr;

  const payload = {
    filename,
    config: {
      a2a,
      foundry: { agent_name: foundryName },
      smoke_tests: { prompts },
      skills,
    },
  };

  let result;
  if (editingSlug === null) {
    // Create
    result = await apiFetch('/agents', { method: 'POST', body: JSON.stringify(payload) });
  } else {
    // Update
    result = await apiFetch(`/agents/${editingSlug}`, { method: 'PUT', body: JSON.stringify(payload) });
  }

  if (!result.ok) {
    showStatus('Error: ' + (result.data.error || JSON.stringify(result.data)), 'err');
    return;
  }

  const saved = result.data;
  showStatus(`✓ Agent '${saved.slug}' saved successfully.`, 'ok');
  await loadAgents();
  editingSlug = saved.slug;
  renderSidebar();
  renderEditForm(saved);
}

/* -------------------------------------------------------------------------
   Delete
   ---------------------------------------------------------------------- */
async function deleteAgent(slug) {
  if (!confirm(`Delete agent '${slug}'? This removes the TOML file.`)) return;
  clearStatus();
  const { ok, data } = await apiFetch(`/agents/${slug}`, { method: 'DELETE' });
  if (!ok) { showStatus('Delete failed: ' + (data.error || '?'), 'err'); return; }
  showStatus(`Agent '${slug}' deleted.`, 'ok');
  editingSlug = null;
  await loadAgents();
  cancelForm();
}

/* -------------------------------------------------------------------------
   Reload
   ---------------------------------------------------------------------- */
async function reloadAgents() {
  clearStatus();
  showStatus('Reloading agents…', 'info');
  const { ok, data } = await apiFetch('/reload', { method: 'POST' });
  if (!ok) {
    showStatus('Reload error: ' + (data.error || JSON.stringify(data)), 'err');
    return;
  }
  const msg = data.reloaded
    ? `✓ Reloaded ${data.agents.length} agent(s).`
    : `⚠ TOML validated (${data.agents.length} agent(s)) but live routing NOT updated: ${data.reason}`;
  showStatus(msg, data.reloaded ? 'ok' : 'info');
  await loadAgents();
}

/* -------------------------------------------------------------------------
   Utility
   ---------------------------------------------------------------------- */
function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
</script>
</body>
</html>
"""


async def _serve_dashboard(_: Request) -> HTMLResponse:
    return HTMLResponse(_HTML)


def create_ui_routes() -> list[Route]:
    """Return Starlette routes that serve the dashboard UI."""
    return [
        Route("/", endpoint=_serve_dashboard, methods=["GET"]),
    ]
