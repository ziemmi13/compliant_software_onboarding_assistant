import { FormEvent, useEffect, useRef, useState } from "react";

import { AnalyzeResponse, ApiRequestError, DpaAnalyzeResponse, DpaChecklistItem, LinkPreview, analyzeDpaUrl, analyzeUrl, fetchLinkPreviews } from "./api";

type ReviewSelection = {
  terms: boolean;
  dpa: boolean;
};

type AnalysisResults = {
  terms: AnalyzeResponse | null;
  dpa: DpaAnalyzeResponse | null;
};

type ResultTab = "terms" | "dpa";
type ViewMode = "input" | "review";

type ModuleExecutionResult<T> = {
  analysis: T | null;
  errorMessage: string | null;
};

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
  {
    label: "twoja stara",
    value: "E-commerce platform selling vintage clothing. Concerned with data privacy, liability for counterfeit goods, uptime during peak sales, and termination rights if the service doesn't meet needs.",
  }
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

const FINAL_STAGE_SLOW_THRESHOLD_SECONDS = 8;

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

function getChecklistStatusLabel(item: DpaChecklistItem) {
  return item.status.replace("_", " ");
}

function getSupportingLinkHref(link: string, preview?: LinkPreview | null) {
  if (preview) {
    return preview.resolved_url || link;
  }

  try {
    const parsed = new URL(link);
    return parsed.toString();
  } catch {
    return link;
  }
}

function hasAnySelection(selection: ReviewSelection) {
  return selection.terms || selection.dpa;
}

function getSelectionLabel(selection: ReviewSelection) {
  if (selection.terms && selection.dpa) {
    return "T&C and DPA";
  }

  if (selection.dpa) {
    return "DPA";
  }

  return "T&C";
}

function getTermsCoverageLabel(result: AnalyzeResponse) {
  if (result.blocked_links.length > 0) {
    return result.source_links.length > 0 ? "Partial coverage" : "Blocked coverage";
  }

  return result.source_links.length > 0 ? "Good coverage" : "Limited coverage";
}

function getDpaCoverageLabel(result: DpaAnalyzeResponse) {
  if (result.blocked_links.length > 0) {
    return result.source_links.length > 0 ? "Partial coverage" : "Blocked coverage";
  }

  return result.source_links.length > 0 ? "Good coverage" : "Limited coverage";
}

function hasTermsAnswer(result: AnalyzeResponse) {
  return result.highlights.length > 0;
}

function hasDpaAnswer(result: DpaAnalyzeResponse) {
  return (
    result.checklist.length > 0 ||
    result.summary.trim().length > 0 ||
    result.supporting_links.length > 0 ||
    result.source_links.length > 0
  );
}

function formatModuleFailureMessage(kind: ResultTab, error: unknown) {
  const moduleLabel = kind === "terms" ? "T&C" : "DPA";
  const specificUrlHint = kind === "terms" ? "a direct terms URL" : "a direct DPA URL";

  if (error instanceof ApiRequestError) {
    if (error.code === "invalid_url") {
      return "Please provide a valid http or https URL.";
    }

    return `${moduleLabel} analysis failed. Try again or use ${specificUrlHint}.`;
  }

  return `${moduleLabel} analysis failed. Try again or use ${specificUrlHint}.`;
}

