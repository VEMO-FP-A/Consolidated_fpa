/* VEMO Consolidated Executive Summary — render logic */
let currentPeriod = 'ytd'; // 'ytd' | 'latest' — only drives the P&L reconciliation table
const budgetKeyFor = { ytd: 'budget_ytd', latest: 'budget_latest' };
const chartInstances = {};

/* ---------- formatting helpers (ported to match the sibling per-company
   dashboards' KPI13 cards byte-for-byte: parens for negatives, "$" for
   money, "bps"/"%" with parens, mlblShort month labels) ---------- */
const MN = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
function mlblShort(m){
  if (!m) return '—';
  const [y, mo] = m.split('-');
  return (MN[+mo - 1] || mo) + ' ' + y.slice(2);
}
function fmtMm(n){ // money in millions, parens for negative — e.g. "$42.5" / "($12.3)"
  if (n===null || n===undefined || isNaN(n)) return '—';
  const v = n/1e6, a = Math.abs(v);
  return (v<0?'($':'$') + a.toFixed(1) + (v<0?')':'');
}
function fmtPctParen(p){ // p is a fraction (e.g. -0.0725) -> "(7.3%)" / "7.3%"
  if (p===null || p===undefined || isNaN(p)) return '—';
  const pct = p*100, a = Math.abs(pct);
  return (pct<0?'(':'') + a.toFixed(1) + '%' + (pct<0?')':'');
}
function fmtBps(b){
  if (b===null || b===undefined || isNaN(b)) return '—';
  const a = Math.abs(b);
  return (b<0?'(':'') + Math.round(a).toLocaleString() + ' bps' + (b<0?')':'');
}
// plain (non-parens) versions, used in the P&L reconciliation table & big charts
function fmtMoney(v){
  if (v===null || v===undefined || isNaN(v)) return '—';
  const abs = Math.abs(v);
  const sign = v<0 ? '-' : '';
  return sign + '$' + (abs/1e6).toLocaleString('es-MX',{minimumFractionDigits:1,maximumFractionDigits:1}) + 'M';
}
function fmtPct(v){
  if (v===null || v===undefined || isNaN(v)) return '—';
  return (v*100).toLocaleString('es-MX',{minimumFractionDigits:1,maximumFractionDigits:1}) + '%';
}

/* ---------- KPI card spec per company ----------
   isPct: value is a fraction (margin/ROE) needing *100 for display & bps deltas
   better: 'up' -> higher is favorable (all 8 of our metrics are 'up') */
const KPI_SPECS = {
  dae: [
    {label:'Revenue', dataKey:'revenue', isPct:false},
    {label:'EBITDA', dataKey:'ebitda', isPct:false},
    {label:'EBITDA Margin', dataKey:'ebitda_margin', isPct:true},
    {label:'Utilidad Neta', dataKey:'net_income', isPct:false},
  ],
  ev: [
    {label:'Revenue', dataKey:'revenue', isPct:false},
    {label:'EBITDA', dataKey:'ebitda', isPct:false},
    {label:'EBITDA Margin', dataKey:'ebitda_margin', isPct:true},
    {label:'Utilidad Neta', dataKey:'net_income', isPct:false},
  ],
  vcn: [
    {label:'Revenue', dataKey:'revenue', isPct:false},
    {label:'EBITDA', dataKey:'ebitda', isPct:false},
    {label:'EBITDA Margin', dataKey:'ebitda_margin', isPct:true},
    {label:'Utilidad Neta', dataKey:'net_income', isPct:false},
  ],
  lto: [
    {label:'Ingreso Oper. Neto', dataKey:'revenue', isPct:false},
    {label:'Utilidad Neta', dataKey:'net_income', isPct:false},
    {label:'Cartera Neta', dataKey:'net_portfolio_board', isPct:false},
    {label:'ROE (mensual)', dataKey:'roe_pct_board', isPct:true},
  ],
};

function devPct(a, b){ if (b===null || b===undefined || !b || isNaN(b)) return null; return (a-b)/Math.abs(b)*100; }
function devBps(a, b){ if (b===null || b===undefined || isNaN(b)) return null; return (a-b)*10000; }
function isNegBetter(p){ if (p===null || p===undefined) return false; return p < 0; } // all our metrics are better:'up'

