/**
 * AgniNetra - Live Pipeline Simulation Demo
 * Walks judges through the live intelligence pipeline:
 * Input -> Detection -> Processing/AI -> Risk Classification -> Map Visualization -> Alert -> Response -> Resolution
 *
 * Uses REAL data from /risk-sites (highest risk_score row).
 */

(function () {
  'use strict';

  let isRunning = false;
  let currentTimers = [];
  let demoRadiusCircle = null;
  let activePulsingElement = null;

  function wait(ms) {
    return new Promise((resolve, reject) => {
      const timerId = setTimeout(() => {
        resolve();
      }, ms);
      currentTimers.push({ timerId, reject });
    });
  }

  function clearAllTimers() {
    currentTimers.forEach(({ timerId, reject }) => {
      clearTimeout(timerId);
      if (reject) {
        try {
          reject(new Error('Simulation cancelled'));
        } catch (_) {}
      }
    });
    currentTimers = [];
  }

  async function getTargetIncident() {
    let dataset = window.sites;
    if (!dataset || dataset.length === 0) {
      try {
        const res = await fetch('/risk-sites');
        const data = await res.json();
        dataset = data.risk_sites || [];
        window.sites = dataset;
      } catch (err) {
        console.error('[AgniNetra Simulation] Failed to fetch /risk-sites:', err);
        return null;
      }
    }

    if (!dataset || dataset.length === 0) {
      return null;
    }

    // Pick single highest risk_score row from actual data
    const sorted = [...dataset].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
    return sorted[0];
  }

  function getPriorityColor(priority) {
    switch (priority) {
      case 'HIGH':
        return '#8B3A2B';
      case 'MEDIUM':
        return '#9C7A24';
      default:
        return '#4B6B4E';
    }
  }

  function renderConsoleShell(incident) {
    const consoleEl = document.getElementById('demoConsole');
    if (!consoleEl) return;

    consoleEl.style.display = 'block';
    consoleEl.innerHTML = `
      <div class="demo-console-header">
        <div class="demo-console-title">
          <span>Live Pipeline Simulation</span>
        </div>
        <div class="demo-live-badge">
          <span class="demo-live-dot"></span>
          ACTIVE SIMULATION
        </div>
      </div>
      <div class="demo-pipeline-progress" id="demoPipelineProgress">
        <div class="demo-pipe-step active" title="1. Detection"></div>
        <div class="demo-pipe-step" title="2. Map Fly & Radius"></div>
        <div class="demo-pipe-step" title="3. AI Classification"></div>
        <div class="demo-pipe-step" title="4. Risk Priority"></div>
        <div class="demo-pipe-step" title="5. Response Dispatch"></div>
        <div class="demo-pipe-step" title="6. Case Logging"></div>
      </div>
      <div class="demo-step-content" id="demoStepContent">
        <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);padding:8px 0;">
          Initializing live intelligence pipeline...
        </div>
      </div>
    `;
  }

  function updatePipelineProgress(stepIndex) {
    const steps = document.querySelectorAll('#demoPipelineProgress .demo-pipe-step');
    steps.forEach((step, idx) => {
      step.classList.remove('active', 'completed');
      if (idx < stepIndex) {
        step.classList.add('completed');
      } else if (idx === stepIndex) {
        step.classList.add('active');
      }
    });
  }

  function resetSimulationState() {
    clearAllTimers();
    isRunning = false;

    // Remove risk radius circle
    if (demoRadiusCircle && window.map) {
      window.map.removeLayer(demoRadiusCircle);
      demoRadiusCircle = null;
    }

    // Remove pulse class from SVG layer
    if (activePulsingElement) {
      activePulsingElement.classList.remove('h3-pulse-active');
      activePulsingElement = null;
    }

    // Re-enable Run button & hide reset button
    const runBtn = document.getElementById('runDemoBtn');
    const resetBtn = document.getElementById('resetDemoBtn');
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.innerHTML = '<span class="demo-btn-icon">▶</span> Run Live Simulation';
    }
    if (resetBtn) {
      resetBtn.style.display = 'none';
    }

    // Hide console
    const consoleEl = document.getElementById('demoConsole');
    if (consoleEl) {
      consoleEl.style.display = 'none';
      consoleEl.innerHTML = '';
    }
  }

  async function runSimulation() {
    if (isRunning) return;
    isRunning = true;

    const runBtn = document.getElementById('runDemoBtn');
    const resetBtn = document.getElementById('resetDemoBtn');
    if (runBtn) {
      runBtn.disabled = true;
      runBtn.innerHTML = '<span class="demo-btn-icon">⏳</span> Simulation Running...';
    }
    if (resetBtn) {
      resetBtn.style.display = 'inline-flex';
    }

    // Close default site panel if open to prevent visual clutter
    const sitePanel = document.getElementById('panel');
    if (sitePanel) {
      sitePanel.style.display = 'none';
    }

    try {
      const incident = await getTargetIncident();
      if (!incident) {
        alert('No persistent risk sites available in the database to simulate.');
        resetSimulationState();
        return;
      }

      console.log('[AgniNetra Simulation] Selected highest risk site from DB:', incident.h3_cell, incident);

      renderConsoleShell(incident);
      const content = document.getElementById('demoStepContent');

      // ─────────────────────────────────────────────────────────────
      // STAGE 1: INCIDENT DETECTED
      // ─────────────────────────────────────────────────────────────
      updatePipelineProgress(0);
      content.innerHTML = `
        <div class="demo-banner danger">
          <div class="demo-banner-headline" style="color:var(--status-danger);">
            <span>⚡ Incident Detected</span>
            <span style="font-family:var(--font-mono);font-size:10px;">STAGE 1/6</span>
          </div>
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:6px;">
            Satellite thermal anomaly flagged by VIIRS sensor stream.
          </div>
        </div>
        <div class="demo-card-field">
          <span class="label">Real Case ID:</span>
          <span class="val" title="H3 Cell Index">${incident.h3_cell}</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Location:</span>
          <span class="val">${incident.location_name || 'Sector Coordinate'}</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Coordinates:</span>
          <span class="val">${incident.latitude.toFixed(4)}°N, ${incident.longitude.toFixed(4)}°E</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Observation History:</span>
          <span class="val">${incident.detection_count} detections · ${incident.active_days} active days</span>
        </div>
      `;

      await wait(2000);

      // ─────────────────────────────────────────────────────────────
      // STAGE 2: MAP VISUALIZATION & RISK RADIUS
      // ─────────────────────────────────────────────────────────────
      updatePipelineProgress(1);

      // Pan/Fly to coordinates on the Leaflet map
      if (window.map) {
        window.map.flyTo([incident.latitude, incident.longitude], 12, {
          duration: 1.5
        });
      }

      // Pulse H3 polygon using CSS animation on fill-opacity
      if (window.h3Layers && window.h3Layers.length > 0) {
        const polyLayer = window.h3Layers.find(
          layer => layer._agninetraSite?.h3_cell === incident.h3_cell
        );
        if (polyLayer && polyLayer.getElement) {
          const el = polyLayer.getElement();
          if (el) {
            el.classList.add('h3-pulse-active');
            activePulsingElement = el;
          }
        }
      }

      // Draw real risk radius circle sized by actual risk_score (500m + risk_score * 20m)
      const radiusMeters = Math.round(500 + (Number(incident.risk_score) || 50) * 20);
      if (demoRadiusCircle && window.map) {
        window.map.removeLayer(demoRadiusCircle);
      }
      if (window.map) {
        demoRadiusCircle = L.circle([incident.latitude, incident.longitude], {
          radius: radiusMeters,
          color: '#8B3A2B',
          fillColor: '#8B3A2B',
          fillOpacity: 0.18,
          weight: 2,
          dashArray: '5, 5'
        }).addTo(window.map);

        demoRadiusCircle.bindTooltip(
          `<strong>Simulated Risk Perimeter</strong><br>Radius: ${radiusMeters}m (Risk Score: ${incident.risk_score})`,
          { sticky: true }
        );
      }

      content.innerHTML = `
        <div class="demo-banner warning">
          <div class="demo-banner-headline" style="color:var(--status-warning);">
            <span>🗺 Geospatial Vector & Perimeter</span>
            <span style="font-family:var(--font-mono);font-size:10px;">STAGE 2/6</span>
          </div>
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:6px;">
            Target centered. H3 cell pulsing; dynamic risk radius generated.
          </div>
        </div>
        <div class="demo-card-field">
          <span class="label">Target Site:</span>
          <span class="val">${incident.h3_cell}</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Risk Perimeter Radius:</span>
          <span class="val">${radiusMeters.toLocaleString()} m</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Radius Computation:</span>
          <span class="val">500m + (score × 20m)</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Peak FRP Output:</span>
          <span class="val">${incident.max_frp} MW</span>
        </div>
      `;

      await wait(2200);

      // ─────────────────────────────────────────────────────────────
      // STAGE 3: PROCESSING / AI EVIDENCE CLASSIFICATION
      // ─────────────────────────────────────────────────────────────
      updatePipelineProgress(2);
      content.innerHTML = `
        <div class="demo-banner">
          <div class="demo-banner-headline" style="color:var(--text-primary);">
            <span>⚙ Analyzing Evidence Features...</span>
            <span style="font-family:var(--font-mono);font-size:10px;">STAGE 3/6</span>
          </div>
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:6px;">
            Evaluating 25 multi-spectral and context features via XGBoost model...
          </div>
        </div>
        <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);text-align:center;padding:12px 0;">
          [ Processing Nightfire · Sentinel-5P NO2 · Land Cover · FRP ]
        </div>
      `;

      await wait(1400);

      content.innerHTML = `
        <div class="demo-banner">
          <div class="demo-banner-headline" style="color:var(--text-primary);">
            <span>✓ Evidence Classification Complete</span>
            <span style="font-family:var(--font-mono);font-size:10px;">STAGE 3/6</span>
          </div>
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:6px;">
            Features processed against trained multi-source evidence model.
          </div>
        </div>
        <div class="demo-card-field">
          <span class="label">Model Classification:</span>
          <span class="val" style="color:var(--primary);font-weight:700;">Probable ${incident.ml_classification}</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Model Confidence:</span>
          <span class="val">${(incident.ml_confidence * 100).toFixed(1)}%</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Risk Score:</span>
          <span class="val">${incident.risk_score} / 100</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Nightfire Corroboration:</span>
          <span class="val">${incident.nightfire_match ? 'Matched (' + incident.nightfire_matches + ' detections)' : 'None'}</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Sentinel-5P NO2 Mean:</span>
          <span class="val">${incident.no2_mean ? incident.no2_mean.toExponential(2) : 'N/A'}</span>
        </div>
      `;

      await wait(2200);

      // ─────────────────────────────────────────────────────────────
      // STAGE 4: RISK & PRIORITY ASSESSMENT
      // ─────────────────────────────────────────────────────────────
      updatePipelineProgress(3);
      const priorityClass = (incident.priority || 'MEDIUM').toLowerCase();
      const priorityColor = getPriorityColor(incident.priority);

      content.innerHTML = `
        <div class="demo-banner ${priorityClass === 'high' ? 'danger' : priorityClass === 'medium' ? 'warning' : 'success'}">
          <div class="demo-banner-headline" style="color:${priorityColor};">
            <span>Priority Assessment: ${incident.priority}</span>
            <span style="font-family:var(--font-mono);font-size:10px;">STAGE 4/6</span>
          </div>
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:6px;">
            Site ranked by composite persistence, FRP peak, and context risk.
          </div>
        </div>
        <div class="demo-card-field">
          <span class="label">Real Priority Tier:</span>
          <span class="val" style="color:${priorityColor};">${incident.priority} PRIORITY</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Persistence Index:</span>
          <span class="val">${incident.persistence_score}</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Observation Window:</span>
          <span class="val">${incident.first_detection} → ${incident.last_detection}</span>
        </div>
      `;

      await wait(2000);

      // ─────────────────────────────────────────────────────────────
      // STAGE 5: RESPONSE CARD
      // ─────────────────────────────────────────────────────────────
      updatePipelineProgress(4);
      content.innerHTML = `
        <div class="demo-banner warning">
          <div class="demo-banner-headline" style="color:var(--status-warning);">
            <span>🚨 Response Unit Dispatched</span>
            <span style="font-family:var(--font-mono);font-size:10px;">STAGE 5/6</span>
          </div>
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:6px;">
            Automated alert packet transmitted to regional ground patrol.
          </div>
        </div>
        <div class="demo-card-field">
          <span class="label">Assigned Unit:</span>
          <span class="val">Patrol Squad #${incident.h3_cell.slice(-4).toUpperCase()}</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Target Coordinates:</span>
          <span class="val">${incident.latitude.toFixed(3)}°N, ${incident.longitude.toFixed(3)}°E</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Estimated Arrival:</span>
          <span class="val" style="color:var(--status-warning);font-weight:700;">ETA: 04:32 (simulated dispatch)</span>
        </div>
        <div class="demo-disclaimer">
          * ETA: 04:32 is illustrative (simulated dispatch). No live GPS telematics stream is connected to patrol vehicles.
        </div>
      `;

      await wait(2400);

      // ─────────────────────────────────────────────────────────────
      // STAGE 6: RESOLUTION & AUDIT LOGGING
      // ─────────────────────────────────────────────────────────────
      updatePipelineProgress(5);
      content.innerHTML = `
        <div class="demo-banner success">
          <div class="demo-banner-headline" style="color:var(--status-success);">
            <span>📋 Incident Logged in System</span>
            <span style="font-family:var(--font-mono);font-size:10px;">STAGE 6/6</span>
          </div>
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:6px;">
            Case #${incident.h3_cell} logged for investigation.
          </div>
        </div>
        <div class="demo-card-field">
          <span class="label">Case Record:</span>
          <span class="val">Case #${incident.h3_cell}</span>
        </div>
        <div class="demo-card-field">
          <span class="label">Status:</span>
          <span class="val" style="color:var(--status-success);">Logged for Investigation</span>
        </div>
        <div class="demo-disclaimer" style="margin-bottom:10px;">
          Note: System records forensic telemetry for ongoing investigation. Case resolution is not claimed without ground inspection.
        </div>
        <div class="demo-actions">
          <a class="demo-action-btn demo-action-primary" href="/dashboard/dossier?h3=${encodeURIComponent(incident.h3_cell)}" target="_blank">
            View Case Dossier
          </a>
          <button class="demo-action-btn demo-action-secondary" id="demoEndResetBtn" type="button">
            Reset Demo
          </button>
        </div>
      `;

      // Attach reset button event inside the final resolution card
      const endResetBtn = document.getElementById('demoEndResetBtn');
      if (endResetBtn) {
        endResetBtn.addEventListener('click', resetSimulationState);
      }

      // Re-enable Run button
      if (runBtn) {
        runBtn.disabled = false;
        runBtn.innerHTML = '<span class="demo-btn-icon">▶</span> Re-Run Simulation';
      }

    } catch (err) {
      if (err && err.message === 'Simulation cancelled') {
        // Handled gracefully on reset
        return;
      }
      console.error('[AgniNetra Simulation] Error running demo:', err);
      resetSimulationState();
    }
  }

  function initDemo() {
    const runBtn = document.getElementById('runDemoBtn');
    const resetBtn = document.getElementById('resetDemoBtn');

    if (runBtn) {
      runBtn.addEventListener('click', () => {
        runSimulation();
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        resetSimulationState();
      });
    }
  }

  // Initialize once DOM is loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDemo);
  } else {
    initDemo();
  }
})();
