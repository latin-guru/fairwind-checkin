// Draws the profile charts with Chart.js. If the CDN script doesn't load, the plain CSS bars stay visible.
(function () {
  "use strict";
  function draw() {
    var el = document.getElementById("profile-data");
    if (!el || typeof window.Chart === "undefined") return;
    var data = JSON.parse(el.textContent);
    document.body.classList.add("charts-on");
    document.querySelectorAll("canvas[data-chart]").forEach(function (canvas) {
      var d = data[canvas.dataset.chart];
      if (!d) return;
      new window.Chart(canvas, {
        type: "bar",
        data: { labels: d.labels, datasets: [{ data: d.counts, backgroundColor: "#0f766e", borderRadius: 6 }] },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { x: { beginAtZero: true, ticks: { precision: 0 } }, y: { grid: { display: false } } }
        }
      });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", draw);
  else draw();
})();
