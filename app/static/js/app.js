const API_BASE = '/api/v1';

// App State
let currentFindings = [];
let currentResources = [];
let currentRules = [];

// Initialize on DOM loaded
document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupFileUpload();
  refreshAllData();
});

// Navigation Tabs
function setupNavigation() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));
      
      tab.classList.add('active');
      const targetId = tab.getAttribute('data-target');
      document.getElementById(targetId).classList.add('active');

      if (targetId === 'view-resources') loadResourcesTable();
      if (targetId === 'view-rules') loadRulesTable();
    });
  });
}

// Global Data Refresh
async function refreshAllData() {
  await Promise.all([
    loadSummaryKPIs(),
    loadWasteFindings()
  ]);
}

// 1. Load KPI Summary
async function loadSummaryKPIs() {
  try {
    const res = await fetch(`${API_BASE}/optimizer/summary`);
    const data = await res.json();
    
    document.getElementById('kpi-gross-spend').textContent = `$${data.total_gross_spend.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    document.getElementById('kpi-leakage').textContent = `$${data.potential_monthly_savings.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    document.getElementById('kpi-savings-pct').textContent = `${data.savings_percentage}%`;
    document.getElementById('kpi-findings-count').textContent = data.total_waste_findings;
    document.getElementById('kpi-resources-count').textContent = `${data.total_resources} Resources Tracked`;

    renderCategoryBreakdown(data.breakdown_by_category || {});
    renderProviderBreakdown(data.breakdown_by_provider || {});
  } catch (err) {
    console.error('Failed to load KPIs:', err);
  }
}

function renderCategoryBreakdown(categories) {
  const container = document.getElementById('category-breakdown-list');
  if (!container) return;
  container.innerHTML = '';
  
  const entries = Object.entries(categories);
  if (entries.length === 0) {
    container.innerHTML = '<div style="color:var(--text-muted); padding:1rem 0;">No waste categories detected yet. Run a scan to evaluate.</div>';
    return;
  }

  entries.sort((a, b) => b[1] - a[1]);
  entries.forEach(([cat, amount]) => {
    const item = document.createElement('div');
    item.style.cssText = 'display:flex; justify-content:space-between; align-items:center; padding:0.6rem 0; border-bottom:1px solid rgba(255,255,255,0.05);';
    item.innerHTML = `
      <span style="font-weight:600; font-size:0.85rem;">${cat}</span>
      <span style="font-weight:700; color:#10B981;">+$${amount.toFixed(2)}/mo</span>
    `;
    container.appendChild(item);
  });
}

function renderProviderBreakdown(providers) {
  const container = document.getElementById('provider-breakdown-list');
  if (!container) return;
  container.innerHTML = '';

  const entries = Object.entries(providers);
  if (entries.length === 0) {
    container.innerHTML = '<div style="color:var(--text-muted); padding:1rem 0;">No provider spend ingested yet.</div>';
    return;
  }

  entries.forEach(([prov, spend]) => {
    const item = document.createElement('div');
    item.style.cssText = 'display:flex; justify-content:space-between; align-items:center; padding:0.6rem 0; border-bottom:1px solid rgba(255,255,255,0.05);';
    const badgeClass = prov === 'gcp' ? 'badge-gcp' : prov === 'aws' ? 'badge-aws' : 'badge-azure';
    item.innerHTML = `
      <span class="badge ${badgeClass}">${prov.toUpperCase()}</span>
      <span style="font-weight:700;">$${spend.toFixed(2)}</span>
    `;
    container.appendChild(item);
  });
}

// 2. Load Waste Findings
async function loadWasteFindings() {
  const severity = document.getElementById('filter-severity')?.value || '';
  const category = document.getElementById('filter-category')?.value || '';
  const provider = document.getElementById('filter-provider')?.value || '';

  let url = `${API_BASE}/optimizer/waste-items?status=pending`;
  if (severity) url += `&severity=${encodeURIComponent(severity)}`;
  if (category) url += `&category=${encodeURIComponent(category)}`;
  if (provider) url += `&provider=${encodeURIComponent(provider)}`;

  try {
    const res = await fetch(url);
    const data = await res.json();
    currentFindings = data.findings || [];

    const tbody = document.getElementById('waste-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (currentFindings.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align:center; padding:2.5rem; color:var(--text-muted);">
            <div style="font-size:1.1rem; font-weight:600; margin-bottom:0.4rem;">Zero Waste Leakage Detected</div>
            <div style="font-size:0.8rem;">Click 'Load Sample Billing Data' or upload GCP exports to analyze resources.</div>
          </td>
        </tr>`;
      return;
    }

    currentFindings.forEach((f, index) => {
      const tr = document.createElement('tr');
      const sevClass = f.severity === 'CRITICAL' ? 'badge-critical' : f.severity === 'HIGH' ? 'badge-high' : f.severity === 'MEDIUM' ? 'badge-medium' : 'badge-low';
      const provClass = f.provider === 'gcp' ? 'badge-gcp' : f.provider === 'aws' ? 'badge-aws' : 'badge-azure';

      tr.innerHTML = `
        <td><span class="badge ${sevClass}">${f.severity}</span></td>
        <td><span class="badge ${provClass}">${f.provider.toUpperCase()}</span></td>
        <td>
          <div style="font-weight:600; color:var(--text-primary);">${f.resource_name}</div>
          <div style="font-size:0.72rem; color:var(--text-muted);">${f.project_or_account_id} • ${f.region_or_zone}</div>
        </td>
        <td><span style="font-weight:600;">${f.category}</span></td>
        <td><span style="color:#10B981; font-weight:700; font-size:0.95rem;">+$${f.monthly_savings_estimate.toFixed(2)}</span></td>
        <td style="max-width:240px; font-size:0.8rem; color:var(--text-secondary);">${f.reason}</td>
        <td>
          <div style="display:flex; gap:0.4rem;">
            <button class="btn btn-secondary" style="padding:0.35rem 0.65rem; font-size:0.75rem;" onclick="openInspectModal(${index})">
              🔍 Inspect
            </button>
            <button class="btn btn-primary" style="padding:0.35rem 0.65rem; font-size:0.75rem;" onclick="openRemediateModal(${index})">
              ⚡ Remediate
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load waste findings:', err);
  }
}

// 3. Inspect Modal (Step 1 of 2-Step Gate)
function openInspectModal(index) {
  const finding = currentFindings[index];
  if (!finding) return;

  document.getElementById('inspect-modal-title').textContent = `Inspect Resource: ${finding.resource_name}`;
  document.getElementById('inspect-resource-meta').innerHTML = `
    <strong>Provider:</strong> ${finding.provider.toUpperCase()} | 
    <strong>Project:</strong> ${finding.project_or_account_id} | 
    <strong>Category:</strong> ${finding.category} | 
    <strong>Potential Savings:</strong> $${finding.monthly_savings_estimate.toFixed(2)}/mo
  `;
  document.getElementById('inspect-command-code').textContent = finding.inspect_command;
  document.getElementById('inspect-modal').classList.add('active');
}

function closeInspectModal() {
  document.getElementById('inspect-modal').classList.remove('active');
}

// 4. Remediate Modal (Step 2 of 2-Step Gate)
function openRemediateModal(index) {
  const finding = currentFindings[index];
  if (!finding) return;

  document.getElementById('remediate-modal-title').textContent = `Remediation Confirmation Gate`;
  document.getElementById('remediate-warning-text').textContent = 
    `You are about to approve remediation for '${finding.resource_name}'. This operation deletes orphaned resources interactively and eliminates recurring costs of $${finding.monthly_savings_estimate.toFixed(2)}/mo.`;

  document.getElementById('remediate-command-code').textContent = finding.remediation_command;
  document.getElementById('remediate-confirm-btn').onclick = () => executeRemediateAction(finding.id);
  document.getElementById('remediate-modal').classList.add('active');
}

function closeRemediateModal() {
  document.getElementById('remediate-modal').classList.remove('active');
}

async function executeRemediateAction(findingId) {
  try {
    const res = await fetch(`${API_BASE}/optimizer/remediate-action?finding_id=${findingId}&action=remediated`, {
      method: 'POST'
    });
    const data = await res.json();
    closeRemediateModal();
    showToast(`Remediation confirmed for Finding #${findingId}`, 'success');
    await refreshAllData();
  } catch (err) {
    showToast(`Remediation action failed: ${err.message}`, 'error');
  }
}

// 5. Actions: Load Samples, Scan, Script Download, Clear DB
async function triggerLoadSamples() {
  showToast('Loading pre-packaged GCP & Multi-Cloud billing datasets...', 'info');
  try {
    const res = await fetch(`${API_BASE}/billing/load-samples`, { method: 'POST' });
    const data = await res.json();
    showToast('Sample data loaded into SQLite! Running optimizer scan...', 'success');
    await triggerScan();
  } catch (err) {
    showToast(`Failed to load sample datasets: ${err.message}`, 'error');
  }
}

async function triggerScan() {
  showToast('Evaluating billing records against rules engine...', 'info');
  try {
    const res = await fetch(`${API_BASE}/optimizer/scan`, { method: 'POST' });
    const data = await res.json();
    showToast(`Scan complete: ${data.findings_detected} waste items identified ($${data.potential_monthly_savings}/mo savings)!`, 'success');
    await refreshAllData();
  } catch (err) {
    showToast(`Scan failed: ${err.message}`, 'error');
  }
}

function downloadRemediationScript() {
  const provider = document.getElementById('filter-provider')?.value || '';
  let url = `${API_BASE}/optimizer/generate-script`;
  if (provider) url += `?provider=${encodeURIComponent(provider)}`;
  
  showToast('Generating safe, confirmation-gated bash script (remediate_waste.sh)...', 'info');
  window.location.href = url;
}

async function triggerClearDatabase() {
  if (!confirm('Are you sure you want to purge all canonical resources and waste findings for a clean benchmark?')) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/billing/clear`, { method: 'DELETE' });
    showToast('Database purged. Ready for fresh imports.', 'info');
    await refreshAllData();
  } catch (err) {
    showToast(`Clear failed: ${err.message}`, 'error');
  }
}

// 6. Canonical Resources Explorer
async function loadResourcesTable() {
  try {
    const res = await fetch(`${API_BASE}/billing/records?limit=100`);
    const data = await res.json();
    currentResources = data.items || [];

    const tbody = document.getElementById('resources-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (currentResources.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:2rem; color:var(--text-muted);">No canonical resources found. Upload billing exports first.</td></tr>';
      return;
    }

    currentResources.forEach(r => {
      const tr = document.createElement('tr');
      const provClass = r.provider === 'gcp' ? 'badge-gcp' : r.provider === 'aws' ? 'badge-aws' : 'badge-azure';
      const statusColor = r.status_hint === 'active' ? '#10B981' : '#F59E0B';
      
      tr.innerHTML = `
        <td><span class="badge ${provClass}">${r.provider.toUpperCase()}</span></td>
        <td>
          <div style="font-weight:600;">${r.resource_name}</div>
          <div style="font-size:0.72rem; color:var(--text-muted); font-family:monospace;">${r.resource_id}</div>
        </td>
        <td>${r.resource_type}</td>
        <td>${r.region_or_zone || 'global'}</td>
        <td><span style="font-weight:700;">$${r.cost_amount.toFixed(2)}</span> ${r.currency}</td>
        <td><span style="color:${statusColor}; font-weight:600; text-transform:capitalize;">${r.status_hint}</span></td>
        <td>${r.usage_amount} ${r.usage_unit}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load resources:', err);
  }
}

// 7. Rule Catalog & Custom Rule Builder
async function loadRulesTable() {
  try {
    const res = await fetch(`${API_BASE}/rules`);
    const data = await res.json();
    
    const tbody = document.getElementById('rules-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    const allRules = [...(data.built_in_rules || []), ...(data.custom_rules || [])];
    allRules.forEach(r => {
      const tr = document.createElement('tr');
      const tierBadge = r.is_custom 
        ? '<span class="badge" style="background:rgba(139,92,246,0.2); color:#c084fc;">Tier 2: Custom</span>'
        : '<span class="badge" style="background:rgba(66,133,244,0.2); color:#93c5fd;">Tier 1: Built-in</span>';

      const actionBtn = r.is_custom
        ? `<button class="btn btn-danger" style="padding:0.25rem 0.5rem; font-size:0.75rem;" onclick="deleteCustomRule('${r.id}')">Delete</button>`
        : `<span style="font-size:0.75rem; color:var(--text-muted);">Immutable Core</span>`;

      tr.innerHTML = `
        <td>${tierBadge}</td>
        <td>
          <div style="font-weight:600;">${r.name}</div>
          <div style="font-size:0.72rem; color:var(--text-muted);">${r.id}</div>
        </td>
        <td>${r.category || 'Custom'}</td>
        <td><span class="badge badge-high">${r.severity}</span></td>
        <td><span style="color:#10B981; font-weight:600;">Enabled</span></td>
        <td>${actionBtn}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load rules:', err);
  }
}

async function createCustomRuleFromForm(event) {
  event.preventDefault();
  const name = document.getElementById('rule-form-name').value;
  const description = document.getElementById('rule-form-desc').value;
  const provider = document.getElementById('rule-form-provider').value;
  const resType = document.getElementById('rule-form-type').value;
  const minCost = parseFloat(document.getElementById('rule-form-min-cost').value || '0');
  const statusHint = document.getElementById('rule-form-status').value;
  const severity = document.getElementById('rule-form-severity').value;

  const conditions = [];
  if (minCost > 0) conditions.push({ field: 'cost_amount', operator: '>', value: minCost });
  if (statusHint) conditions.push({ field: 'status_hint', operator: '==', value: statusHint });

  const payload = {
    name,
    description,
    provider,
    resource_type: resType,
    conditions,
    severity
  };

  try {
    const res = await fetch(`${API_BASE}/rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to create rule');
    showToast(`Rule '${name}' created successfully!`, 'success');
    closeCustomRuleModal();
    await loadRulesTable();
  } catch (err) {
    showToast(`Error creating rule: ${err.message}`, 'error');
  }
}

async function deleteCustomRule(ruleId) {
  if (!confirm(`Delete custom policy '${ruleId}'?`)) return;
  try {
    await fetch(`${API_BASE}/rules/${ruleId}`, { method: 'DELETE' });
    showToast(`Rule '${ruleId}' deleted`, 'info');
    await loadRulesTable();
  } catch (err) {
    showToast(`Failed to delete rule: ${err.message}`, 'error');
  }
}

function openCustomRuleModal() {
  document.getElementById('custom-rule-modal').classList.add('active');
}

function closeCustomRuleModal() {
  document.getElementById('custom-rule-modal').classList.remove('active');
}

// 8. File Upload Setup
function setupFileUpload() {
  const fileInput = document.getElementById('billing-file-input');
  if (!fileInput) return;

  fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    const providerSelect = document.getElementById('upload-provider-select');
    if (providerSelect && providerSelect.value) {
      formData.append('provider', providerSelect.value);
    }

    showToast(`Uploading and parsing ${file.name}...`, 'info');
    try {
      const res = await fetch(`${API_BASE}/billing/upload`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');
      showToast(`Success: Ingested ${data.records_ingested} records (${data.provider_detected.toUpperCase()})!`, 'success');
      await triggerScan();
    } catch (err) {
      showToast(`Upload failed: ${err.message}`, 'error');
    }
    fileInput.value = '';
  });
}

// 9. Toast Helper
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast';
  const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

// 10. Copy Helper
function copyCode(elementId) {
  const code = document.getElementById(elementId).textContent;
  navigator.clipboard.writeText(code).then(() => {
    showToast('CLI snippet copied to clipboard!', 'success');
  });
}

// 11. Quick Database Actions
async function triggerLoadSamples() {
  showToast('Loading pre-packaged multi-cloud sample datasets...', 'info');
  try {
    const res = await fetch(`${API_BASE}/billing/load-samples?clear_existing=true`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to load samples');
    showToast(data.message || 'Sample datasets loaded successfully!', 'success');
    await triggerScan();
    await loadKPIs();
    await loadWasteFindings();
    await loadResources();
  } catch (err) {
    showToast(`Error loading samples: ${err.message}`, 'error');
  }
}

async function triggerClearDatabase() {
  if (!confirm('Are you sure you want to clear all canonical resources and waste findings from the database?')) {
    return;
  }
  showToast('Purging database records...', 'info');
  try {
    const res = await fetch(`${API_BASE}/billing/clear`, { method: 'POST' });
    const data = await res.json();
    showToast(data.message || 'Database purged successfully!', 'success');
    await loadKPIs();
    await loadWasteFindings();
    await loadResources();
  } catch (err) {
    showToast(`Failed to clear database: ${err.message}`, 'error');
  }
}
