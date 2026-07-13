# ruff: noqa: E501
"""A dependency-free local dashboard for RouteLLM analytics."""


def dashboard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RouteLLM Control Room</title>
  <style>
    :root { --ink:#17211f; --paper:#f8f4e8; --lime:#b6f36b; --teal:#1c7865; --muted:#66716d; --line:#d8d1bf; --dark:#182520; }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--ink); background:radial-gradient(circle at 90% 0%, #d7f1c3 0, transparent 28rem), var(--paper); font-family:Bahnschrift,"Trebuchet MS",sans-serif; }
    main { width:min(1160px,calc(100% - 32px)); margin:0 auto; padding:48px 0 72px; }
    header { display:flex; align-items:end; justify-content:space-between; gap:24px; border-bottom:2px solid var(--dark); padding-bottom:24px; }
    .eyebrow { color:var(--teal); font:700 12px/1.2 Consolas,monospace; letter-spacing:.12em; text-transform:uppercase; }
    h1 { margin:8px 0 0; font-size:clamp(34px,6vw,68px); line-height:.9; letter-spacing:-.06em; }
    .status { display:flex; align-items:center; gap:8px; color:var(--muted); font:600 13px/1.2 Consolas,monospace; }
    .pulse { width:10px; height:10px; border-radius:50%; background:var(--teal); box-shadow:0 0 0 5px #bfe0d6; }
    .grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:28px 0; }
    .card { min-height:142px; padding:18px; border:1px solid var(--line); background:#fffdf5b8; box-shadow:4px 4px 0 #d6cfbd; }
    .card.accent { background:var(--dark); color:var(--paper); border-color:var(--dark); box-shadow:4px 4px 0 var(--lime); }
    .label { color:var(--muted); font:700 11px/1.2 Consolas,monospace; letter-spacing:.08em; text-transform:uppercase; }
    .accent .label { color:#aebbb4; }
    .value { margin-top:22px; font-size:34px; line-height:1; font-weight:800; letter-spacing:-.04em; }
    .hint { margin-top:9px; font-size:13px; color:var(--muted); }
    .accent .hint { color:#c4d1c9; }
    .split { display:grid; grid-template-columns:1.1fr .9fr; gap:26px; margin-top:40px; }
    section { border-top:2px solid var(--dark); padding-top:14px; }
    h2 { margin:0 0 16px; font-size:17px; letter-spacing:-.02em; }
    .usage { display:grid; gap:10px; }
    .usage-row { display:grid; grid-template-columns:1fr auto; align-items:center; gap:12px; padding:12px 0; border-bottom:1px solid var(--line); }
    .bar { height:7px; background:#dce4d6; margin-top:7px; overflow:hidden; } .bar > i { display:block; height:100%; background:var(--teal); }
    table { width:100%; border-collapse:collapse; font-size:13px; } th { text-align:left; padding:0 8px 10px; color:var(--muted); font:700 10px/1 Consolas,monospace; letter-spacing:.08em; text-transform:uppercase; } td { padding:12px 8px; border-top:1px solid var(--line); } .pill { display:inline-block; padding:4px 7px; font:700 10px/1 Consolas,monospace; letter-spacing:.04em; } .local { background:var(--lime); } .cloud { background:#eadfc7; }
    .empty { color:var(--muted); padding:28px 0; font-size:14px; } button { border:1px solid var(--dark); background:var(--lime); color:var(--dark); padding:10px 13px; font:700 12px Consolas,monospace; cursor:pointer; } button:hover { background:#9bd64e; }
    @media (max-width:780px) { header { align-items:start; flex-direction:column; } .grid { grid-template-columns:repeat(2,1fr); } .split { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <main>
    <header>
      <div><div class="eyebrow">Local-first inference telemetry</div><h1>Control<br>Room.</h1></div>
      <div><div class="status"><span class="pulse"></span><span id="status">Loading analytics</span></div><div style="margin-top:12px"><button id="refresh">Refresh data</button></div></div>
    </header>
    <div class="grid">
      <article class="card accent"><div class="label">Estimated API savings</div><div class="value" id="savings">--</div><div class="hint" id="baseline">Against reference cloud baseline</div></article>
      <article class="card"><div class="label">Local route share</div><div class="value" id="local-share">--</div><div class="hint" id="local-count">-- local requests</div></article>
      <article class="card"><div class="label">Average route latency</div><div class="value" id="latency">--</div><div class="hint">Estimated end-to-end latency</div></article>
      <article class="card"><div class="label">Escalations</div><div class="value" id="escalations">--</div><div class="hint">Quality or transport fallbacks</div></article>
    </div>
    <div class="split">
      <section><h2>Model usage</h2><div class="usage" id="usage"><div class="empty">No routing decisions yet.</div></div></section>
      <section><h2>Recent decisions</h2><div id="decisions"><div class="empty">No routing decisions yet.</div></div></section>
    </div>
  </main>
  <script>
    const money = value => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:4}).format(value || 0);
    const text = value => String(value ?? '');
    const escape = value => text(value).replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[character]));
    async function load() {
      const status = document.getElementById('status'); status.textContent = 'Refreshing analytics';
      try {
        const [summaryResponse, decisionsResponse] = await Promise.all([fetch('/v1/analytics/summary'), fetch('/v1/analytics/decisions?limit=8')]);
        if (!summaryResponse.ok || !decisionsResponse.ok) throw new Error('Analytics API unavailable');
        const summary = await summaryResponse.json(); const decisions = await decisionsResponse.json();
        document.getElementById('savings').textContent = money(summary.estimated_savings_usd);
        document.getElementById('baseline').textContent = `${summary.estimated_savings_percent}% below ${summary.reference_baseline_model}`;
        const share = summary.request_count ? Math.round(summary.local_request_count / summary.request_count * 100) : 0;
        document.getElementById('local-share').textContent = `${share}%`;
        document.getElementById('local-count').textContent = `${summary.local_request_count} of ${summary.request_count} requests local`;
        document.getElementById('latency').textContent = `${Math.round(summary.average_estimated_latency_ms)} ms`;
        document.getElementById('escalations').textContent = summary.escalation_count;
        const maximum = Math.max(...summary.model_usage.map(item => item.request_count), 1);
        document.getElementById('usage').innerHTML = summary.model_usage.length ? summary.model_usage.map(item => `<div class="usage-row"><div><strong>${escape(item.model_key)}</strong><div class="bar"><i style="width:${item.request_count / maximum * 100}%"></i></div></div><div>${item.request_count} req<br><small>${money(item.actual_spend_usd)}</small></div></div>`).join('') : '<div class="empty">No routing decisions yet.</div>';
        document.getElementById('decisions').innerHTML = decisions.length ? `<table><thead><tr><th>Model</th><th>Type</th><th>Saved</th></tr></thead><tbody>${decisions.map(item => `<tr><td><strong>${escape(item.selected_model)}</strong><br><span class="pill ${item.is_local ? 'local' : 'cloud'}">${item.is_local ? 'LOCAL' : 'CLOUD'}</span></td><td>${escape(item.task_type)}</td><td>${money(item.estimated_savings_usd)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">No routing decisions yet.</div>';
        status.textContent = 'Analytics live';
      } catch (error) { status.textContent = error.message; }
    }
    document.getElementById('refresh').addEventListener('click', load); load();
  </script>
</body>
</html>"""
