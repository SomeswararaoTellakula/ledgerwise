const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const inr = (n) => "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
const LABEL = { APPROVE: "Approve", REJECT: "Reject", PARTIAL: "Pay GRN qty", HOLD_DUPLICATE: "Hold duplicate", ESCALATE: "Escalate / verify" };
let S = null;
let chosen = null;

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}

function vendorName(id) { return (S.vendors.find((v) => v.id === id) || {}).name || id; }

function curve(stats) {
  const W = 320, H = 170, pad = 26, weeks = 8, bw = (W - pad * 2) / weeks;
  let g = `<line x1="${pad}" y1="${H - 22}" x2="${W - 6}" y2="${H - 22}" stroke="#d8cfba"/>`;
  [0, 50, 100].forEach((v) => {
    const y = H - 22 - (v / 100) * (H - 40);
    g += `<text x="2" y="${y + 3}">${v}%</text><line x1="${pad}" x2="${W - 6}" y1="${y}" y2="${y}" stroke="#eee6d3"/>`;
  });
  for (let w = 1; w <= weeks; w++) {
    const row = stats.weeks.find((r) => r.week === w);
    const x = pad + (w - 1) * bw + 4;
    g += `<text x="${x + bw / 2 - 8}" y="${H - 8}">W${w}</text>`;
    if (!row || !row.exceptions) continue;
    const h = Math.max(2, (row.auto_rate / 100) * (H - 40));
    g += `<rect class="bar ${row.auto_rate ? "" : "zero"}" x="${x}" y="${H - 22 - h}" width="${bw - 8}" height="${h}" rx="2"><title>Week ${w}: ${row.auto}/${row.exceptions} auto</title></rect>`;
    g += `<text class="val" x="${x}" y="${H - 26 - h}">${Math.round(row.auto_rate)}</text>`;
  }
  $("#curve").innerHTML = g;
  $("#kpis").innerHTML = [
    [`${stats.processed}/${stats.total}`, "invoices processed"],
    [stats.total_exceptions, "had an exception"],
    [`${stats.auto_rate}%`, "auto-resolved"],
    [stats.total_wrong, "auto decisions the lead would overturn"],
  ].map(([b, s]) => `<div class="kpi"><b>${b}</b><span>${s}</span></div>`).join("");
}

function precChips(ps) {
  if (!ps || !ps.length) return "";
  return `<div class="prec">${ps.map((p) => `<span class="chip ${p.decision}" title="${esc(p.reason)}">${esc(p.invoice)} · ${p.decision} · ${p.is_human ? esc(p.decided_by.split(" (")[0]) : "agent"}</span>`).join("")}</div>`;
}

function card(r, review = false) {
  const tag = r.straight_through ? `<span class="tag clean">clean match</span>`
    : r.status === "auto_resolved" ? `<span class="tag auto">auto · from memory</span>`
    : `<span class="tag human">${r.status === "human_resolved" ? "decided by you" : "needs you"}</span>`;
  const wrong = r.outcome === "wrong" ? `<span class="tag wrong">lead disagrees</span>` : "";
  const stampDecision = r.human_decision || r.decision;
  const stamp = review ? "" : `<div class="stamp ${stampDecision}">${LABEL[stampDecision] || stampDecision}</div>`;
  const excs = (r.exceptions || []).map((d) => `
    <div class="exc"><div class="t">${d.exception.type.replace(/_/g, " ")}</div>
      <div>${esc(d.exception.summary)} <span class="meta">· at risk ${inr(d.exception.amount_at_risk)}</span></div>
      <div class="rule">${d.auto ? "✓" : "↗"} ${esc(d.rule)}</div>${precChips(d.precedents)}</div>`).join("");
  const email = r.vendor_email ? `<details><summary>Drafted vendor email</summary><pre>${esc(r.vendor_email)}</pre></details>` : "";
  const human = r.human_reason ? `<p class="explain"><b>Your note (retained):</b> ${esc(r.human_reason)}</p>` : "";
  const note = r.note ? `<div class="note">📎 ${esc(r.note)}</div>` : "";
  return `<article class="card ${review ? "review" : ""}" id="c-${esc(r.invoice_id)}">
    <div class="head"><div><span class="id">${esc(r.invoice_id)}</span> <span class="meta">${esc(r.vendor)} · W${r.week} · ${r.date}</span></div>
    <div class="amt">${inr(r.total)}</div></div>
    <div style="margin-top:6px">${tag}${wrong}</div>${stamp}${note}${excs}
    ${r.straight_through ? "" : `<p class="explain">${esc(r.explanation)}</p>`}${human}${email}
    ${review ? reviewForm(r) : ""}</article>`;
}

