/**
 * Gold Pulse Web v3.0
 * ECharts-based real-time gold price dashboard
 */

const MAX_POINTS = 120;
let chart;
let darkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;

const COLORS = {
  london: '#b88200',
  newyork: '#0ea5e9',
  shanghai: '#dc2626',
};

const history = {
  london: [],
  newyork: [],
  shanghai: [],
  timestamps: [],
};

// ── Chart ──

function makeArea(hex) {
  return {
    type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
    colorStops: [
      { offset: 0, color: hex + '33' },
      { offset: 1, color: hex + '00' },
    ],
  };
}

function themeColors() {
  return darkMode
    ? { text: '#94a3b8', title: '#f1f5f9', split: '#1e293b',
        tipBg: '#1e293b', tipBorder: '#334155', tipText: '#f1f5f9' }
    : { text: '#64748b', title: '#1e293b', split: '#e2e8f0',
        tipBg: '#ffffff', tipBorder: '#e2e8f0', tipText: '#1e293b' };
}

function initChart() {
  chart = echarts.init(document.getElementById('chart'));
  applyChartOption();

  window.addEventListener('resize', () => chart.resize());

  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  mq.addEventListener('change', (e) => {
    darkMode = e.matches;
    applyChartOption();
    updateChartData();
  });
}

function applyChartOption() {
  const t = themeColors();
  chart.setOption({
    backgroundColor: 'transparent',
    title: {
      text: '黄金价格走势 · 实时滚动',
      left: 'center', top: 8,
      textStyle: { fontSize: 13, fontWeight: 'bold', color: t.title },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: t.tipBg,
      borderColor: t.tipBorder,
      textStyle: { color: t.tipText, fontSize: 12 },
      formatter: (params) => {
        const time = new Date(params[0].value[0])
          .toLocaleTimeString('zh-CN', { hour12: false });
        let html = `<div style="font-size:11px;color:#64748b;margin-bottom:4px">${time}</div>`;
        for (const p of params) {
          if (p.value[1] == null) continue;
          html += `<div style="color:${p.color}">${p.marker}${p.seriesName}: <b>${p.value[1].toFixed(2)}</b></div>`;
        }
        return html;
      },
    },
    legend: {
      data: ['伦敦金(折算CNY/g)', '纽约金(折算CNY/g)', '上海金 CNY/g'],
      bottom: 5,
      textStyle: { color: t.text, fontSize: 11 },
      itemWidth: 16, itemHeight: 3,
    },
    grid: { left: 55, right: 20, top: 45, bottom: 40 },
    xAxis: {
      type: 'time',
      axisLabel: { color: t.text, fontSize: 10, hideOverlap: true },
      axisLine: { lineStyle: { color: t.split } },
    },
    yAxis: {
      type: 'value', scale: true,
      axisLabel: { color: t.text, fontSize: 10 },
      splitLine: { lineStyle: { color: t.split, type: 'dashed' } },
    },
    series: [
      {
        name: '伦敦金(折算CNY/g)', type: 'line', smooth: true,
        showSymbol: false, connectNulls: true,
        lineStyle: { width: 2, color: COLORS.london },
        itemStyle: { color: COLORS.london },
        areaStyle: { color: makeArea(COLORS.london) },
        data: [],
      },
      {
        name: '纽约金(折算CNY/g)', type: 'line', smooth: true,
        showSymbol: false, connectNulls: true,
        lineStyle: { width: 2, color: COLORS.newyork },
        itemStyle: { color: COLORS.newyork },
        areaStyle: { color: makeArea(COLORS.newyork) },
        data: [],
      },
      {
        name: '上海金 CNY/g', type: 'line', smooth: true,
        showSymbol: false, connectNulls: true,
        lineStyle: { width: 2, color: COLORS.shanghai },
        itemStyle: { color: COLORS.shanghai },
        areaStyle: { color: makeArea(COLORS.shanghai) },
        data: [],
      },
    ],
  }, true);
}

function updateChartData() {
  const keys = ['london', 'newyork', 'shanghai'];
  const seriesData = keys.map(key => {
    const data = [];
    for (let i = 0; i < history.timestamps.length; i++) {
      const v = history[key][i];
      if (v != null && v > 0) {
        data.push([history.timestamps[i], v]);
      }
    }
    return data;
  });
  chart.setOption({ series: seriesData.map(d => ({ data: d })) });
}

// ── Cards ──

function formatChange(diff, pct) {
  if (diff == null || isNaN(diff)) return { text: '', cls: 'neut' };
  const arrow = diff >= 0 ? '▲' : '▼';
  const cls = diff > 0 ? 'up' : diff < 0 ? 'down' : 'neut';
  return { text: `${arrow} ${Math.abs(diff).toFixed(2)}  (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)`, cls };
}

function updateCard(prefix, item, label) {
  if (!item) return;
  const change = formatChange(item.diff, item.pct);
  document.getElementById(prefix + '-price').textContent =
    item.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const changeEl = document.getElementById(prefix + '-change');
  changeEl.textContent = change.text;
  changeEl.className = 'card-change ' + change.cls;
  document.getElementById(prefix + '-implied').textContent = item.implied || '';
  const high = Number(item.high) || 0;
  const low = Number(item.low) || 0;
  document.getElementById(prefix + '-extra').textContent =
    `${label} ${item.prev_close.toFixed(2)}  ·  高 ${high.toFixed(2)}  低 ${low.toFixed(2)}`;
}

// ── Data refresh ──

async function refresh() {
  try {
    const resp = await fetch('/api/gold');
    const data = await resp.json();
    if (data.error) throw new Error(data.error);

    if (data.usdcny) {
      document.getElementById('usdcny').textContent = `USD/CNY ${data.usdcny.toFixed(4)}`;
    }

    updateCard('lon', data.london, '昨结');
    updateCard('ny', data.newyork, '昨收');
    updateCard('sh', data.shanghai, '昨收');

    const now = Date.now();
    history.timestamps.push(now);
    if (history.timestamps.length > MAX_POINTS) history.timestamps.shift();

    history.london.push(data.london && data.london.implied_cny_g ? data.london.implied_cny_g : null);
    history.newyork.push(data.newyork && data.newyork.implied_cny_g ? data.newyork.implied_cny_g : null);
    history.shanghai.push(data.shanghai ? data.shanghai.price : null);

    for (const k of ['london', 'newyork', 'shanghai']) {
      if (history[k].length > MAX_POINTS) history[k].shift();
    }

    updateChartData();

    const s = document.getElementById('status');
    s.textContent = '● 实时连接中 · 每 5 秒刷新';
    s.className = 'status ok';
  } catch (e) {
    const s = document.getElementById('status');
    s.textContent = '● 更新失败: ' + e.message;
    s.className = 'status err';
  }
}

// ── Init ──

if (typeof echarts === 'undefined') {
  const s = document.getElementById('status');
  s.textContent = '● ECharts 加载失败，请检查网络';
  s.className = 'status err';
} else {
  initChart();
  refresh();
  setInterval(refresh, 5000);
}
