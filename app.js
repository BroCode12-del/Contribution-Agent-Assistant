"use strict";
const $ = id => document.getElementById(id);
let selectedReview = "", currentReview = null, sessionToken = "", busy = false;
let activeLearning = null;
function node(tag, text, parent) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (parent) parent.append(element);
  return element;
}
function list(id, rows) { $(id).replaceChildren(); for (const text of rows || []) node("li", text, $(id)); }
function notice(text, error = false) { $("job").textContent = text; $("job").classList.toggle("error", error); }
async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed.");
  return data;
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll("button:not([data-permanent])").forEach(button => { button.disabled = value; });
  $("review-select").disabled = value;
  updateLearningControls();
}
function sourceDetails(parent, evidence) {
  const details = node("details", undefined, parent);
  node("summary", `${evidence.id}: ${evidence.file}, lines ${evidence.line}–${evidence.line_end}`, details);
  node("pre", evidence.code, details);
}
function safeLink(parent, url, text) {
  try {
    const value = new URL(url);
    if (value.protocol !== "https:" || value.hostname !== "github.com") return;
    const link = node("a", text || url, parent);
    link.href = value.href; link.target = "_blank"; link.rel = "noopener noreferrer";
  } catch { /* Untrusted source URLs are not turned into links. */ }
}
async function loadReviews(preferred) {
  const data = await api("/api/reviews");
  $("review-select").replaceChildren();
  for (const review of data.reviews) {
    const option = node("option", `${review.repository} · ${review.review_id.slice(0, 8)}`, $("review-select"));
    option.value = review.review_id;
  }
  selectedReview = data.reviews.some(row => row.review_id === preferred) ? preferred : data.default_review_id;
  $("review-select").value = selectedReview;
  await loadReview();
}
async function loadReview() {
  const data = await api(`/api/review?review_id=${encodeURIComponent(selectedReview)}`);
  currentReview = data;
  $("review-meta").textContent = `${data.repository} · Commit ${data.commit_sha} · Review ${data.review_id}`;
  $("analysis-state").textContent = data.analysis ? "Saved Nightshift analysis · static code only · claims still require human review" : "No saved AI analysis yet. The collector's raw records are shown below; they are not AI skill assessments.";
  $("observations").replaceChildren();
  const evidence = data.evidence || [];
  for (const observation of data.analysis?.observations || []) {
    const card = node("article", undefined, $("observations"));
    node("p", observation.statement, card);
    node("small", `Evidence: ${observation.evidence_ids.join(", ")}`, card);
    for (const id of observation.evidence_ids) {
      const record = evidence.find(item => item.id === id);
      if (record) sourceDetails(card, record);
    }
  }
  if (!data.analysis) for (const record of evidence) sourceDetails($("observations"), record);
  if (!evidence.length) node("p", "No supported pandas.read_csv calls were found. This collector does not identify every ability in a repository.", $("observations"));
  const c = data.coverage;
  $("coverage").textContent = `${evidence.length} evidence records. All downloaded Python files parsed: ${c.all_python_files_parsed}. Skipped: ${(c.skipped_files || []).length}; excluded: ${(c.excluded_files || []).length}; download failures: ${(c.download_failures || []).length}. ${c.coverage_note || "Coverage is limited to downloaded Python files."}`;
  list("limitations", data.analysis?.limitations || ["Static code does not establish execution, authorship, correctness, or mastery."]);
  renderRanking(data.ranking);
  await loadLearning();
}
function renderRanking(ranking) {
  $("candidates").replaceChildren();
  $("ranking-state").textContent = ranking ? `Saved checks: ${ranking.status_checked_at} · ${ranking.status}. Ordering is for human investigation.` : "No opportunity search saved for this review yet.";
  for (const candidate of ranking?.candidates || []) {
    const card = node("article", undefined, $("candidates"));
    node("h3", `${candidate.review_priority}. ${candidate.title}`, card);
    safeLink(card, candidate.url, candidate.candidate_id);
    node("p", `Status: ${candidate.availability} · Assessment: ${candidate.assessment_status}`, card);
    node("small", candidate.reason, card);
    if (candidate.blockers?.length) node("p", `Hold reasons: ${candidate.blockers.join(", ")}`, card);
    if (candidate.assessment_error) node("p", `Assessment unavailable: ${candidate.assessment_error.detail || candidate.assessment_error.type}. No AI fit is claimed.`, card);
    const assessment = candidate.assessment;
    if (candidate.application_cache?.reused) node("small", "Reused an exact-input validated record or retained exhausted failure; no new AI request. Fresh issue checks are shown above.", card);
    if (assessment) {
      node("p", assessment.fit?.length ? "Limited evidence overlap recorded; review the requirements and gaps." : "No implementation fit established yet. A related practice task is available.", card);
      const detail = node("details", undefined, card);
      node("summary", "Inspect requirements, evidence and gaps", detail);
      node("h3", "Requirements", detail);
      for (const requirement of assessment.requirements || []) {
        node("p", requirement.statement, detail); node("blockquote", requirement.source_quote, detail);
      }
      node("h3", "Fit supported by supplied evidence", detail);
      if (!assessment.fit?.length) node("p", "No supported fit was established.", detail);
      for (const fit of assessment.fit || []) node("p", `${fit.statement} (${fit.evidence_ids.join(", ")})`, detail);
      node("h3", "Gaps in the evidence", detail);
      const gaps = node("ul", undefined, detail);
      for (const gap of assessment.gaps || []) node("li", gap, gaps);
      if (candidate.group !== "held" && candidate.availability === "needs_review") {
        const practiceButton = node("button", "Start connected practice", card);
        practiceButton.disabled = busy;
        practiceButton.addEventListener("click", () => runAction({action:"start_learning", review_id:selectedReview, discovery_id:ranking.discovery_id, run_id:ranking.run_id, candidate_id:candidate.candidate_id}));
      }
    }
    if (candidate.group === "held") {
      node("small", candidate.assessment_status === "held" ? "Held before AI assessment because of the recorded blockers. No assessment request was sent." : "This saved issue is held. Refresh status checks before considering it again.", card);
    } else if (candidate.assessment_status === "assessed") {
      node("small", "Assessment saved and structure checked. Review the quoted requirements and interpretation before choosing work.", card);
    } else if ((candidate.attempt_count || 0) >= 2) {
      node("small", "The two-attempt limit has been reached. No further request is available for this candidate in this run.", card);
    } else {
      const button = node("button", "Request / retry this assessment", card);
      button.className = "secondary"; button.disabled = busy;
      button.addEventListener("click", () => runAction({action:"assess", review_id:selectedReview, discovery_id:ranking.discovery_id, run_id:ranking.run_id, candidate_id:candidate.candidate_id}));
      node("small", "Nightshift · maximum two attempts per candidate per run. Checks older than 24 hours require a new search.", card);
    }
  }
}
function renderChecks(id, result) {
  const parent = $(id); parent.replaceChildren();
  if (!result) { node("p", "No saved results.", parent); return; }
  node("p", `Origin: ${result.submission_origin || "unverified"}`, parent);
  node("p", `Independent ability established: ${result.independent_ability_established === true ? "yes" : "no"}`, parent);
  const checks = node("ul", undefined, parent);
  for (const check of result.checks || []) node("li", `${check.passed ? "PASS" : "FAIL"} · ${check.name}`, checks).className = check.passed ? "check-pass" : "check-fail";
  if (result.error) node("p", `Error: ${result.error.type} · ${result.error.message}`, parent);
}
async function loadDemo() {
  const data = await api("/api/demo");
  const opportunity = data.opportunity || {};
  $("demo-opportunity").replaceChildren();
  node("span", `${opportunity.summary || "O1"} · Saved status: ${opportunity.availability} · Checked ${opportunity.checked_on}. `, $("demo-opportunity"));
  safeLink($("demo-opportunity"), opportunity.url, "Inspect original issue");
  const practice = data.practice || {};
  $("practice-title").textContent = practice.title || "No saved practice";
  $("practice-instructions").textContent = (practice.instructions || "").replaceAll("\\n", "\n");
  $("practice-input").textContent = practice.input_csv || "";
  list("practice-criteria", practice.success_criteria);
  $("practice-scope").textContent = practice.scope_note || "";
  renderChecks("practice-results", data.results); renderChecks("followup-results", data.followup_results);
  $("feedback-summary").textContent = data.feedback?.explanation?.summary || "No saved feedback.";
  list("feedback-limits", data.feedback?.explanation?.limitations);
  $("followup-task").textContent = data.followup ? JSON.stringify(data.followup, null, 2) : "No follow-up saved.";
  const decision = data.state?.latest_decision;
  $("agent-decision").replaceChildren();
  if (decision) {
    node("h3", decision.next_action.replaceAll("_", " "), $("agent-decision"));
    node("p", decision.reason, $("agent-decision"));
    node("p", `Opportunity: ${decision.opportunity_decision} · Attempts: ${decision.attempts_used}/${decision.max_attempts}`, $("agent-decision"));
    node("small", "Saved decision snapshot; refreshing this page does not rerun the agent or consume an attempt.", $("agent-decision"));
  }
  $("draft").textContent = data.outreach?.draft || "No private draft saved.";
  list("draft-notes", data.outreach?.review_notes);
}

