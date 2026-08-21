let nanoChart = null;

document.addEventListener("DOMContentLoaded", () => {
    initChart();
    fetchHistory();

    document.getElementById("sim-form").addEventListener("submit", (e) => {
        e.preventDefault();
        runSimulation();
    });
});

async function runSimulation() {
    const payload = {
        project_name: document.getElementById("project_name").value,
        contaminant_type: document.getElementById("contaminant_type").value,
        initial_concentration: parseFloat(document.getElementById("initial_concentration").value),
        nano_material: document.getElementById("nano_material").value,
        nano_dosage: parseFloat(document.getElementById("nano_dosage").value),
        uv_intensity: parseFloat(document.getElementById("uv_intensity").value),
        biomass_density: parseFloat(document.getElementById("biomass_density").value),
        contact_time: parseFloat(document.getElementById("contact_time").value),
        ph: parseFloat(document.getElementById("ph").value)
    };

    try {
        const response = await fetch("/api/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        
        // Update dashboard widgets, compliance status, table, and charts
        updateDashboard(data);
        fetchHistory();
    } catch (err) {
        console.error("Simulation error:", err);
    }
}

async function fetchHistory() {
    try {
        const response = await fetch("/api/history");
        const history = await response.json();
        const tbody = document.getElementById("history-table-body");
        tbody.innerHTML = "";

        history.forEach(item => {
            const isCompliant = item.is_compliant !== undefined ? item.is_compliant : true;
            const badgeClass = isCompliant 
                ? "bg-emerald-900/60 text-emerald-300 border-emerald-700" 
                : "bg-rose-900/60 text-rose-300 border-rose-700";

            const row = document.createElement("tr");
            row.className = "hover:bg-slate-700/50 transition border-b border-slate-700/50";
            row.innerHTML = `
                <td class="p-2 font-mono text-slate-400">#${item.id}</td>
                <td class="p-2 font-semibold text-teal-300">${item.project_name}</td>
                <td class="p-2">${item.contaminant_type}</td>
                <td class="p-2">${item.nano_material}</td>
                <td class="p-2">${item.nano_dosage} mg/L</td>
                <td class="p-2 font-bold ${isCompliant ? 'text-teal-400' : 'text-rose-400'}">
                    ${item.effluent_concentration} mg/L
                </td>
                <td class="p-2 font-bold text-emerald-400">${item.total_removal_efficiency}%</td>
                <td class="p-2">
                    <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${badgeClass}">
                        ${isCompliant ? 'PASS' : 'FAIL'}
                    </span>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (err) {
        console.error("Error fetching history:", err);
    }
}

function updateDashboard(data) {
    const results = data.simulation_results;
    const compliance = data.compliance_and_optimization;

    // 1. Core Simulation Metric Cards
    document.getElementById("metric-effluent").textContent = `${results.effluent_concentration_mg_L} mg/L`;
    document.getElementById("metric-total-eff").textContent = `${results.total_removal_efficiency_pct}%`;
    document.getElementById("metric-viability").textContent = `${results.bio_viability_pct}%`;
    document.getElementById("metric-leaching").textContent = `${results.nano_leaching_mg_L} mg/L`;

    // 2. Optimization Cards
    if (compliance) {
        const timeElem = document.getElementById("metric-required-time");
        const dosageElem = document.getElementById("metric-required-dosage");
        
        if (timeElem) timeElem.textContent = `${compliance.required_contact_time_min} min`;
        if (dosageElem) dosageElem.textContent = `${compliance.min_required_dosage_mg_L} mg/L`;

        // 3. Update EPA Compliance Banner
        updateSafetyBanner(compliance, results.effluent_concentration_mg_L);
    }

    // 4. Update Time-Series Graph
    updateChart(data.time_series, compliance ? compliance.epa_mcl_mg_L : null);
}

function updateSafetyBanner(compliance, finalConc) {
    const banner = document.getElementById("safety-banner");
    const title = document.getElementById("safety-title");
    const limitTag = document.getElementById("safety-limit-tag");
    const message = document.getElementById("safety-message");

    if (!banner) return;

    banner.classList.remove("hidden", "bg-emerald-950/80", "border-emerald-500", "text-emerald-200", "bg-rose-950/80", "border-rose-500", "text-rose-200");

    limitTag.textContent = `EPA Limit: ${compliance.epa_mcl_mg_L} mg/L`;

    if (compliance.is_compliant) {
        banner.classList.add("bg-emerald-950/80", "border-emerald-500", "text-emerald-200");
        title.textContent = "✅ EPA WATER QUALITY STANDARD ACHIEVED";
        message.textContent = `The effluent concentration (${finalConc} mg/L) meets environmental safety regulations. Minimum required contact time was estimated at ${compliance.required_contact_time_min} minutes.`;
    } else {
        banner.classList.add("bg-rose-950/80", "border-rose-500", "text-rose-200");
        title.textContent = "⚠️ EPA WATER QUALITY THRESHOLD EXCEEDED";
        message.textContent = `The effluent concentration (${finalConc} mg/L) exceeds safety limits. Consider increasing catalyst dosage to at least ${compliance.min_required_dosage_mg_L} mg/L or extending contact time.`;
    }
}

function initChart() {
    const ctx = document.getElementById("nanoChart").getContext("2d");
    nanoChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Contaminant (mg/L)',
                    data: [],
                    borderColor: 'rgba(239, 68, 68, 1)',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    fill: true,
                    tension: 0.3
                },
                {
                    label: 'Biomass (mg/L)',
                    data: [],
                    borderColor: 'rgba(16, 185, 129, 1)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: false,
                    tension: 0.3
                },
                {
                    label: 'EPA Compliance Limit',
                    data: [],
                    borderColor: 'rgba(245, 158, 11, 0.8)',
                    borderDash: [6, 6],
                    borderWidth: 2,
                    fill: false,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { 
                    title: { display: true, text: 'Time (minutes)', color: '#94a3b8' },
                    grid: { color: 'rgba(51, 65, 85, 0.5)' },
                    ticks: { color: '#94a3b8' }
                },
                y: { 
                    title: { display: true, text: 'Concentration (mg/L)', color: '#94a3b8' },
                    grid: { color: 'rgba(51, 65, 85, 0.5)' },
                    ticks: { color: '#94a3b8' },
                    beginAtZero: true 
                }
            },
            plugins: {
                legend: { labels: { color: '#f1f5f9' } }
            }
        }
    });
}

function updateChart(timeSeries, epaLimit) {
    if (!nanoChart || !timeSeries) return;
    
    nanoChart.data.labels = timeSeries.time_min;
    nanoChart.data.datasets[0].data = timeSeries.contaminant_mg_L;
    nanoChart.data.datasets[1].data = timeSeries.biomass_mg_L;

    // Render EPA Threshold line across all time steps
    if (epaLimit !== null && epaLimit !== undefined) {
        nanoChart.data.datasets[2].data = new Array(timeSeries.time_min.length).fill(epaLimit);
    } else {
        nanoChart.data.datasets[2].data = [];
    }

    nanoChart.update();
}

// Action Handlers
function exportCSV() {
    window.location.href = "/api/export/csv";
}

function exportPDF() {
    window.print();
}