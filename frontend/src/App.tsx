import { FormEvent, useEffect, useState } from "react";

import { AnalyzeResponse, DpaAnalyzeResponse, DpaChecklistItem, analyzeDpaUrl, analyzeUrl } from "./api";

type AnalysisType = "terms" | "dpa";
type AnalysisResult = AnalyzeResponse | DpaAnalyzeResponse;

const CONTEXT_PRESETS = [
  {
    label: "B2B SaaS",
    value:
      "B2B SaaS platform handling customer and employee data. Focus on liability caps, data use, confidentiality, indemnity, uptime, and termination rights.",
  },
  {
    label: "AI Vendor",
    value:
      "AI software company concerned with data usage for training, IP ownership, confidentiality, service reliability, and limitations on model outputs or enterprise use.",
  },
  {
    label: "Cloud Infra",
    value:
      "Enterprise cloud infrastructure provider focused on uptime, support commitments, security responsibilities, export controls, indemnity, and liability allocation.",
  },
  {
    label: "HR Tech",
    value:
      "HR technology company handling employee PII and payroll-adjacent workflows. Prioritize privacy, confidentiality, retention, subcontractors, and termination impacts.",
  },
];

const LOADING_STAGES = [
  {
    title: "Finding legal pages",
    detail: "Locating the policy, terms, and legal pages that define the vendor relationship.",
  },
  {
    title: "Analyzing terms",
    detail: "Extracting the clauses that matter most for onboarding, liability, data use, and termination.",
  },
  {
    title: "Ranking business risks",
    detail: "Prioritizing the issues that are most likely to affect compliance, operations, and exposure.",
  },
];

function countHighlightsByRisk(result: AnalyzeResponse) {
  return result.highlights.reduce(
    (counts, item) => {
      counts[item.risk_level] += 1;
      return counts;
    },
    { high: 0, medium: 0, low: 0, unknown: 0 }
  );
}

function countChecklistByStatus(result: DpaAnalyzeResponse) {
  return result.checklist.reduce(
    (counts, item) => {
      counts[item.status] += 1;
      return counts;
    },
    { missing: 0, partial: 0, unclear: 0, satisfied: 0 }
  );
}

function isDpaResult(result: AnalysisResult | null): result is DpaAnalyzeResponse {
  return Boolean(result && "checklist" in result);
}

function getChecklistStatusLabel(item: DpaChecklistItem) {
  return item.status.replace("_", " ");
}