function updateLearningControls() {
  const exhausted = !activeLearning || activeLearning.attempts.length >= activeLearning.max_attempts;
  for (const id of ["learning-submit", "learning-wrong", "learning-correct"]) $(id).disabled = busy || exhausted;
  $("learning-sync").disabled = busy || !activeLearning;
  $("learning-select").disabled = busy;
}

async function loadLearning(flowId) {
  let url = `/api/learning?review_id=${encodeURIComponent(selectedReview)}`;
  if (flowId) url += `&flow_id=${encodeURIComponent(flowId)}`;
  const data = await api(url);
  activeLearning = data.flow;
  $("learning-empty").hidden = !!data.flow;
  $("learning-content").hidden = !data.flow;
  $("learning-select").replaceChildren();
  for (const item of data.flows) {
    const option = node("option", `${item.candidate_id} · ${item.flow_id.slice(0,8)}`, $("learning-select"));
    option.value = item.flow_id;
  }
  if (!data.flow) { updateLearningControls(); return; }
  const flow = data.flow;
  $("learning-select").value = flow.flow_id;
  $("learning-binding").textContent = `${flow.candidate_id} · Review ${flow.review_id} · Flow ${flow.flow_id} · Status checked ${flow.availability_checked_at}`;
  const practice = flow.active_task;
  $("learning-title").textContent = `${practice.sequence === 2 ? "Follow-up: " : ""}${practice.title}`;
  $("learning-instructions").textContent = practice.instructions;
  $("learning-csv").textContent = practice.input_csv;
  list("learning-criteria", practice.success_criteria);
  $("learning-scope").textContent = practice.scope_note;
  $("learning-budget").textContent = `${flow.attempts.length}/${flow.max_attempts} attempts used. Reference examples count. Reopening this flow does not reset its budget.`;
  $("learning-attempts").replaceChildren();
  for (const [index, attempt] of flow.attempts.entries()) {
    const card = node("article", undefined, $("learning-attempts"));
    node("h3", `Attempt ${index+1} · ${attempt.results.all_passed ? "Output passed" : "Revise output"}`, card);
    node("small", `${attempt.practice_id} · Assistance: ${attempt.submission_origin}`, card);
    node("p", attempt.feedback, card);
    const checks = node("ul", undefined, card);
    for (const check of attempt.results.checks) node("li", `${check.passed ? "PASS" : "FAIL"} · ${check.name}`, checks).className = check.passed ? "check-pass" : "check-fail";
    node("small", attempt.results.measurement + " Independent ability established: no.", card);
  }
  $("learning-next").replaceChildren();
  node("p", `Before practice: ${flow.initial_recommendation.next_action.replaceAll("_"," ")}`, $("learning-next"));
  node("h3", flow.recommendation.next_action.replaceAll("_"," "), $("learning-next"));
  node("p", flow.recommendation.reason, $("learning-next"));
  node("p", `Opportunity decision: ${flow.recommendation.opportunity_decision}. This is not implementation approval.`, $("learning-next"));
  $("learning-followup").textContent = flow.followup_reason || "";
  $("learning-memory").replaceChildren();
  node("p", `Saved memory status: ${flow.memory.status}${flow.memory.checked_at ? " · " + flow.memory.checked_at : ""}`, $("learning-memory"));
  if (flow.without_memory_recommendation) node("p", `Without recalled history: ${flow.without_memory_recommendation.next_action.replaceAll("_"," ")}`, $("learning-memory"));
  for (const item of flow.memory.memories || []) node("small", `${item.id} · ${item.origin} · ${item.source}`, $("learning-memory"));
  $("learning-zetaris").textContent = `Saved Zetaris check: ${flow.zetaris.status}${flow.zetaris.checked_at ? " · " + flow.zetaris.checked_at : ""} · ${flow.zetaris.note || "Query pending."}`;
  $("learning-joined").textContent = JSON.stringify(flow.zetaris.records || [], null, 2);
  $("learning-draft").textContent = flow.outreach?.draft || "A private draft will be prepared after the first measured attempt. Nothing is sent.";
  list("learning-disclosures", flow.outreach?.review_notes);
  updateLearningControls();
}
async function runAction(payload) {
  if (busy) return;
  setBusy(true); notice("Starting… Keep this page open. Saved results remain available.");
  try {
    const {job_id} = await api("/api/actions", {method:"POST", headers:{"Content-Type":"application/json", "X-Session-Token":sessionToken}, body:JSON.stringify(payload)});
    sessionStorage.setItem("contribution-job", job_id);
    await watchJob(job_id);
  } catch (error) { notice(error.message, true); }
  finally { setBusy(false); }
}
async function watchJob(id) {
  while (true) {
    const job = await api(`/api/jobs/${id}`);
    notice(job.message, job.status === "failed");
    if (job.status !== "running") {
      sessionStorage.removeItem("contribution-job");
      if (job.result?.review_id) await loadReviews(job.result.review_id);
      if (job.result?.flow_id) {
        await loadLearning(job.result.flow_id);
        $("learning-answer").value = "";
        $("learning").scrollIntoView({behavior:"smooth"});
      }
      if (job.result?.comparison) {
        const comparison = job.result.comparison;
        $("memory-result").replaceChildren();
        const box = node("article", undefined, $("memory-result"));
        node("p", `Without memory: ${comparison.without_memory.next_action}`, box);
        node("p", `With memory: ${comparison.with_memory.next_action}`, box);
        node("p", comparison.with_memory.reason, box);
        node("small", `Retrieved memory IDs: ${comparison.with_memory.memory_ids.join(", ")}`, box);
      }
      if (job.action === "zetaris") $("zetaris-result").textContent = job.message;
      return;
    }
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
}
async function boot() {
  document.querySelector("#outreach button").dataset.permanent = "true";
  try {
    sessionToken = (await api("/api/session")).token;
    await Promise.all([loadReviews(), loadDemo()]);
    notice("Saved results loaded. Live requests run only when you choose an action.");
    const pending = sessionStorage.getItem("contribution-job");
    if (pending) {
      setBusy(true);
      try { await watchJob(pending); } catch (error) { sessionStorage.removeItem("contribution-job"); notice(error.message, true); }
      finally { setBusy(false); }
    }
  } catch (error) { notice(`Could not load the app: ${error.message} Start python api_server.py and use http://127.0.0.1:8000/.`, true); }
}
$("repository-form").addEventListener("submit", event => {event.preventDefault(); runAction({action:"fetch", url:$("repository-url").value.trim()});});
$("review-select").addEventListener("change", async () => { selectedReview = $("review-select").value; try { await loadReview(); } catch(error) { notice(error.message, true); } });
$("reload").addEventListener("click", async () => { try { await Promise.all([loadReviews(selectedReview), loadDemo()]); notice("Saved results refreshed."); } catch(error) { notice(error.message, true); } });
$("analyse").addEventListener("click", () => runAction({action:"analyse", review_id:selectedReview}));
$("discover").addEventListener("click", () => runAction({action:"discover", review_id:selectedReview}));
$("memory").addEventListener("click", () => runAction({action:"memory"}));
$("zetaris").addEventListener("click", () => runAction({action:"zetaris"}));
$("learning-select").addEventListener("change", () => loadLearning($("learning-select").value).catch(error=>notice(error.message,true)));
$("learning-form").addEventListener("submit", event => {
  event.preventDefault();
  if (!activeLearning) return;
  try {
    const answer = JSON.parse($("learning-answer").value);
    runAction({action:"submit_learning",flow_id:activeLearning.flow_id,answer,origin:$("learning-origin").value});
  } catch { notice("Enter valid JSON records before submitting. No attempt was consumed.",true); }
});
$("learning-wrong").addEventListener("click",()=>activeLearning && runAction({action:"reference_learning",flow_id:activeLearning.flow_id,example:"incorrect_reference"}));
$("learning-correct").addEventListener("click",()=>activeLearning && runAction({action:"reference_learning",flow_id:activeLearning.flow_id,example:"correct_reference"}));
$("learning-sync").addEventListener("click",()=>activeLearning && runAction({action:"sync_learning",flow_id:activeLearning.flow_id}));
boot();
