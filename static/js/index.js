(function () {
  'use strict';

  const D = window.LEADERBOARD;
  const fmt = (v) => (v === null || v === undefined ? '–' : v.toFixed(1));

  /* ---------- leaderboard ---------- */

  const groups = [
    { id: 'main', label: 'pass³ by analysis task', expanded: false },
    { id: 'classes', label: 'By question class', expanded: false },
    { id: 'pairs', label: 'Instrument pairs', expanded: false },
  ];

  const cols = [];
  cols.push({
    group: 'main', label: 'Overall<br><span class="ci">(' + D.questions + ')</span>', best: 'max',
    title: 'pass³ (%) on the ' + D.questions + ' computable and recognition questions, with the 95% bootstrap interval',
    get: (r) => r.overall,
    show: (r) => fmt(r.overall) + (r.interval ? '<span class="ci">[' + fmt(r.interval[0]) + ', ' + fmt(r.interval[1]) + ']</span>' : ''),
  });
  D.tasks.forEach((t, i) => cols.push({
    group: 'main', detail: true, best: 'max',
    label: t.replace(' and ', ' and<br>').replace('Regional ', 'Regional<br>') + '<br><span class="ci">(' + D.task_questions[i] + ')</span>',
    title: 'pass³ (%) on the ' + D.task_questions[i] + ' ' + t + ' questions',
    get: (r) => r.tasks[i],
  }));
  cols.push({
    group: 'classes', detail: true, label: 'Computable<br>closed book',
    title: 'pass³ (%) on the 153 computable questions without the record', get: (r) => r.computable[0],
  });
  cols.push({
    group: 'classes', label: 'Computable<br>record', best: 'max',
    title: 'pass³ (%) on the 153 computable questions with the record', get: (r) => r.computable[1],
  });
  cols.push({
    group: 'classes', detail: true, label: 'Recognition<br>closed book',
    title: 'pass³ (%) on the 73 recognition questions without the record', get: (r) => r.recognition[0],
  });
  cols.push({
    group: 'classes', label: 'Recognition<br>record', best: 'max',
    title: 'pass³ (%) on the 73 recognition questions with the record', get: (r) => r.recognition[1],
  });
  cols.push({
    group: 'pairs', label: 'Moved', best: 'min',
    title: 'Cases right on the original in all three passes that turn wrong when one satellite’s data are altered (moved / right on the original; lower is better)',
    get: (r) => (r.pairs && r.pairs[1] ? r.pairs[0] / r.pairs[1] : null),
    show: (r) => (r.pairs ? r.pairs[0] + '/' + r.pairs[1] : '–'),
  });
  cols.push({
    group: 'pairs', detail: true, label: 'Held',
    title: 'Cases that stay right but are already right in the closed book or have no change as the reference',
    get: (r) => (r.pairs ? r.pairs[2] : null), show: (r) => (r.pairs ? String(r.pairs[2]) : '–'),
  });
  cols.push({
    group: 'pairs', detail: true, label: 'Beyond', best: 'max',
    title: 'Cases that stay right beyond both the closed book and a no-change answer',
    get: (r) => (r.pairs ? r.pairs[3] : null), show: (r) => (r.pairs && r.pairs[3] !== null ? String(r.pairs[3]) : '–'),
  });
  cols.push({
    group: 'pairs', detail: true, label: 'Placebo<br>moved',
    title: 'Placebo pairs (5% of clear scenes removed at random): cases that turn wrong / right on the original',
    get: (r) => (r.placebo && r.placebo[1] ? r.placebo[0] / r.placebo[1] : null),
    show: (r) => (r.placebo ? r.placebo[0] + '/' + r.placebo[1] : '–'),
  });

  const DEFAULT_SORT = { col: 0, dir: 'desc' };
  let sort = Object.assign({}, DEFAULT_SORT);

  const visible = () => cols.filter((c) => !c.detail || groups.find((g) => g.id === c.group).expanded);

  function bestValues() {
    return cols.map((c) => {
      if (!c.best) return null;
      const vals = D.models.map(c.get).filter((v) => v !== null && v !== undefined);
      return c.best === 'max' ? Math.max.apply(null, vals) : Math.min.apply(null, vals);
    });
  }
  const best = bestValues();

  function cell(c, r, isModel) {
    const v = c.get(r);
    const text = c.show ? c.show(r) : fmt(v);
    const i = cols.indexOf(c);
    const isBest = isModel && best[i] !== null && v !== null && v !== undefined && Math.abs(v - best[i]) < 1e-9;
    return '<td>' + (isBest ? '<b>' + text + '</b>' : text) + '</td>';
  }

  function render() {
    const table = document.getElementById('er-table');
    if (!table) return;
    const vis = visible();
    let head1 = '<tr><th class="model-col clickable" id="reset-cell" title="Reset sorting and collapse all groups">Reset</th>';
    groups.forEach((g) => {
      const n = vis.filter((c) => c.group === g.id).length;
      head1 += '<th colspan="' + n + '" class="group-head clickable' + (g.expanded ? ' expanded' : '') +
        '" data-group="' + g.id + '">' + g.label + '<span class="toggle">' + (g.expanded ? '◂' : '▸') + '</span></th>';
    });
    head1 += '</tr>';
    let head2 = '<tr><th class="model-col clickable sortable" data-col="name">Model</th>';
    vis.forEach((c) => {
      const i = cols.indexOf(c);
      const cls = sort.col === i ? ' sorted-' + sort.dir : '';
      head2 += '<th class="clickable sortable' + cls + '" data-col="' + i + '" title="' + c.title + '">' + c.label + '</th>';
    });
    head2 += '</tr>';

    const rows = D.models.slice();
    if (sort.col === 'name') {
      rows.sort((a, b) => a.name.localeCompare(b.name) * (sort.dir === 'asc' ? 1 : -1));
    } else {
      const c = cols[sort.col];
      rows.sort((a, b) => {
        const x = c.get(a), y = c.get(b);
        if (x === null || x === undefined) return 1;
        if (y === null || y === undefined) return -1;
        return (sort.dir === 'asc' ? x - y : y - x) || (b.overall - a.overall);
      });
    }
    let body = '';
    rows.forEach((r) => {
      body += '<tr><td><img class="model-logo" src="static/images/logos/' + r.logo + '.svg" alt="">' + r.name + '</td>';
      vis.forEach((c) => { body += cell(c, r, true); });
      body += '</tr>';
    });
    D.baselines.forEach((r, k) => {
      body += '<tr class="baseline' + (k === 0 ? ' first-baseline' : '') + '"><td>' + r.name + '</td>';
      vis.forEach((c) => { body += cell(c, r, false); });
      body += '</tr>';
    });
    table.innerHTML = '<thead>' + head1 + head2 + '</thead><tbody>' + body + '</tbody>';

    table.querySelectorAll('.group-head').forEach((th) => th.addEventListener('click', () => {
      const g = groups.find((x) => x.id === th.dataset.group);
      g.expanded = !g.expanded;
      render();
    }));
    table.querySelectorAll('.sortable').forEach((th) => th.addEventListener('click', () => {
      const key = th.dataset.col === 'name' ? 'name' : Number(th.dataset.col);
      if (sort.col === key) {
        sort.dir = sort.dir === 'desc' ? 'asc' : 'desc';
      } else {
        sort = { col: key, dir: key === 'name' || (cols[key] && cols[key].best === 'min') ? 'asc' : 'desc' };
      }
      render();
    }));
    document.getElementById('reset-cell').addEventListener('click', () => {
      groups.forEach((g) => { g.expanded = false; });
      sort = Object.assign({}, DEFAULT_SORT);
      render();
    });
  }

  /* ---------- failure steps ---------- */

  function renderSteps() {
    const box = document.getElementById('steps-chart');
    if (!box) return;
    const F = D.failure_steps;
    const max = Math.max.apply(null, F.leading.concat(F.other));
    const nLead = F.leading.reduce((a, b) => a + b, 0);
    const nOther = F.other.reduce((a, b) => a + b, 0);
    let html = '<div class="steps-legend"><span class="leading">Leading six models (' + nLead + ' runs)</span>' +
      '<span class="other">Other six models (' + nOther + ' runs)</span></div>';
    F.steps.forEach((s, i) => {
      const bar = (cls, v, n, who) => '<div class="bar-line" title="' + s + ': ' + v + ' of ' + n + ' failed runs of the ' + who + '">' +
        '<div class="bar ' + cls + '" style="width:' + (v / max * 85).toFixed(1) + '%"></div><span class="bar-value">' + v + '</span></div>';
      html += '<div class="step-row"><div class="step-name">' + s + '</div><div class="step-bars">' +
        bar('leading', F.leading[i], nLead, 'leading six') + bar('other', F.other[i], nOther, 'other six') + '</div></div>';
    });
    box.innerHTML = html;
  }

  /* ---------- carousel ---------- */

  function initCarousel(root) {
    const track = root.querySelector('.carousel-track');
    const slides = Array.from(track.children);
    const dots = root.querySelector('.carousel-dots');
    dots.innerHTML = slides.map((_, i) => '<span data-i="' + i + '" title="Example ' + (i + 1) + '"></span>').join('');
    let current = 0;
    const go = (i) => {
      current = (i + slides.length) % slides.length;
      slides.forEach((s, k) => s.classList.toggle('active', k === current));
      dots.querySelectorAll('span').forEach((d, k) => d.classList.toggle('active', k === current));
    };
    root.querySelector('.prev').addEventListener('click', () => go(current - 1));
    root.querySelector('.next').addEventListener('click', () => go(current + 1));
    dots.querySelectorAll('span').forEach((d) => d.addEventListener('click', () => go(Number(d.dataset.i))));
    let x0 = null;
    track.addEventListener('touchstart', (e) => { x0 = e.touches[0].clientX; }, { passive: true });
    track.addEventListener('touchend', (e) => {
      if (x0 === null) return;
      const dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 50) go(current + (dx < 0 ? 1 : -1));
      x0 = null;
    });
    go(0);
  }

  /* ---------- BibTeX ---------- */

  function initCopy() {
    const btn = document.getElementById('copy-bibtex');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const text = document.getElementById('bibtex').textContent;
      const done = () => { btn.querySelector('.label').textContent = 'Copied'; setTimeout(() => { btn.querySelector('.label').textContent = 'Copy'; }, 1500); };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, () => {});
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    render();
    renderSteps();
    document.querySelectorAll('.carousel').forEach(initCarousel);
    initCopy();
  });
})();
