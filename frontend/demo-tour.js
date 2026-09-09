(() => {
  const demoUrl = "883c591b13fffff";
  const stepDuration = 2800;
  const progressMessages = [
    "Checking thermal persistence",
    "Checking multi-source evidence",
    "Checking model confidence",
    "Identifying investigation opportunities",
    "Preparing the site dossier",
  ];

  const steps = [
    {
      target: "#overviewStats",
      title: "Let's take a quick tour",
      description: "See how AgniNetra turns satellite observations into a clear investigation workflow.",
      duration: 2400,
    },
    {
      target: "#searchInput",
      title: "Start with a site",
      description: "Search for a place or H3 case ID to begin an investigation.",
      duration: 3000,
      action: () => {
        const input = document.querySelector("#searchInput");
        if (input) {
          input.value = demoUrl;
          input.dispatchEvent(new Event("input", { bubbles: true }));
        }
      },
    },
    {
      target: "#searchBtn",
      title: "Run the investigation",
      description: "AgniNetra checks persistence, thermal intensity, independent evidence, and model confidence in one flow.",
      duration: 3600,
      action: () => {
        const button = document.querySelector("#searchBtn");
        if (button) button.click();
      },
      progress: true,
    },
    {
      target: "#overviewStats",
      title: "National overview",
      description: "The overview turns the full dataset into a fast read of persistent, industrial, medium-risk, and high-risk sites.",
      duration: 3000,
    },
    {
      target: "#total",
      title: "Persistent thermal activity",
      description: "Persistence shows where thermal activity repeats over time instead of appearing as a single isolated detection.",
      duration: 2600,
    },
    {
      target: "#map",
      title: "See the evidence geographically",
      description: "The map places classified H3 cells in context so teams can move from a national view to a specific location.",
      duration: 3000,
    },
    {
      target: () => document.querySelector(".site.high, .site.medium, .site.low"),
      title: "Prioritized investigation sites",
      description: "We do not just identify signals. Each site is ranked so the highest-priority investigation is easy to find.",
      duration: 3000,
    },
    {
      target: () => document.querySelector(".site.high .site-btn, .site.medium .site-btn, .site.low .site-btn"),
      title: "Open the recommendation",
      description: "Every prioritized site has a direct next action: open its investigation dossier and inspect the supporting evidence.",
      duration: 3000,
    },
    {
      target: "#list",
      title: "Quick wins for investigators",
      description: "Start with the highest-priority cases in the list to turn a large satellite dataset into a focused work queue.",
      duration: 2800,
    },
    {
      target: "#panel",
      title: "From signal to dossier",
      description: "This investigation preview brings the site score, model confidence, evidence sources, and report action together.",
      duration: 3200,
      action: () => {
        const site = document.querySelector(".site.high, .site.medium, .site.low");
        if (site) site.click();
      },
    },
    {
      target: () => document.querySelector(".site.high .site-btn, .site.medium .site-btn, .site.low .site-btn"),
      title: "Ready to investigate?",
      description: "Open the full dossier when you are ready to review the evidence and download the investigation record.",
      duration: 3000,
    },
  ];

  let currentStep = 0;
  let timer = null;
  let paused = false;
  let demoState = null;
  let progressTimer = null;
  let activeTarget = null;
  let spotlightFrame = null;

  function targetFor(step) {
    if (!step.target) return null;
    const target = typeof step.target === "function" ? step.target() : document.querySelector(step.target);
    if (!target || !target.isConnected || target.getClientRects().length === 0) return null;
    return target;
  }

  function buildTour() {
    const tour = document.createElement("div");
    tour.className = "demo-tour";
    tour.hidden = true;
    tour.setAttribute("aria-live", "polite");
    tour.innerHTML = `
      <div class="demo-tour__shade"></div>
      <div class="demo-tour__spotlight" aria-hidden="true"></div>
      <section class="demo-tour__intro" role="dialog" aria-modal="true" aria-label="AgniNetra demo introduction">
        <div class="eyebrow">GUIDED DEMO</div>
        <h2>Let's take a quick tour</h2>
        <p>See how AgniNetra turns satellite signals into an investigation workflow in under a minute.</p>
      </section>
      <section class="demo-tour__card" role="dialog" aria-modal="true" aria-label="AgniNetra guided demo">
        <div class="demo-tour__eyebrow"><span id="demoTourStep"></span><span id="demoTourState">AUTO-PLAY</span></div>
        <h2 class="demo-tour__title" id="demoTourTitle"></h2>
        <p class="demo-tour__description" id="demoTourDescription"></p>
        <div class="demo-tour__progress"><div class="demo-tour__progress-bar" id="demoTourProgressBar"></div></div>
        <div class="demo-tour__actions">
          <div class="demo-tour__status" id="demoTourStatus"></div>
          <div class="demo-tour__controls">
            <button type="button" class="demo-tour__button" id="demoTourPause">Pause</button>
            <button type="button" class="demo-tour__button" id="demoTourSkip">Skip</button>
            <button type="button" class="demo-tour__button demo-tour__button--primary" id="demoTourExit">Exit Demo</button>
          </div>
        </div>
      </section>
    `;
    document.body.appendChild(tour);
    return tour;
  }

  const tour = buildTour();
  const spotlight = tour.querySelector(".demo-tour__spotlight");
  const intro = tour.querySelector(".demo-tour__intro");
  const card = tour.querySelector(".demo-tour__card");
  const stepLabel = tour.querySelector("#demoTourStep");
  const stateLabel = tour.querySelector("#demoTourState");
  const title = tour.querySelector("#demoTourTitle");
  const description = tour.querySelector("#demoTourDescription");
  const status = tour.querySelector("#demoTourStatus");
  const progressBar = tour.querySelector("#demoTourProgressBar");
  const pauseButton = tour.querySelector("#demoTourPause");

  function positionSpotlight(target, shouldScroll = true) {
    activeTarget = target;
    if (!target) {
      tour.classList.remove("is-targeted");
      tour.querySelector(".demo-tour__shade").style.clipPath = "polygon(0 0, 100% 0, 100% 100%, 0 100%)";
      card.classList.remove("is-repositioned");
      return;
    }
    if (shouldScroll) target.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
    window.setTimeout(() => {
      if (activeTarget !== target || tour.hidden) return;
      const rect = target.getBoundingClientRect();
      const padding = 7;
      const top = Math.max(8, rect.top - padding);
      const left = Math.max(8, rect.left - padding);
      const right = Math.min(window.innerWidth - 8, rect.right + padding);
      const bottom = Math.min(window.innerHeight - 8, rect.bottom + padding);
      spotlight.style.top = `${top}px`;
      spotlight.style.left = `${left}px`;
      spotlight.style.width = `${Math.max(0, right - left)}px`;
      spotlight.style.height = `${Math.max(0, bottom - top)}px`;
      tour.querySelector(".demo-tour__shade").style.clipPath = `polygon(0 0, 100% 0, 100% 100%, 0 100%, 0 ${bottom}px, ${left}px ${bottom}px, ${left}px ${top}px, ${right}px ${top}px, ${right}px ${bottom}px, 0 ${bottom}px)`;
      positionCard(rect);
      tour.classList.add("is-targeted");
    }, 80);
  }

  function positionCard(targetRect) {
    const cardHeight = card.getBoundingClientRect().height;
    const lowerEdge = window.innerHeight - 30;
    const overlapsBottomCard = targetRect.bottom > lowerEdge - cardHeight && targetRect.top < lowerEdge;
    if (overlapsBottomCard && targetRect.top > cardHeight + 24) {
      card.style.setProperty("--demo-card-top", "24px");
      card.classList.add("is-repositioned");
      return;
    }
    card.classList.remove("is-repositioned");
    card.style.removeProperty("--demo-card-top");
  }

  function refreshSpotlight() {
    if (!activeTarget || tour.hidden) return;
    if (spotlightFrame) return;
    spotlightFrame = window.requestAnimationFrame(() => {
      spotlightFrame = null;
      const rect = activeTarget.getBoundingClientRect();
      positionSpotlight(activeTarget, false);
      if (rect.width === 0 || rect.height === 0) tour.classList.remove("is-targeted");
    });
  }

  function setProgressMessage() {
    let messageIndex = 0;
    status.textContent = progressMessages[messageIndex];
    window.clearInterval(progressTimer);
    progressTimer = window.setInterval(() => {
      messageIndex += 1;
      if (messageIndex >= progressMessages.length) {
        window.clearInterval(progressTimer);
        return;
      }
      status.textContent = `✓ ${progressMessages[messageIndex]}`;
    }, 520);
  }

  function clearTimers() {
    window.clearTimeout(timer);
    window.clearInterval(progressTimer);
    timer = null;
    progressTimer = null;
  }

  function renderStep() {
    clearTimers();
    if (currentStep >= steps.length) {
      exitDemo();
      return;
    }

    const step = steps[currentStep];
    const isIntro = currentStep === 0;
    tour.classList.toggle("is-intro", isIntro);
    tour.classList.toggle("is-targeted", false);
    card.hidden = isIntro;
    intro.hidden = !isIntro;
    stepLabel.textContent = `Demo ${currentStep + 1} / ${steps.length}`;
    stateLabel.textContent = paused ? "PAUSED" : "AUTO-PLAY";
    title.textContent = step.title;
    description.textContent = step.description;
    status.textContent = "";
    progressBar.style.width = `${((currentStep + 1) / steps.length) * 100}%`;
    pauseButton.textContent = paused ? "Resume" : "Pause";

    const target = targetFor(step);
    positionSpotlight(target);
    if (step.progress) setProgressMessage();
    if (typeof step.action === "function") {
      window.setTimeout(() => {
        step.action();
        if (!targetFor(step) && step.target) positionSpotlight(targetFor(step));
      }, 220);
    }

    if (!paused) {
      timer = window.setTimeout(() => {
        currentStep += 1;
        renderStep();
      }, step.duration || stepDuration);
    }
  }

  function snapshotState() {
    const panel = document.querySelector("#panel");
    const searchInput = document.querySelector("#searchInput");
    const filter = document.querySelector("#filter");
    demoState = {
      bodyOverflow: document.body.style.overflow,
      searchValue: searchInput ? searchInput.value : "",
      filterValue: filter ? filter.value : "ALL",
      panelDisplay: panel ? panel.style.display : "",
    };
  }

  function restoreState() {
    if (!demoState) return;
    const searchInput = document.querySelector("#searchInput");
    const filter = document.querySelector("#filter");
    const panel = document.querySelector("#panel");
    if (searchInput) searchInput.value = demoState.searchValue;
    if (filter) {
      filter.value = demoState.filterValue;
      filter.dispatchEvent(new Event("change", { bubbles: true }));
    }
    if (panel) panel.style.display = demoState.panelDisplay;
    document.body.style.overflow = demoState.bodyOverflow;
    demoState = null;
  }

  function startDemo() {
    if (!tour.hidden) return;
    snapshotState();
    currentStep = 0;
    paused = false;
    document.body.style.overflow = "hidden";
    tour.hidden = false;
    window.requestAnimationFrame(() => {
      tour.classList.add("is-active");
      renderStep();
    });
  }

  function pauseDemo() {
    if (paused) {
      paused = false;
      renderStep();
      return;
    }
    paused = true;
    clearTimers();
    stateLabel.textContent = "PAUSED";
    pauseButton.textContent = "Resume";
  }

  function skipStep() {
    currentStep += 1;
    paused = false;
    renderStep();
  }

  function exitDemo() {
    clearTimers();
    paused = false;
    tour.classList.remove("is-active", "is-intro", "is-targeted");
    window.setTimeout(() => {
      tour.hidden = true;
      restoreState();
    }, 220);
  }

  document.querySelector("#demoRunButton").addEventListener("click", startDemo);
  pauseButton.addEventListener("click", pauseDemo);
  tour.querySelector("#demoTourSkip").addEventListener("click", skipStep);
  tour.querySelector("#demoTourExit").addEventListener("click", exitDemo);

  document.addEventListener("pointerdown", event => {
    if (!tour.hidden && !tour.contains(event.target) && !paused) pauseDemo();
  }, true);

  window.addEventListener("resize", () => {
    if (tour.hidden || currentStep === 0) return;
    positionSpotlight(targetFor(steps[currentStep]));
  });

  window.addEventListener("scroll", refreshSpotlight, true);
})();