function reviewForm(r) {
  const opts = ["APPROVE", "PARTIAL", "REJECT", "HOLD_DUPLICATE", "ESCALATE"];
  const h = r.reviewer_hint;
  return `<div class="decide">
    ${r.suggested ? `<div class="meta">Agent leans: <b>${LABEL[r.suggested] || r.suggested}</b> — but won't act without you.</div>` : ""}
    <div class="row">${opts.map((o) => `<button data-d="${o}">${LABEL[o]}</button>`).join("")}</div>
    <textarea id="reason" placeholder="Why? This note is what the agent will remember next time."></textarea>
    ${h ? `<div class="hint"><b>AP lead's notebook:</b> ${LABEL[h.decision]} — ${esc(h.reason)} <button id="useHint" style="margin-left:6px">Use this</button></div>` : ""}
    <button class="primary" id="submitDecision">Save decision to memory</button></div>`;
}

function render() {
  const m = S.memory;
  $("#memBadge").textContent = m.enabled ? (m.backend === "hindsight" ? `Hindsight · ${m.bank_id}` : "local memory (offline)") : "memory OFF";
  $("#memBadge").className = "badge" + (m.enabled ? "" : " off");
  $("#memToggle").checked = m.enabled;
  curve(S.stats);
  $("#queue").innerHTML = S.next.map((n) => `<li><span>${esc(n.id)}</span><span>${esc(vendorName(n.vendor_id).split(" ")[0])} · W${n.week}</span></li>`).join("") || "<li>All invoices processed.</li>";
  const pending = S.results.filter((r) => S.pending.includes(r.invoice_id));
  $("#review").innerHTML = pending.map((r) => card(r, true)).join("");
  $("#feed").innerHTML = S.results.filter((r) => !S.pending.includes(r.invoice_id)).map((r) => card(r)).join("");
  $("#empty").style.display = S.results.length ? "none" : "block";
  const blocked = S.pending.length > 0, done = S.stats.processed >= S.stats.total;
  $("#nextBtn").disabled = blocked || done;
  $("#weekBtn").disabled = done && !blocked;
  $("#allBtn").disabled = done && !blocked;
  $("#nextBtn").textContent = blocked ? "Decide the invoice above first" : done ? "All 8 weeks processed" : "Process next invoice";
  $("#vendors").innerHTML = S.vendors.map((v) => `<li><div class="vn">${esc(v.name)}</div><div class="vq">${esc(v.category)} · ${esc(v.terms)}</div><button data-v="${v.id}">Brief</button></li>`).join("");
  $("#recall").innerHTML = S.recall_log.slice().reverse().map((l) => `<li><b>recall</b> “${esc(l.query)}” → ${l.hits} memories, ${l.precedents} precedents</li>`).join("") || "<li>No recalls yet.</li>";
  wireReview(pending[0]);
}

function wireReview(r) {
  if (!r) return;
  chosen = null;
  document.querySelectorAll(".decide .row button").forEach((b) => b.onclick = () => {
    chosen = b.dataset.d;
    document.querySelectorAll(".decide .row button").forEach((x) => x.classList.toggle("sel", x === b));
  });
  const hint = $("#useHint");
  if (hint) hint.onclick = () => {
    chosen = r.reviewer_hint.decision; $("#reason").value = r.reviewer_hint.reason;
    document.querySelectorAll(".decide .row button").forEach((x) => x.classList.toggle("sel", x.dataset.d === chosen));
  };
  $("#submitDecision").onclick = async () => {
    const reason = $("#reason").value.trim();
    if (!chosen || !reason) { alert("Pick a decision and write a reason — the reason is what gets remembered."); return; }
    const j = await api("/api/decide", { invoice_id: r.invoice_id, decision: chosen, reason });
    S = j.state; render();
  };
}

$("#nextBtn").onclick = async () => { const j = await api("/api/next", {}); S = j.state; render(); };
$("#weekBtn").onclick = async () => { S = (await api("/api/run", {})).state; render(); };
$("#allBtn").onclick = async () => { S = (await api("/api/run", { until_week: 99 })).state; render(); };
$("#resetBtn").onclick = async () => { S = (await api("/api/reset", { memory_enabled: $("#memToggle").checked })).state; render(); };
$("#memToggle").onchange = async (e) => { S = (await api("/api/reset", { memory_enabled: e.target.checked })).state; render(); };
$("#vendors").onclick = async (e) => {
  const id = e.target.dataset && e.target.dataset.v; if (!id) return;
  $("#briefTitle").textContent = vendorName(id); $("#briefBody").textContent = "Reflecting over this vendor's history…";
  $("#briefDlg").showModal();
  try { $("#briefBody").textContent = (await api(`/api/brief/${id}`)).brief; }
  catch (err) { $("#briefBody").textContent = String(err); }
};

fetch("/api/state").then((r) => r.json()).then((j) => { S = j; render(); });
