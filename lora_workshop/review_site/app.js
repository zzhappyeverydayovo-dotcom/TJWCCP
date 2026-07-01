const stateKey = "tjwccp-lora-review-v1";
let reviewData = null;
let reviewState = JSON.parse(localStorage.getItem(stateKey) || "{}");

const $ = (selector) => document.querySelector(selector);

function saveState() {
  localStorage.setItem(stateKey, JSON.stringify(reviewState));
}

function manualDecision(trialId) {
  return reviewState[trialId]?.decision || "";
}

function championTrialId() {
  return Object.entries(reviewState).find(([, value]) => value.decision === "champion")?.[0] || "";
}

function badgeClass(value) {
  if (value === "approved_for_platform" || value === "internal_preview") return "good";
  if (value === "needs_revision") return "warn";
  if (value === "reject") return "bad";
  return "";
}

function labelDecision(value) {
  return {
    champion: "Champion",
    shortlist: "候选",
    hold: "保留观察",
    reject: "人工淘汰",
  }[value] || "未评审";
}

function renderSummary() {
  $("#runId").textContent = reviewData.run_id;
  $("#trialCount").textContent = reviewData.trials.length;
  $("#runMeta").textContent = `${reviewData.project} · ${reviewData.review_goal} · 生成时间 ${reviewData.generated_at}`;
  const metricBest = reviewData.best_by_metric?.trial_id || reviewData.trials[0]?.trial_id || "-";
  $("#metricBest").textContent = metricBest;
  const champion = championTrialId();
  const championTrial = reviewData.trials.find((trial) => trial.trial_id === champion);
  $("#championName").textContent = championTrial ? `${championTrial.lora_id} ${championTrial.lora_name}` : "未选择";
}

function renderRubric() {
  $("#rubricList").innerHTML = reviewData.review_rubric.map((item) => `<li>${item}</li>`).join("");
}

function trackLabel(key) {
  return {
    style_fidelity: "风格还原",
    cultural_accuracy: "文化准确",
    product_transferability: "产品转化",
    prompt_adherence: "提示遵循",
    artifact_control: "瑕疵控制",
    cost_efficiency: "成本效率",
  }[key] || key;
}

function renderTracks(tracks) {
  return Object.entries(tracks)
    .filter(([key]) => key !== "simulated")
    .map(([key, value]) => {
      const percent = Math.round(Number(value) * 100);
      return `<div class="track"><span>${trackLabel(key)}</span><div class="bar"><i style="width:${percent}%"></i></div><b>${percent}</b></div>`;
    })
    .join("");
}

function renderParams(config) {
  const items = [
    ["底座模型", config.base_model],
    ["数据集", config.dataset_ref],
    ["触发词", config.trigger_token],
    ["LR", config.learning_rate],
    ["Rank/Alpha", `${config.rank}/${config.alpha}`],
    ["Steps", config.steps],
    ["默认权重", config.default_weight],
    ["适用品类", config.product_fit.join("、")],
  ];
  return items.map(([key, value]) => `<div><dt>${key}</dt><dd>${value}</dd></div>`).join("");
}

function filteredTrials() {
  const q = $("#searchInput").value.trim().toLowerCase();
  const decisionFilter = $("#decisionFilter").value;
  const manualFilter = $("#manualFilter").value;
  return reviewData.trials.filter((trial) => {
    const text = `${trial.trial_id} ${trial.lora_id} ${trial.lora_name} ${trial.theme}`.toLowerCase();
    if (q && !text.includes(q)) return false;
    if (decisionFilter && trial.release_decision !== decisionFilter) return false;
    if (manualFilter && manualDecision(trial.trial_id) !== manualFilter) return false;
    return true;
  });
}

function renderTrials() {
  const grid = $("#trialGrid");
  const template = $("#trialCardTemplate");
  grid.innerHTML = "";
  filteredTrials().forEach((trial) => {
    const node = template.content.cloneNode(true);
    const card = node.querySelector(".trial-card");
    const decision = manualDecision(trial.trial_id);
    if (decision === "champion") card.classList.add("champion");
    node.querySelector(".trial-id").textContent = `${trial.trial_id} · ${trial.lora_id}`;
    node.querySelector("h2").textContent = trial.lora_name;
    node.querySelector(".theme").textContent = trial.theme;
    node.querySelector(".score").textContent = trial.score.toFixed(4);
    node.querySelector(".badges").innerHTML = [
      `<span class="badge ${badgeClass(trial.release_decision)}">${trial.release_decision}</span>`,
      `<span class="badge">${labelDecision(decision)}</span>`,
      trial.config_lock.dry_run ? `<span class="badge warn">dry-run</span>` : `<span class="badge good">trained</span>`,
    ].join("");
    node.querySelector(".params").innerHTML = renderParams(trial.config);
    node.querySelector(".tracks").innerHTML = renderTracks(trial.evaluation.tracks);
    const textarea = node.querySelector("textarea");
    textarea.value = reviewState[trial.trial_id]?.note || "";
    textarea.addEventListener("input", () => {
      reviewState[trial.trial_id] = reviewState[trial.trial_id] || {};
      reviewState[trial.trial_id].note = textarea.value;
      saveState();
    });
    node.querySelectorAll("button[data-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const action = button.dataset.action;
        if (action === "champion") {
          Object.keys(reviewState).forEach((id) => {
            if (reviewState[id].decision === "champion") reviewState[id].decision = "shortlist";
          });
        }
        reviewState[trial.trial_id] = reviewState[trial.trial_id] || {};
        reviewState[trial.trial_id].decision = action;
        reviewState[trial.trial_id].updated_at = new Date().toISOString();
        saveState();
        renderSummary();
        renderTrials();
      });
    });
    const link = node.querySelector(".sample-link");
    if (trial.sample_url) {
      link.href = trial.sample_url;
    } else {
      link.remove();
    }
    grid.appendChild(node);
  });
}

function exportReview() {
  const champion = championTrialId();
  const payload = {
    schema_version: "heritage-human-review-export-v1",
    exported_at: new Date().toISOString(),
    run_id: reviewData.run_id,
    champion_trial_id: champion,
    champion: reviewData.trials.find((trial) => trial.trial_id === champion) || null,
    reviews: reviewState,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${reviewData.run_id}_human_review.json`;
  a.click();
  URL.revokeObjectURL(url);
}

async function init() {
  const response = await fetch("review-data.json", { cache: "no-store" });
  reviewData = await response.json();
  renderSummary();
  renderRubric();
  renderTrials();
  ["#searchInput", "#decisionFilter", "#manualFilter"].forEach((selector) => {
    $(selector).addEventListener("input", renderTrials);
  });
  $("#exportReview").addEventListener("click", exportReview);
  $("#resetReview").addEventListener("click", () => {
    reviewState = {};
    saveState();
    renderSummary();
    renderTrials();
  });
}

init().catch((error) => {
  document.body.innerHTML = `<main class="rubric"><h1>评审数据加载失败</h1><p>${error.message}</p><p>请先运行 build_review_site.py 生成 review-data.json。</p></main>`;
});