/* ---------- inline SVG sparkline — ported verbatim from the sibling dashboards ---------- */
function kpiSparkline(series, budgetSeries, w, h){
  w = w || 260; h = h || 50;
  const vals = series.filter(v => v !== null && v !== undefined && !isNaN(v));
  if (!vals.length) return '';
  const budVals = (budgetSeries || []).filter(v => v !== null && v !== undefined && !isNaN(v) && v !== 0);
  const allVals = vals.concat(budVals);
  const mn = Math.min(0, Math.min.apply(null, allVals)), mx = Math.max.apply(null, allVals);
  const range = mx - mn || 1;
  const n = series.length;
  const stepX = n > 1 ? w / (n - 1) : w;
  function y(v){ return h - ((v - mn) / range) * (h - 6) - 3; }
  let path = 'M0,' + h + ' ';
  for (let i=0; i<n; i++){
    const v = series[i]; if (v === null || v === undefined || isNaN(v)) continue;
    path += 'L' + (i*stepX).toFixed(1) + ',' + y(v).toFixed(1) + ' ';
  }
  path += 'L' + w + ',' + h + ' Z';
  let linePath = '', started = false;
  for (let i=0; i<n; i++){
    const v = series[i]; if (v === null || v === undefined || isNaN(v)) continue;
    linePath += (started ? 'L' : 'M') + (i*stepX).toFixed(1) + ',' + y(v).toFixed(1) + ' ';
    started = true;
  }
  let budgetPath = '';
  if (budgetSeries && budgetSeries.length){
    let bs = false;
    for (let i=0; i<n; i++){
      const bv = budgetSeries[i]; if (bv === null || bv === undefined || isNaN(bv) || bv === 0) continue;
      budgetPath += (bs ? 'L' : 'M') + (i*stepX).toFixed(1) + ',' + y(bv).toFixed(1) + ' ';
      bs = true;
    }
  }
  return '<svg viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none" style="display:block;width:100%;height:100%">' +
    '<defs><linearGradient id="spg" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0%" stop-color="#11ABAB" stop-opacity="0.30"/>' +
    '<stop offset="100%" stop-color="#11ABAB" stop-opacity="0.03"/>' +
    '</linearGradient></defs>' +
    '<path d="' + path + '" fill="url(#spg)" stroke="none"/>' +
    '<path d="' + linePath + '" fill="none" stroke="#11ABAB" stroke-width="1.8"/>' +
    (budgetPath ? '<path d="' + budgetPath + '" fill="none" stroke="#1F5454" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.7"/>' : '') +
    '</svg>';
}

function fmtRangeVal(v, isPct){
  if (v === null || v === undefined || isNaN(v)) return '';
  if (isPct) return (v*100).toFixed(0) + '%';
  const a = Math.abs(v);
  if (a >= 1e9) return (v/1e9).toFixed(1) + 'B';
  if (a >= 1e6) return (v/1e6).toFixed(1) + 'M';
  if (a >= 1e3) return (v/1e3).toFixed(0) + 'k';
  return v.toFixed(1);
}

