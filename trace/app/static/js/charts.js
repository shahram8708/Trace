/* global Chart */
(function () {
  const centerTextPlugin = {
    id: 'centerText',
    afterDraw(chart, args, opts) {
      if (!opts || !opts.text) return;
      const { ctx, chartArea: { width, height } } = chart;
      ctx.save();
      ctx.font = opts.font || '700 18px Inter, sans-serif';
      ctx.fillStyle = opts.color || '#111827';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(opts.text, width / 2, height / 2);
      ctx.restore();
    }
  };

  function renderQualityDoughnutChart(elementId, data) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const ctx = el.getContext('2d');
    const counts = [data.again_count || 0, data.hard_count || 0, data.good_count || 0, data.easy_count || 0];
    const total = counts.reduce((a, b) => a + b, 0);
    const displayCounts = total === 0 ? [1, 0, 0, 0] : counts;
    const colors = ['#EF4444', '#F59E0B', '#148F77', '#3B82F6'];
    const labels = ['Again', 'Hard', 'Good', 'Easy'];
    const chart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: displayCounts,
          backgroundColor: colors,
          borderWidth: 0,
          hoverOffset: 6,
        }],
      },
      options: {
        responsive: true,
        cutout: '65%',
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            callbacks: {
              label: (context) => {
                const value = context.raw;
                if (total === 0) return 'No reviews';
                const pct = ((value / total) * 100).toFixed(1);
                return `${context.label}: ${value} (${pct}%)`;
              }
            }
          },
          centerText: {
            text: total === 0 ? 'No reviews' : `${total} reviewed`,
            font: '700 18px Inter, sans-serif',
            color: '#111827',
          },
        },
      },
      plugins: [centerTextPlugin],
    });
    return chart;
  }

  function renderRetentionLineChart(elementId, dataPoints) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const ctx = el.getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: dataPoints.map((d) => d.date),
        datasets: [{
          label: 'Retention',
          data: dataPoints.map((d) => (d.retention_strength || 0) * 100),
          borderColor: '#1B4F72',
          backgroundColor: 'rgba(209, 242, 235, 0.35)',
          fill: true,
          tension: 0.3,
          pointRadius: 4,
          pointBackgroundColor: '#1B4F72',
        }],
      },
      options: {
        responsive: true,
        scales: {
          y: {
            min: 0,
            max: 100,
            ticks: { callback: (val) => `${val}%` },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.parsed.y.toFixed(1)}%`,
            },
          },
        },
      },
    });
  }

  function renderDomainBarChart(elementId, domainData) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const ctx = el.getContext('2d');
    const labels = domainData.map((d) => d.domain);
    const values = domainData.map((d) => (d.avg_retention || 0) * 100);
    const colors = domainData.map((d) => {
      const v = d.avg_retention || 0;
      if (v >= 0.8) return '#148F77';
      if (v >= 0.5) return '#F59E0B';
      return '#EF4444';
    });
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderRadius: 6,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        scales: {
          x: { min: 0, max: 100, ticks: { callback: (v) => `${v}%` } },
          y: { ticks: { autoSkip: false } },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.parsed.x.toFixed(1)}%`,
            },
          },
        },
      },
    });
  }

  function renderActivityHeatmap(containerId, activityData) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    activityData.forEach((item) => {
      const cell = document.createElement('div');
      const count = item.count || 0;
      cell.className = 'heatmap-cell';
      cell.dataset.count = count;
      cell.dataset.tooltip = `${item.date}: ${count} reviews`;
      let level = 'count-0';
      if (count >= 8) level = 'count-8';
      else if (count >= 4) level = 'count-4';
      else if (count >= 1) level = 'count-1';
      cell.classList.add(level);
      container.appendChild(cell);
    });
  }

  window.renderQualityDoughnutChart = renderQualityDoughnutChart;
  window.renderRetentionLineChart = renderRetentionLineChart;
  window.renderDomainBarChart = renderDomainBarChart;
  window.renderActivityHeatmap = renderActivityHeatmap;
})();