export default function App() {
  const [analysisType, setAnalysisType] = useState<AnalysisType>("terms");
  const [url, setUrl] = useState("");
  const [companyContext, setCompanyContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStageIndex, setLoadingStageIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);

  useEffect(() => {
    if (!loading) {
      setLoadingStageIndex(0);
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      setLoadingStageIndex((current) => Math.min(current + 1, LOADING_STAGES.length - 1));
    }, 1400);

    return () => window.clearInterval(intervalId);
  }, [loading]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (!url.trim()) {
      setError("Please provide a URL.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const analysis =
        analysisType === "dpa"
          ? await analyzeDpaUrl(url.trim(), companyContext)
          : await analyzeUrl(url.trim(), companyContext);
      setResult(analysis);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error.");
    } finally {
      setLoading(false);
    }
  };

  const applyPreset = (value: string) => {
    setCompanyContext(value);
  };

  const changeAnalysisType = (nextType: AnalysisType) => {
    setAnalysisType(nextType);
    setError(null);
    setResult(null);
  };

  const currentLoadingStage = LOADING_STAGES[loadingStageIndex];
  const loadingProgress = ((loadingStageIndex + 1) / LOADING_STAGES.length) * 100;
  const targetHost = (() => {
    try {
      return url.trim() ? new URL(url.trim()).host : null;
    } catch {
      return null;
    }
  })();
  const reviewModeTitle =
    targetHost
      ? analysisType === "dpa"
        ? `Reviewing DPA for ${targetHost}`
        : `Reviewing ${targetHost}`
      : analysisType === "dpa"
        ? "Reviewing your DPA submission"
        : "Reviewing your submission";

  const riskCounts = result && !isDpaResult(result) ? countHighlightsByRisk(result) : null;
  const checklistCounts = result && isDpaResult(result) ? countChecklistByStatus(result) : null;
  const coverageLabel = result
    ? result.blocked_links.length > 0
      ? result.source_links.length > 0
        ? "Partial"
        : "Blocked"
      : result.source_links.length > 0
        ? "Good"
        : "Limited"
    : null;

  return (
    <main className="page-shell">
      <div className="page-orb page-orb-left" />
      <div className="page-orb page-orb-right" />
      <main className="page">
        <header className="topbar">
          <div className="brand-lockup" aria-label="COMPL.AI">
            <img className="topbar-logo" src="/comp_ai-logo.png" alt="Comp AI" />
          </div>
          <nav className="top-tabs" aria-label="Primary">
            <button type="button" className="top-tab top-tab-active">
              Overview
            </button>
            <button type="button" className="top-tab">
              Reviews
            </button>
            <button type="button" className="top-tab">
              Policies
            </button>
            <button type="button" className="top-tab top-tab-cta">
              Contact
            </button>
          </nav>
        </header>
        {loading ? (
          <section className="review-mode" aria-live="polite" aria-busy="true">
            <div className="review-mode-copy">
              <div className="review-mode-meta">
                <span className="review-mode-pill">Active analysis</span>
                {targetHost ? <span className="review-mode-pill">{targetHost}</span> : null}
              </div>
              <h1 className="review-mode-heading">{reviewModeTitle}</h1>
              <p className="review-mode-body">
                {analysisType === "dpa"
                  ? "COMPL.AI is reviewing the DPA package and linked annexes before generating an Article 28 checklist."
                  : "COMPL.AI is running a focused legal intake pass before generating the final summary and ranked highlights."}
              </p>

              <div className="review-mode-notes">
                <article className="review-mode-note">
                  <strong>Coverage</strong>
                  <p>Scanning the legal surface area that defines the vendor relationship.</p>
                </article>
                <article className="review-mode-note">
                  <strong>Output</strong>
                  <p>
                    {analysisType === "dpa"
                      ? "Preparing a structured Article 28 checklist with cited privacy control findings."
                      : "Preparing a concise summary and issue list for business review."}
                  </p>
                </article>
                <article className="review-mode-note">
                  <strong>Priority</strong>
                  <p>Weighting the clauses most likely to affect compliance, risk, and operations.</p>
                </article>
              </div>
            </div>

            <section className="review-status review-status-immersive">
              <div className="review-status-header">
                <div>
                  <p className="section-kicker review-kicker">Review in progress</p>
                  <h2 className="review-title">{currentLoadingStage.title}</h2>
                </div>
                <span className="review-stage-count">
                  0{loadingStageIndex + 1}/0{LOADING_STAGES.length}
                </span>
              </div>

              <p className="review-copy">{currentLoadingStage.detail}</p>

              <div className="review-progress" aria-hidden="true">
                <div className="review-progress-track">
                  <div className="review-progress-fill" style={{ width: `${loadingProgress}%` }} />
                </div>
                <div className="review-progress-meta">
                  <span>Automated legal review</span>
                  {targetHost ? <span>{targetHost}</span> : <span>Preparing source scan</span>}
                </div>
              </div>

              <ol className="review-rail">
                {LOADING_STAGES.map((stage, index) => {
                  const stateClassName =
                    index < loadingStageIndex
                      ? "review-step review-step-complete"
                      : index === loadingStageIndex
                        ? "review-step review-step-current"
                        : "review-step";

                  return (
                    <li key={stage.title} className={stateClassName}>
                      <span className="review-step-index">0{index + 1}</span>
                      <div className="review-step-body">
                        <strong>{stage.title}</strong>
                        <span>{stage.detail}</span>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </section>
          </section>
        ) : (
          <>
            <header className="hero">
              <div className="hero-copy">
                <h1>{analysisType === "dpa" ? "Data Processing Agreement Review" : "Compliant Software Onboarding"}</h1>
                <p className="hero-body">
                  {analysisType === "dpa"
                    ? "Review a vendor DPA against Article 28-style processor obligations in minutes."
                    : "Screen any software in minutes, not hours."}
                </p>
              </div>
            </header>

            <section className="workspace-grid">
              <section className="panel intake-panel">
                <div className="panel-header">
                  <div>
                    <p className="section-kicker">Start here</p>
                  </div>
                </div>

                <div className="analysis-type-switch" role="tablist" aria-label="Review type">
                  <button
                    type="button"
                    className={analysisType === "terms" ? "analysis-type-pill analysis-type-pill-active" : "analysis-type-pill"}
                    onClick={() => changeAnalysisType("terms")}
                  >
                    T&amp;C Review
                  </button>
                  <button
                    type="button"
                    className={analysisType === "dpa" ? "analysis-type-pill analysis-type-pill-active" : "analysis-type-pill"}
                    onClick={() => changeAnalysisType("dpa")}
                  >
                    DPA Review
                  </button>
                </div>

                <form onSubmit={onSubmit} className="form">
                  <label htmlFor="url">{analysisType === "dpa" ? "Website or DPA URL" : "Website URL"}</label>
                  <div className="row">
                    <input
                      id="url"
                      type="url"
                      placeholder="https://example.com"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                    />
                    <button type="submit" disabled={loading}>
                      {loading ? "Analyzing..." : "Analyze"}
                    </button>
                  </div>

                  <label htmlFor="company-context">Company context</label>
                  <textarea
                    id="company-context"
                    className="context-input"
                    placeholder="Describe the company, product, customers, data sensitivity, or specific legal concerns you want prioritized."
                    value={companyContext}
                    onChange={(e) => setCompanyContext(e.target.value)}
                    rows={5}
                  />
                  <div className="preset-group">
                    <p className="preset-label">Quick context presets</p>
                    <div className="preset-list">
                      {CONTEXT_PRESETS.map((preset) => (
                        <button
                          key={preset.label}
                          type="button"
                          className="preset-chip"
                          onClick={() => applyPreset(preset.value)}
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </form>

                {!result && !error && (
                  <div className="inline-note">
                    <p>
                      {analysisType === "dpa"
                        ? "Enter a DPA URL or vendor website and optional company context to generate an Article 28 checklist with linked evidence."
                        : "Enter a target URL and optional company context to generate a concise compliance brief with ranked contractual risks."}
                    </p>
                  </div>
                )}

                {error && <p className="error">{error}</p>}
              </section>
            </section>
          </>
        )}

        {result && !loading && (
          <section className="results">
            <section className="results-topbar simple-topbar">
              <div>
                <p className="section-kicker">Analysis brief</p>
                <h2>{result.normalized_domain}</h2>
              </div>
              <div className="topbar-metrics compact-metrics">
                {!isDpaResult(result) ? (
                  <span className="topbar-pill topbar-pill-high">High {riskCounts?.high ?? 0}</span>
                ) : (
                  <>
                    <span className="topbar-pill topbar-pill-high">Missing {checklistCounts?.missing ?? 0}</span>
                    <span className="topbar-pill">Partial {checklistCounts?.partial ?? 0}</span>
                    <span className="topbar-pill">Satisfied {checklistCounts?.satisfied ?? 0}</span>
                  </>
                )}
                <span className="topbar-pill">Coverage {coverageLabel}</span>
                <span className="topbar-pill">Sources {result.source_links.length}</span>
                {result.blocked_links.length > 0 && <span className="topbar-pill">Blocked {result.blocked_links.length}</span>}
              </div>
            </section>

            <div className="results-primary">
              <article className="card summary-card narrative-card">
                <div className="card-header">
                  <h2>{isDpaResult(result) ? "DPA Summary" : "T&C Summary"}</h2>
                </div>
                <p className="summary-copy">{result.summary}</p>
              </article>

              <article className="card highlights-card narrative-card">
                <div className="card-header">
                  <h2>{isDpaResult(result) ? "Article 28 Checklist" : "Key Highlights"}</h2>
                </div>
                {!isDpaResult(result) ? result.highlights.length === 0 ? (
                  <p>No highlights were extracted.</p>
                ) : (
                  <ul className="highlights editorial-highlights">
                    {result.highlights.map((item, index) => (
                      <li key={`${item.title}-${index}`} className={`highlight-card highlight-card-${item.risk_level}`}>
                        <div className="title-row">
                          <strong>{item.title}</strong>
                          <span className={`risk risk-${item.risk_level}`}>{item.risk_level}</span>
                        </div>
                        <p>{item.rationale}</p>
                        {item.source_url && (
                          <p className="highlight-source">
                            Source:{" "}
                            <a href={item.source_url} target="_blank" rel="noreferrer">
                              {item.source_url}
                            </a>
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : result.checklist.length === 0 ? (
                  <p>No checklist items were extracted.</p>
                ) : (
                  <ul className="highlights editorial-highlights dpa-checklist">
                    {result.checklist.map((item) => (
                      <li key={item.requirement_key} className={`highlight-card dpa-checklist-item dpa-checklist-item-${item.status}`}>
                        <div className="title-row">
                          <strong>{item.requirement_title}</strong>
                          <span className={`check-status check-status-${item.status}`}>{getChecklistStatusLabel(item)}</span>
                        </div>
                        <p>{item.rationale}</p>
                        {item.source_url && (
                          <p className="highlight-source">
                            Source:{" "}
                            <a href={item.source_url} target="_blank" rel="noreferrer">
                              {item.source_url}
                            </a>
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </article>

              <article className="card evidence-card narrative-card">
                <div className="card-header">
                  <h2>Evidence &amp; Coverage</h2>
                </div>

                {result.confidence_notes.length > 0 && (
                  <div className="coverage-note">
                    {result.confidence_notes.map((note) => (
                      <p key={note}>{note}</p>
                    ))}
                  </div>
                )}

                <div className="evidence-section">
                  <h3>Source links</h3>
                  {result.source_links.length === 0 ? (
                    <p className="muted-copy">No source links were confirmed.</p>
                  ) : (
                    <ul className="source-list">
                      {result.source_links.map((link) => (
                        <li key={link}>
                          <a href={link} target="_blank" rel="noreferrer">
                            {link}
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {result.blocked_links.length > 0 && (
                  <div className="evidence-section">
                    <h3>Blocked links</h3>
                    <ul className="blocked-list">
                      {result.blocked_links.map((link) => (
                        <li key={link}>{link}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </article>
            </div>
          </section>
        )}
      </main>
    </main>
  );
}