export default function App() {
  const activeRequestIdRef = useRef(0);
  const [url, setUrl] = useState("");
  const [companyContext, setCompanyContext] = useState("");
  const [reviewSelection, setReviewSelection] = useState<ReviewSelection>({ terms: true, dpa: true });
  const [viewMode, setViewMode] = useState<ViewMode>("input");
  const [loading, setLoading] = useState(false);
  const [loadingStageIndex, setLoadingStageIndex] = useState(0);
  const [loadingElapsedSeconds, setLoadingElapsedSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<AnalysisResults>({ terms: null, dpa: null });
  const [supportingLinkPreviews, setSupportingLinkPreviews] = useState<Record<string, LinkPreview>>({});
  const [activeResultTab, setActiveResultTab] = useState<ResultTab>("terms");

  useEffect(() => {
    if (!loading) {
      setLoadingStageIndex(0);
      return undefined;
    }

    setLoadingStageIndex(0);

    const intervalId = window.setInterval(() => {
      setLoadingStageIndex((current) => Math.min(current + 1, LOADING_STAGES.length - 1));
    }, 1400);

    return () => window.clearInterval(intervalId);
  }, [loading]);

  useEffect(() => {
    if (!loading) {
      setLoadingElapsedSeconds(0);
      return undefined;
    }

    const startedAt = Date.now();
    setLoadingElapsedSeconds(0);
    const intervalId = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setLoadingElapsedSeconds(elapsed);
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, [loading]);

  useEffect(() => {
    const links = results.dpa?.supporting_links ?? [];
    const requestId = activeRequestIdRef.current;

    if (links.length === 0) {
      setSupportingLinkPreviews({});
      return undefined;
    }

    let isCancelled = false;
    setSupportingLinkPreviews({});

    void (async () => {
      try {
        const previews = await fetchLinkPreviews(links);
        if (isCancelled || activeRequestIdRef.current !== requestId) {
          return;
        }

        setSupportingLinkPreviews(
          Object.fromEntries(previews.map((preview) => [preview.requested_url, preview]))
        );
      } catch {
        if (!isCancelled && activeRequestIdRef.current === requestId) {
          setSupportingLinkPreviews({});
        }
      }
    })();

    return () => {
      isCancelled = true;
    };
  }, [results.dpa]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (!url.trim()) {
      setError("Please provide a URL.");
      return;
    }

    if (!hasAnySelection(reviewSelection)) {
      setError("Select at least one review type.");
      return;
    }

    const requestId = activeRequestIdRef.current + 1;
    activeRequestIdRef.current = requestId;

    setLoading(true);
    setError(null);
    setResults({ terms: null, dpa: null });
    setSupportingLinkPreviews({});
    setActiveResultTab(reviewSelection.dpa && !reviewSelection.terms ? "dpa" : "terms");

    try {
      const executeOnce = async <T,>(
        kind: ResultTab,
        run: () => Promise<T>,
        hasAnswer: (result: T) => boolean
      ): Promise<ModuleExecutionResult<T>> => {
        try {
          const analysis = await run();
          if (hasAnswer(analysis)) {
            return { analysis, errorMessage: null };
          }

          return {
            analysis: null,
            errorMessage:
              kind === "dpa"
                ? "DPA analysis did not return structured checklist output."
                : "T&C analysis did not return an answer.",
          };
        } catch (error) {
          return { analysis: null, errorMessage: formatModuleFailureMessage(kind, error) };
        }
      };

      const termsJob = reviewSelection.terms
        ? executeOnce("terms", () => analyzeUrl(url.trim(), companyContext), hasTermsAnswer)
        : Promise.resolve<ModuleExecutionResult<AnalyzeResponse>>({ analysis: null, errorMessage: null });
      const dpaJob = reviewSelection.dpa
        ? executeOnce("dpa", () => analyzeDpaUrl(url.trim(), companyContext), hasDpaAnswer)
        : Promise.resolve<ModuleExecutionResult<DpaAnalyzeResponse>>({ analysis: null, errorMessage: null });

      const [termsResult, dpaResult] = await Promise.all([termsJob, dpaJob]);
      const nextResults: AnalysisResults = {
        terms: termsResult.analysis,
        dpa: dpaResult.analysis,
      };
      const failures = [termsResult.errorMessage, dpaResult.errorMessage].filter(Boolean) as string[];

      if (activeRequestIdRef.current !== requestId) {
        return;
      }

      setResults(nextResults);

      if (nextResults.terms || nextResults.dpa) {
        setViewMode("review");
      }

      if (failures.length > 0) {
        setError(failures.join(" "));
      }
    } catch (err) {
      if (activeRequestIdRef.current !== requestId) {
        return;
      }

      setError(err instanceof Error ? err.message : "Unknown error.");
    } finally {
      if (activeRequestIdRef.current === requestId) {
        setLoading(false);
      }
    }
  };

  const applyPreset = (value: string) => {
    setCompanyContext(value);
  };

  const toggleReviewType = (reviewType: keyof ReviewSelection) => {
    setReviewSelection((current) => ({ ...current, [reviewType]: !current[reviewType] }));
    setError(null);
    setResults({ terms: null, dpa: null });
    setSupportingLinkPreviews({});
    setViewMode("input");
  };

  const returnToSetup = () => {
    activeRequestIdRef.current += 1;
    setLoading(false);
    setViewMode("input");
    setError(null);
    setResults({ terms: null, dpa: null });
    setSupportingLinkPreviews({});
  };

  const currentLoadingStage = LOADING_STAGES[loadingStageIndex];
  const isFinalLoadingStage = loading && loadingStageIndex === LOADING_STAGES.length - 1;
  const finalStageHasExtendedRun = isFinalLoadingStage && loadingElapsedSeconds >= FINAL_STAGE_SLOW_THRESHOLD_SECONDS;
  const loadingProgress = isFinalLoadingStage
    ? ((LOADING_STAGES.length - 1) / LOADING_STAGES.length) * 100
    : ((loadingStageIndex + 1) / LOADING_STAGES.length) * 100;
  const loadingDetail = isFinalLoadingStage
    ? "Prioritizing findings across contractual, compliance, and operational impact before finalizing the report."
    : currentLoadingStage.detail;
  const targetHost = (() => {
    try {
      return url.trim() ? new URL(url.trim()).host : null;
    } catch {
      return null;
    }
  })();
  const reviewModeTitle =
    targetHost
      ? `Reviewing ${getSelectionLabel(reviewSelection)} for ${targetHost}`
      : `Reviewing your ${getSelectionLabel(reviewSelection)} submission`;

  const termsRiskCounts = results.terms ? countHighlightsByRisk(results.terms) : null;
  const dpaChecklistCounts = results.dpa ? countChecklistByStatus(results.dpa) : null;

  const getCoverageLabel = (sourceLinks: string[], blockedLinks: string[]) => {
    if (blockedLinks.length > 0) {
      return sourceLinks.length > 0 ? "Partial" : "Blocked";
    }

    return sourceLinks.length > 0 ? "Good" : "Limited";
  };

  const hasResults = Boolean(results.terms || results.dpa);
  const availableTabs: ResultTab[] = [results.terms ? "terms" : null, results.dpa ? "dpa" : null].filter(Boolean) as ResultTab[];
  const visibleResultTab = availableTabs.includes(activeResultTab) ? activeResultTab : availableTabs[0] ?? "terms";

  useEffect(() => {
    if (results.terms && !results.dpa) {
      setActiveResultTab("terms");
      return;
    }

    if (results.dpa && !results.terms) {
      setActiveResultTab("dpa");
    }
  }, [results.dpa, results.terms]);

  const renderTermsPanel = () => {
    if (!results.terms) {
      return null;
    }

    return (
      <section className="result-block">
        <section className="results-topbar simple-topbar">
          <div className="topbar-metrics compact-metrics">
            <span className="topbar-pill topbar-pill-high">High {termsRiskCounts?.high ?? 0}</span>
            <span className="topbar-pill topbar-pill-medium">Medium {termsRiskCounts?.medium ?? 0}</span>
            <span className="topbar-pill topbar-pill-low">Low {termsRiskCounts?.low ?? 0}</span>
            <span className="topbar-pill topbar-pill-coverage">Coverage {getCoverageLabel(results.terms.source_links, results.terms.blocked_links)}</span>
            <span className="topbar-pill topbar-pill-sources">Sources {results.terms.source_links.length}</span>
            {results.terms.blocked_links.length > 0 && <span className="topbar-pill topbar-pill-blocked">Blocked {results.terms.blocked_links.length}</span>}
          </div>
        </section>

        <div className="results-primary">
          <article className="card summary-card narrative-card">
            <div className="card-header">
              <h2>T&amp;C Summary</h2>
            </div>
            <p className="summary-copy">{results.terms.summary}</p>
          </article>

          <article className="card highlights-card narrative-card">
            <div className="card-header">
              <h2>Key Highlights</h2>
            </div>
            {results.terms.highlights.length === 0 ? (
              <p>No highlights were extracted.</p>
            ) : (
              <ul className="highlights editorial-highlights">
                {results.terms.highlights.map((item, index) => (
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
            )}
          </article>

          <article className="card evidence-card narrative-card">
            <div className="card-header">
              <h2>Evidence &amp; Coverage</h2>
            </div>

            <div className="evidence-section">
              <h3>Source links</h3>
              {results.terms.source_links.length === 0 ? (
                <p className="muted-copy">No source links were confirmed.</p>
              ) : (
                <ul className="source-list">
                  {results.terms.source_links.map((link) => (
                    <li key={link}>
                      <a href={link} target="_blank" rel="noreferrer">
                        {link}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {results.terms.blocked_links.length > 0 && (
              <div className="evidence-section">
                <h3>Blocked links</h3>
                <ul className="blocked-list">
                  {results.terms.blocked_links.map((link) => (
                    <li key={link}>{link}</li>
                  ))}
                </ul>
              </div>
            )}
          </article>
        </div>
      </section>
    );
  };

  const renderDpaPanel = () => {
    if (!results.dpa) {
      return null;
    }

    return (
      <section className="result-block">
        <section className="results-topbar simple-topbar">
          <div className="topbar-metrics compact-metrics">
            <span className="topbar-pill topbar-pill-high">Missing {dpaChecklistCounts?.missing ?? 0}</span>
            <span className="topbar-pill topbar-pill-partial">Partial {dpaChecklistCounts?.partial ?? 0}</span>
            <span className="topbar-pill topbar-pill-satisfied">Satisfied {dpaChecklistCounts?.satisfied ?? 0}</span>
            <span className="topbar-pill topbar-pill-coverage">Coverage {getCoverageLabel(results.dpa.source_links, results.dpa.blocked_links)}</span>
            <span className="topbar-pill topbar-pill-sources">Sources {results.dpa.source_links.length}</span>
            {results.dpa.supporting_links.length > 0 && <span className="topbar-pill topbar-pill-sources">Support {results.dpa.supporting_links.length}</span>}
            {results.dpa.blocked_links.length > 0 && <span className="topbar-pill topbar-pill-blocked">Blocked {results.dpa.blocked_links.length}</span>}
          </div>
        </section>

        <div className="results-primary">
          <article className="card summary-card narrative-card">
            <div className="card-header">
              <h2>DPA Summary</h2>
            </div>
            <p className="summary-copy">{results.dpa.summary}</p>
          </article>

          <article className="card highlights-card narrative-card">
            <div className="card-header">
              <h2>Article 28 Checklist</h2>
            </div>
            {results.dpa.checklist.length === 0 ? (
              <p>No checklist items were extracted.</p>
            ) : (
              <ul className="highlights editorial-highlights dpa-checklist">
                {results.dpa.checklist.map((item) => (
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

            <div className="evidence-section">
              <h3>Source links</h3>
              {results.dpa.source_links.length === 0 ? (
                <p className="muted-copy">
                  {results.dpa.supporting_links.length > 0
                    ? "No confirmed DPA page was found."
                    : "No source links were confirmed."}
                </p>
              ) : (
                <ul className="source-list evidence-link-list">
                  {results.dpa.source_links.map((link) => (
                    <li key={link}>
                      <a href={link} target="_blank" rel="noreferrer">
                        {link}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {results.dpa.supporting_links.length > 0 && (
              <div className="evidence-section">
                <h3>Supporting links</h3>
                <ul className="source-list evidence-link-list">
                  {results.dpa.supporting_links.map((link, index) => {
                    const resolvedHref = getSupportingLinkHref(link, supportingLinkPreviews[link]);

                    return (
                      <li key={link}>
                        <a href={resolvedHref} target="_blank" rel="noreferrer" title={resolvedHref}>
                          {resolvedHref}
                        </a>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {results.dpa.blocked_links.length > 0 && (
              <div className="evidence-section">
                <h3>Blocked links</h3>
                <ul className="blocked-list">
                  {results.dpa.blocked_links.map((link) => (
                    <li key={link}>{link}</li>
                  ))}
                </ul>
              </div>
            )}
          </article>
        </div>
      </section>
    );
  };

  const showReviewScreen = viewMode === "review" && hasResults;
  const showLogoHomeAction = loading || showReviewScreen;

  return (
    <main className="page-shell">
      <div className="page-orb page-orb-left" />
      <div className="page-orb page-orb-right" />
      <main className={showReviewScreen ? "page page-review" : "page"}>
        <header className="topbar">
          {showLogoHomeAction ? (
            <button type="button" className="brand-lockup brand-lockup-button" onClick={returnToSetup} aria-label="Return to front page">
              <img className="topbar-logo" src="/comp_ai-logo.png" alt="Comp AI" />
            </button>
          ) : (
            <div className="brand-lockup" aria-label="COMPL.AI">
              <img className="topbar-logo" src="/comp_ai-logo.png" alt="Comp AI" />
            </div>
          )}
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
          <section className="review-mode" aria-busy="true">
            <div className="review-mode-copy">
              <div className="review-mode-meta">
                <span className="review-mode-pill">Active analysis</span>
                {targetHost ? <span className="review-mode-pill">{targetHost}</span> : null}
              </div>
              <h1 className="review-mode-heading">{reviewModeTitle}</h1>
              <p className="review-mode-body">
                {reviewSelection.terms && reviewSelection.dpa
                  ? "COMPL.AI is running both the contractual review and the DPA review before assembling the combined report."
                  : reviewSelection.dpa
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
                    {reviewSelection.terms && reviewSelection.dpa
                      ? "Preparing a combined report with ranked T&C issues and a cited DPA checklist."
                      : reviewSelection.dpa
                        ? "Preparing a structured Article 28 checklist with cited privacy control findings."
                        : "Preparing a concise T&C report with ranked issues and linked source pages."}
                  </p>
                </article>
                <article className="review-mode-note">
                  <strong>Priority</strong>
                  <p>Weighting the clauses most likely to affect compliance, risk, and operations.</p>
                </article>
              </div>
            </div>

            <section className="review-status review-status-immersive">
              <p className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">
                {isFinalLoadingStage
                  ? "Final prioritization step is in progress."
                  : `${currentLoadingStage.title} is in progress.`}
              </p>
              <div className="review-status-header">
                <div>
                  <p className="section-kicker review-kicker">Review in progress</p>
                  <h2 className="review-title">{currentLoadingStage.title}</h2>
                </div>
                <span className="review-stage-count">
                  0{loadingStageIndex + 1}/0{LOADING_STAGES.length}
                </span>
              </div>

              <p className="review-copy">{loadingDetail}</p>
              {isFinalLoadingStage ? (
                <p className="review-note-live">
                  This final prioritization pass usually takes longer than discovery and clause extraction.
                  {finalStageHasExtendedRun ? " We are still processing and validating severity ordering." : ""}
                </p>
              ) : null}

              <div className="review-progress" aria-hidden="true">
                <div
                  className={
                    isFinalLoadingStage
                      ? "review-progress-track review-progress-track-indeterminate"
                      : "review-progress-track"
                  }
                >
                  <div
                    className={
                      isFinalLoadingStage
                        ? "review-progress-fill review-progress-fill-indeterminate"
                        : "review-progress-fill"
                    }
                    style={isFinalLoadingStage ? undefined : { width: `${loadingProgress}%` }}
                  />
                </div>
                <div className="review-progress-meta">
                  <span>{isFinalLoadingStage ? "Prioritization in progress" : "Automated legal review"}</span>
                  <span>
                    {targetHost ? `${targetHost} - ${loadingElapsedSeconds}s elapsed` : `${loadingElapsedSeconds}s elapsed`}
                  </span>
                </div>
              </div>

              <ol className="review-rail">
                {LOADING_STAGES.map((stage, index) => {
                  const stateClassName =
                    index < loadingStageIndex
                      ? "review-step review-step-complete"
                      : index === loadingStageIndex
                        ? isFinalLoadingStage
                          ? "review-step review-step-current review-step-current-pending"
                          : "review-step review-step-current"
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
        ) : showReviewScreen ? (
          <section className="review-shell">
            <div className="review-shell-header">
              <div className="review-shell-copy">
                <p className="section-kicker">Review ready</p>
                <h1 className="review-shell-title">{targetHost ?? "Analysis report"}</h1>
                <p className="review-shell-body">
                  Switch between the completed review modules below, or go back to refine the software, URL, and context.
                </p>
              {availableTabs.length > 1 && (
                <div className="results-tablist results-tablist-header" role="tablist" aria-label="Result sections">
                  {results.terms && (
                    <button
                      type="button"
                      role="tab"
                      aria-selected={visibleResultTab === "terms"}
                      aria-label="Show T and C results"
                      className={visibleResultTab === "terms" ? "results-tab results-tab-active" : "results-tab"}
                      onClick={() => setActiveResultTab("terms")}
                    >
                      <span>T&amp;C</span>
                    </button>
                  )}
                  {results.dpa && (
                    <button
                      type="button"
                      role="tab"
                      aria-selected={visibleResultTab === "dpa"}
                      aria-label="Show D P A results"
                      className={visibleResultTab === "dpa" ? "results-tab results-tab-active" : "results-tab"}
                      onClick={() => setActiveResultTab("dpa")}
                    >
                      <span>DPA</span>
                    </button>
                  )}
                </div>
              )}
              </div>
              <button type="button" className="review-back-button" onClick={returnToSetup}>
                Back to setup
              </button>
            </div>

            {error ? <p className="error review-error">{error}</p> : null}

            <section className="results results-stack">

              {visibleResultTab === "terms" ? renderTermsPanel() : renderDpaPanel()}
            </section>
          </section>
        ) : (
          <>
            <header className="hero">
              <div className="hero-copy">
                <h1>Compliant Software Onboarding</h1>
                <p className="hero-body">
                  Screen andy software in minutes instead of days.
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

                <fieldset className="review-type-group">
                  <legend>Select reviews</legend>
                  <p className="field-note">Pick one or both review types. The system only runs the items you check.</p>
                  <div className="review-type-switch" role="group" aria-label="Review type">
                    <label className={reviewSelection.terms ? "review-type-card review-type-card-selected" : "review-type-card"}>
                      <input
                        type="checkbox"
                        checked={reviewSelection.terms}
                        onChange={() => toggleReviewType("terms")}
                      />
                      <span>
                        <strong>T&amp;C Review</strong>
                        <small>Terms, platform obligations, liability, and commercial risk.</small>
                      </span>
                    </label>
                    <label className={reviewSelection.dpa ? "review-type-card review-type-card-selected" : "review-type-card"}>
                      <input
                        type="checkbox"
                        checked={reviewSelection.dpa}
                        onChange={() => toggleReviewType("dpa")}
                      />
                      <span>
                        <strong>DPA Review</strong>
                        <small>Article 28 processor obligations, annexes, and privacy controls.</small>
                      </span>
                    </label>
                  </div>
                </fieldset>

                <form onSubmit={onSubmit} className="form">
                  <label htmlFor="url">Insert URL</label>
                  <p className="field-note field-note-tight">
                    Paste a homepage, terms page, or DPA link. The app will follow the relevant legal surface from there.
                  </p>
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
                  <p className="field-note field-note-tight">
                    Optional. Add your business model, customer profile, or legal concerns so the review is prioritized correctly.
                  </p>
                  <textarea
                    id="company-context"
                    className="context-input"
                    placeholder="Describe the company, product, customers, data sensitivity, or specific legal concerns you want prioritized."
                    value={companyContext}
                    onChange={(e) => setCompanyContext(e.target.value)}
                    rows={3}
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

                {error && <p className="error">{error}</p>}
              </section>
            </section>
          </>
        )}
      </main>
    </main>
  );
}