function kpiCardHTML(spec, company){
  const kc = company.kpi_charts[spec.dataKey];
  const months = DATA.spark_months;
  const n = months.length;
  const cur = n - 1, prev = n - 2;
  const actual = kc ? kc.actual : [];
  const budget = kc ? kc.budget : [];
  const val = actual[cur];
  const valPrev = actual[prev];
  const valBud = budget[cur];

  const momPct = spec.isPct ? null : devPct(val, valPrev);
  const momBps = spec.isPct ? devBps(val, valPrev) : null;
  const budPct = spec.isPct ? null : (valBud ? devPct(val, valBud) : null);
  const budBps = spec.isPct ? devBps(val, valBud) : null;

  const momTxt = spec.isPct ? fmtBps(momBps) : (momPct===null ? '—' : fmtPctParen(momPct/100));
  const budTxt = spec.isPct ? fmtBps(budBps) : (budPct===null ? 'n.a.' : fmtPctParen(budPct/100));
  const momVal = spec.isPct ? momBps : momPct;
  const budVal = spec.isPct ? budBps : budPct;
  const momCls = isNegBetter(momVal) ? 'neg' : 'pos';
  const budCls = isNegBetter(budVal) ? 'neg' : 'pos';
  const arrSym = momVal===null ? '' : (momVal>=0 ? '▲' : '▼');
  // amber left-border: ported verbatim from the source dashboards' KPI13 cards —
  // triggered by an unfavorable MoM move, NOT by vs-Budget performance
  const cardCls = isNegBetter(momVal) ? 'amber' : '';

  const fmtCardVal = spec.isPct ? fmtPctParen(val) : fmtMm(val);
  const fmtBudVal = spec.isPct ? fmtPctParen(valBud) : fmtMm(valBud);

  const sparkline = kpiSparkline(actual, budget, 260, 50);
  const rangeVals = actual.filter(v => v !== null && v !== undefined && !isNaN(v));
  let rangeTxt = '';
  if (rangeVals.length){
    const mn = Math.min(...rangeVals), mx = Math.max(...rangeVals);
    rangeTxt = fmtRangeVal(mn, spec.isPct) + ' – ' + fmtRangeVal(mx, spec.isPct);
  }
  const dateRangeTxt = mlblShort(months[0]) + ' – ' + mlblShort(months[cur]);

  return `<div class="kpi-card ${cardCls}">
    <div class="kpi-l">${spec.label}</div>
    <div class="kpi-v">${fmtCardVal}</div>
    <div class="kpi-mom"><span class="arr ${momCls}">${arrSym}</span> <span class="${momCls}">${momTxt}</span> <span style="color:var(--tx3)">vs ${mlblShort(months[prev])}</span></div>
    ${valBud!==null && valBud!==undefined ? `<div class="kpi-bud"><span><span class="lbl">vs Budget</span> ${fmtBudVal}</span><span class="v ${budCls}">${budTxt}</span></div>` : ''}
    <div class="kpi-spark">${sparkline}</div>
    <div class="kpi-spark-foot"><span>${rangeTxt}</span><span>${dateRangeTxt}</span></div>
  </div>`;
}

function monthLabel(m){
  const meses = {'01':'Ene','02':'Feb','03':'Mar','04':'Abr','05':'May','06':'Jun','07':'Jul','08':'Ago','09':'Sep','10':'Oct','11':'Nov','12':'Dic'};
  const [y,mo] = m.split('-');
  return meses[mo] + " '" + y.slice(2);
}

function renderCompanyBlock(c){
  const spec = KPI_SPECS[c.key];
  const kpiHTML = spec.map(s => kpiCardHTML(s, c)).join('');
  const chartId = `chart-${c.key}`;
  return `
  <div class="company-block">
    <div class="company-head">
      <div class="company-id">
        <img class="company-logo" src="${LOGOS[c.logo]}" alt="${c.name} logo">
        <div class="company-names">
          <div class="cname">${c.name}</div>
          <div class="cfull">${c.full_name}</div>
        </div>
      </div>
      <a class="company-link" href="${c.url}" target="_blank" rel="noopener">Company Board Deck →</a>
    </div>
    <div class="kpi-grid">${kpiHTML}</div>
    <div class="chart-box">
      <div class="chart-title">${c.key === 'lto' ? 'Ingreso Operativo Neto (barras) vs. Utilidad Neta (línea) · mensual' : 'Revenue (barras) vs. EBITDA (línea) · mensual'}</div>
      <canvas id="${chartId}"></canvas>
    </div>
  </div>`;
}

function buildChart(c){
  const ctx = document.getElementById(`chart-${c.key}`);
  if (!ctx) return;
  const months = c.chart.months.map(monthLabel);
  const isDark = document.body.classList.contains('dark-mode');
  const gridColor = isDark ? '#353c42' : '#e8eaed';
  const txColor = isDark ? '#9aa3ac' : '#888';
  if (chartInstances[c.key]) chartInstances[c.key].destroy();
  chartInstances[c.key] = new Chart(ctx, {
    data: {
      labels: months,
      datasets: [
        {
          type: 'bar',
          label: c.key === 'lto' ? 'Ingreso Oper. Neto' : 'Revenue',
          data: c.chart.revenue,
          backgroundColor: c.accent + '55',
          borderColor: c.accent,
          borderWidth: 1,
          borderRadius: 3,
          order: 2,
          yAxisID: 'y',
        },
        {
          type: 'line',
          label: c.key === 'lto' ? 'Utilidad Neta' : 'EBITDA',
          data: c.chart.ebitda,
          borderColor: '#1F5454',
          backgroundColor: '#1F5454',
          pointRadius: 2,
          tension: 0.3,
          order: 1,
          yAxisID: 'y',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 }, color: txColor } },
        tooltip: {
          callbacks: {
            label: (item) => `${item.dataset.label}: ${fmtMoney(item.raw)}`,
          }
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 9 }, color: txColor, maxRotation: 0 } },
        y: {
          grid: { color: gridColor },
          ticks: { font: { size: 9 }, color: txColor, callback: (v) => fmtMoney(v) },
        },
      },
    },
  });
}

// ---------- P&L reconciliation table ----------
const RECON_ROWS = [
  {label:'Revenue / Ingreso Operativo Neto', field:'revenue'},
  {label:'Costo Operativo (Opex)', field:'opex', neg:true},
  {label:'Utilidad Bruta', field:'gross_profit', subtotal:true},
  {label:'SG&A', field:'sga_total', neg:true},
  {label:'EBITDA', field:'ebitda', subtotal:true, note:1},
  {label:'D&A', field:'da', neg:true},
  {label:'EBIT', field:'ebit', subtotal:true},
  {label:'Gastos Financieros', field:'interest_expense', neg:true},
  {label:'EBT (Utilidad antes de Impuestos)', field:'ebt', subtotal:true},
  {label:'Impuestos', field:'taxes', neg:true},
  {label:'Utilidad Neta Consolidada', field:'net_income', total:true},
];
const RECON_ORDER = ['dae','lto','ev','vcn'];

function cellClass(val, neg){
  if (val===null || val===undefined) return '';
  if (neg) return val < 0 ? 'neg' : (val > 0 ? 'pos' : '');
  return '';
}

function renderRecon(){
  const periodKey = currentPeriod;
  const companies = DATA.companies;
  let thead = `<thead><tr><th>Línea (${currentPeriod==='ytd'?'YTD 2026':DATA.generated_month_label})</th>`;
  RECON_ORDER.forEach(k => thead += `<th>${companies[k].name}</th>`);
  thead += `<th>Total VEMO</th></tr></thead>`;

  let tbody = '<tbody>';
  RECON_ROWS.forEach(row => {
    let total = 0, hasAny = false;
    let cells = '';
    RECON_ORDER.forEach(k => {
      const line = companies[k].pl[row.field];
      const val = line ? line[periodKey] : null;
      if (val !== null && val !== undefined){ total += val; hasAny = true; }
      cells += `<td class="${cellClass(val, row.neg)}">${fmtMoney(val)}</td>`;
    });
    const rowCls = row.total ? 'total' : (row.subtotal ? 'sub' : '');
    const noteSup = row.note ? '<sup>1</sup>' : '';
    tbody += `<tr class="${rowCls}"><td>${row.label}${noteSup}</td>${cells}<td>${hasAny ? fmtMoney(total) : '—'}</td></tr>`;
  });
  tbody += '</tbody>';
  document.getElementById('reconTable').innerHTML = thead + tbody;

  document.getElementById('reconFootnote').innerHTML =
    `<sup>1</sup> VEMO Impulso (LTO) es un negocio financiero (leasing) y no reporta EBITDA nativamente; ` +
    `para esta conciliación se calcula como EBT + Gastos Financieros + D&amp;A, de forma consistente con el resto de las empresas. ` +
    `Sus KPIs propios (ROE, Cartera Neta) se muestran en su tarjeta arriba en vez de EBITDA.`;
}

// ---------- init ----------
function renderCompanies(){
  const wrap = document.getElementById('companies');
  const order = ['dae','lto','ev','vcn'];
  wrap.innerHTML = order.map(k => renderCompanyBlock(DATA.companies[k])).join('');
  order.forEach(k => buildChart(DATA.companies[k]));
}

document.getElementById('periodSeg').addEventListener('click', (e) => {
  const btn = e.target.closest('button');
  if (!btn) return;
  currentPeriod = btn.dataset.period;
  [...document.getElementById('periodSeg').children].forEach(b => b.classList.toggle('active', b===btn));
  renderRecon();
});

document.getElementById('darkToggle').addEventListener('click', () => {
  document.body.classList.toggle('dark-mode');
  document.getElementById('darkToggle').textContent = document.body.classList.contains('dark-mode') ? '☀️' : '🌙';
  buildChart_all();
});
function buildChart_all(){
  ['dae','lto','ev','vcn'].forEach(k => buildChart(DATA.companies[k]));
}

renderCompanies();
renderRecon();
