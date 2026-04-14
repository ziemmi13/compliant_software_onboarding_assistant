import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { AnalyzeResponse, ApiRequestError, DpaAnalyzeResponse, DpaChecklistItem, DpiaAnalyzeResponse, DpiaThresholdItem, LinkPreview, RopaAnalyzeResponse, RopaField, analyzeDpaUrl, analyzeDpiaUrl, analyzeRopaUrl, analyzeUrl, fetchLinkPreviews } from "./api";
import { TermsPanel } from "./components/TermsPanel";
import { DpaPanel } from "./components/DpaPanel";
import { DpiaPanel } from "./components/DpiaPanel";
import { RopaPanel } from "./components/RopaPanel";
import { countBy, parseUrlHostname, parseUrlHost, formatStatusLabel } from "./utils";
import { MODULE_LABELS, ERROR_HINTS, LOADING_MESSAGES, OUTPUT_DESCRIPTIONS } from "./constants";

type ReviewSelection = {
  terms: boolean;
  dpa: boolean;
  dpia: boolean;
  ropa: boolean;
};

type AnalysisResults = {
  terms: AnalyzeResponse | null;
  dpa: DpaAnalyzeResponse | null;
  dpia: DpiaAnalyzeResponse | null;
  ropa: RopaAnalyzeResponse | null;
};

type ResultTab = "terms" | "dpa" | "dpia" | "ropa";
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

const SESSIONS_KEY = "legal_scout_sessions";
const SESSIONS_VERSION = 1;


function getChecklistStatusLabel(item: DpaChecklistItem) {
  return formatStatusLabel(item.status);
}

function getThresholdStatusLabel(item: DpiaThresholdItem) {
  return formatStatusLabel(item.status);
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
  return selection.terms || selection.dpa || selection.dpia || selection.ropa;
}

function getSelectionLabel(selection: ReviewSelection) {
  const parts: string[] = [];
  if (selection.terms) parts.push(MODULE_LABELS.terms);
  if (selection.dpa) parts.push(MODULE_LABELS.dpa);
  if (selection.dpia) parts.push(MODULE_LABELS.dpia);
  if (selection.ropa) parts.push(MODULE_LABELS.ropa);
  return parts.join(" and ") || MODULE_LABELS.terms;
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

function hasDpiaAnswer(result: DpiaAnalyzeResponse) {
  return (
    result.threshold_criteria.length > 0 ||
    result.summary.trim().length > 0 ||
    result.source_links.length > 0
  );
}

function hasRopaAnswer(result: RopaAnalyzeResponse) {
  return result.summary.trim().length > 0 || result.ropa_fields.length > 0;
}

function formatModuleFailureMessage(kind: ResultTab, error: unknown) {
  const moduleLabel = MODULE_LABELS[kind] || kind.toUpperCase();
  const specificUrlHint = ERROR_HINTS[kind] || "try again";

  if (error instanceof ApiRequestError) {
    if (error.code === "invalid_url") {
      return "Please provide a valid http or https URL.";
    }

    return `${moduleLabel} analysis failed. Try again or use ${specificUrlHint}.`;
  }

  return `${moduleLabel} analysis failed. Try again or use ${specificUrlHint}.`;
}

type SessionStatus = "processing" | "complete" | "error";

type SavedSession = {
  id: string;
  createdAt: string;
  url: string;
  normalizedDomain: string;
  name?: string;
  companyContext: string;
  reviewSelection: ReviewSelection;
  results: AnalysisResults;
  activeResultTab: ResultTab;
  status?: SessionStatus;
};

function formatSessionDate(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function getLoadingMessage(selection: ReviewSelection): string {
  if (selection.ropa) return LOADING_MESSAGES.ropa;
  if (selection.dpia) return LOADING_MESSAGES.dpia;
  if (selection.terms && selection.dpa) return LOADING_MESSAGES["terms-dpa"];
  if (selection.dpa) return LOADING_MESSAGES.dpa;
  return LOADING_MESSAGES.terms;
}

function getOutputDescription(selection: ReviewSelection): string {
  if (selection.ropa) return OUTPUT_DESCRIPTIONS.ropa;
  if (selection.terms && selection.dpa) return OUTPUT_DESCRIPTIONS["terms-dpa"];
  if (selection.dpa) return OUTPUT_DESCRIPTIONS.dpa;
  return OUTPUT_DESCRIPTIONS.terms;
}

export default function App() {
  const activeRequestIdRef = useRef(0);
  const [url, setUrl] = useState("");
  const [companyContext, setCompanyContext] = useState("");
  const [reviewSelection, setReviewSelection] = useState<ReviewSelection>({ terms: true, dpa: true, dpia: false, ropa: false });
  const [viewMode, setViewMode] = useState<ViewMode>("input");
  const [loading, setLoading] = useState(false);
  const [loadingStageIndex, setLoadingStageIndex] = useState(0);
  const [loadingElapsedSeconds, setLoadingElapsedSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<AnalysisResults>({ terms: null, dpa: null, dpia: null, ropa: null });
  const [supportingLinkPreviews, setSupportingLinkPreviews] = useState<Record<string, LinkPreview>>({});
  const [activeResultTab, setActiveResultTab] = useState<ResultTab>("terms");
  const [sessions, setSessions] = useState<SavedSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Load sessions from localStorage on mount and auto-restore the most recent one
  useEffect(() => {
    try {
      const raw = localStorage.getItem(SESSIONS_KEY);
      if (!raw) return;
      const data = JSON.parse(raw) as { v: number; sessions: SavedSession[] };
      if (data.v !== SESSIONS_VERSION || !Array.isArray(data.sessions)) return;
      setSessions(data.sessions);
      if (data.sessions.length > 0) {
        const last = data.sessions[0];
        setUrl(last.url);
        setCompanyContext(last.companyContext);
        setReviewSelection(last.reviewSelection);
        setResults(last.results);
        setActiveResultTab(last.activeResultTab);
        setViewMode("review");
        setActiveSessionId(last.id);
      }
    } catch {
      // Ignore malformed or missing session data
    }
  }, []);

  // Persist sessions list to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem(SESSIONS_KEY, JSON.stringify({ v: SESSIONS_VERSION, sessions }));
    } catch {
      // Ignore quota or serialization errors
    }
  }, [sessions]);

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
    const dpaLinks = results.dpa?.supporting_links ?? [];
    const dpiaLinks = results.dpia?.supporting_links ?? [];
    const links = [...new Set([...dpaLinks, ...dpiaLinks])];
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
  }, [results.dpa, results.dpia]);

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
    setResults({ terms: null, dpa: null, dpia: null, ropa: null });
    setSupportingLinkPreviews({});
    setActiveResultTab(
      reviewSelection.terms ? "terms" : reviewSelection.ropa ? "ropa" : reviewSelection.dpa ? "dpa" : "dpia"
    );

    const savedDomain = parseUrlHostname(url);
    const newId = crypto.randomUUID();
    const pendingSession: SavedSession = {
      id: newId,
      createdAt: new Date().toISOString(),
      url: url.trim(),
      normalizedDomain: savedDomain,
      companyContext,
      reviewSelection,
      results: { terms: null, dpa: null, dpia: null, ropa: null },
      activeResultTab: reviewSelection.terms ? "terms" : reviewSelection.ropa ? "ropa" : reviewSelection.dpa ? "dpa" : "dpia",
      status: "processing",
    };
    setSessions((prev) => [pendingSession, ...prev]);
    setActiveSessionId(newId);
    setViewMode("review");

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
                : kind === "dpia"
                  ? "DPIA analysis did not return structured screening output."
                  : kind === "ropa"
                    ? "ROPA synthesis did not return a structured registry output."
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
      const dpiaJob = reviewSelection.dpia
        ? executeOnce("dpia", () => analyzeDpiaUrl(url.trim(), companyContext), hasDpiaAnswer)
        : Promise.resolve<ModuleExecutionResult<DpiaAnalyzeResponse>>({ analysis: null, errorMessage: null });

      const [termsResult, dpaResult, dpiaResult] = await Promise.all([termsJob, dpaJob, dpiaJob]);
      const nextResults: AnalysisResults = {
        terms: termsResult.analysis,
        dpa: dpaResult.analysis,
        dpia: dpiaResult.analysis,
        ropa: null,
      };
      const failures = [termsResult.errorMessage, dpaResult.errorMessage, dpiaResult.errorMessage].filter(Boolean) as string[];

      if (reviewSelection.ropa) {
        if (nextResults.dpa && nextResults.dpia) {
          const ropaResult = await executeOnce(
            "ropa",
            () => analyzeRopaUrl(url.trim(), nextResults.dpa as DpaAnalyzeResponse, nextResults.dpia as DpiaAnalyzeResponse, companyContext),
            hasRopaAnswer
          );
          nextResults.ropa = ropaResult.analysis;
          if (ropaResult.errorMessage) {
            failures.push(ropaResult.errorMessage);
          }
        } else {
          failures.push("ROPA synthesis requires both DPA and DPIA results, so the registry view could not be generated.");
        }
      }

      const savedTab: ResultTab = nextResults.terms ? "terms" : nextResults.dpa ? "dpa" : nextResults.dpia ? "dpia" : "ropa";
      setSessions((prev) =>
        prev.map((s) =>
          s.id === newId
            ? { ...s, results: nextResults, activeResultTab: savedTab, status: "complete" as SessionStatus }
            : s
        )
      );

      if (activeRequestIdRef.current !== requestId) {
        return;
      }

      setResults(nextResults);

      if (failures.length > 0) {
        setError(failures.join(" "));
      }
    } catch (err) {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === newId ? { ...s, status: "error" as SessionStatus } : s
        )
      );

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
    setReviewSelection((current) => {
      if (reviewType === "ropa") {
        const nextRopa = !current.ropa;
        return {
          ...current,
          ropa: nextRopa,
          dpa: nextRopa ? true : current.dpa,
          dpia: nextRopa ? true : current.dpia,
        };
      }

      if (reviewType === "dpa") {
        const nextDpa = !current.dpa;
        return { ...current, dpa: nextDpa, ropa: nextDpa ? current.ropa : false };
      }

      if (reviewType === "dpia") {
        const nextDpia = !current.dpia;
        return { ...current, dpia: nextDpia, ropa: nextDpia ? current.ropa : false };
      }

      return { ...current, [reviewType]: !current[reviewType] };
    });
    setError(null);
    setResults({ terms: null, dpa: null, dpia: null, ropa: null });
    setSupportingLinkPreviews({});
    setViewMode("input");
  };

  const returnToSetup = () => {
    activeRequestIdRef.current += 1;
    setLoading(false);
    setViewMode("input");
    setError(null);
    setResults({ terms: null, dpa: null, dpia: null, ropa: null });
    setSupportingLinkPreviews({});
    setActiveSessionId(null);
  };

  const startRenaming = (session: SavedSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setRenamingSessionId(session.id);
    setRenameValue(session.name ?? session.normalizedDomain);
  };

  const commitRename = (id: string) => {
    const trimmed = renameValue.trim();
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, name: trimmed || undefined } : s))
    );
    setRenamingSessionId(null);
  };

  const loadSession = (session: SavedSession) => {
    activeRequestIdRef.current += 1;
    setLoading(false);
    setUrl(session.url);
    setCompanyContext(session.companyContext);
    setReviewSelection(session.reviewSelection);
    setResults(session.results);
    setActiveResultTab(session.activeResultTab);
    setViewMode("review");
    setError(null);
    setSupportingLinkPreviews({});
    setActiveSessionId(session.id);
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
  const targetHost = parseUrlHost(url);
  const reviewModeTitle =
    targetHost
      ? `Reviewing ${getSelectionLabel(reviewSelection)} for ${targetHost}`
      : `Reviewing your ${getSelectionLabel(reviewSelection)} submission`;

  const termsRiskCounts = results.terms
    ? countBy(results.terms.highlights, "risk_level", { high: 0, medium: 0, low: 0, unknown: 0 })
    : null;
  const dpaChecklistCounts = results.dpa
    ? countBy(results.dpa.checklist, "status", { missing: 0, partial: 0, unclear: 0, satisfied: 0 })
    : null;
  const dpiaThresholdCounts = results.dpia
    ? countBy(results.dpia.threshold_criteria, "status", { detected: 0, not_detected: 0, insufficient_info: 0 })
    : null;
  const ropaFieldCounts = results.ropa
    ? countBy(results.ropa.ropa_fields, "status", { populated: 0, partial: 0, placeholder: 0 })
    : null;

  const getCoverageLabel = (sourceLinks: string[], blockedLinks: string[]) => {
    if (blockedLinks.length > 0) {
      return sourceLinks.length > 0 ? "Partial" : "Blocked";
    }

    return sourceLinks.length > 0 ? "Good" : "Limited";
  };

  const hasResults = Boolean(results.terms || results.dpa || results.dpia || results.ropa);
  const availableTabs: ResultTab[] = [results.terms ? "terms" : null, results.dpa ? "dpa" : null, results.dpia ? "dpia" : null, results.ropa ? "ropa" : null].filter(Boolean) as ResultTab[];
  const visibleResultTab = availableTabs.includes(activeResultTab) ? activeResultTab : availableTabs[0] ?? "terms";





  const showReviewScreen = viewMode === "review" && hasResults;
  const showLogoHomeAction = loading || showReviewScreen;

  return (
    <>
      <aside className={sidebarCollapsed ? "sessions-sidebar sessions-sidebar-collapsed" : "sessions-sidebar"}>
          <div className="sidebar-header">
            <div className="sidebar-header-row">
              {!sidebarCollapsed && <p className="sidebar-title">Sessions</p>}
              <button
                type="button"
                className="sidebar-collapse-btn"
                aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                onClick={() => setSidebarCollapsed((c) => !c)}
              >
                {sidebarCollapsed ? "»" : "«"}
              </button>
            </div>
            {!sidebarCollapsed && (
              <button type="button" className="sidebar-new-btn" onClick={returnToSetup}>
                + New session
              </button>
            )}
          </div>
          {!sidebarCollapsed && (
          <div className="sidebar-sessions">
            {sessions.length === 0 ? (
              <p className="sidebar-empty">Your completed analyses will appear here.</p>
            ) : (
              sessions.map((session) => (
              <div
                key={session.id}
                className={session.id === activeSessionId ? "sidebar-session-item sidebar-session-item-active" : "sidebar-session-item"}
              >
                {renamingSessionId === session.id ? (
                  <input
                    className="sidebar-rename-input"
                    autoFocus
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={() => commitRename(session.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitRename(session.id);
                      if (e.key === "Escape") setRenamingSessionId(null);
                    }}
                  />
                ) : (
                  <button
                    type="button"
                    className="sidebar-session-btn"
                    onClick={() => loadSession(session)}
                  >
                    <span className="sidebar-session-domain">{session.name ?? session.normalizedDomain}</span>
                    <span className="sidebar-session-date">{formatSessionDate(session.createdAt)}</span>
                    <span className="sidebar-session-badges">
                      {session.status === "processing" ? (
                        <span className="sidebar-badge sidebar-badge-processing">Analysing…</span>
                      ) : session.status === "error" ? (
                        <span className="sidebar-badge sidebar-badge-error">Failed</span>
                      ) : (
                        <>
                          {session.reviewSelection.terms && session.results.terms && <span className="sidebar-badge">T&amp;C</span>}
                          {session.reviewSelection.dpa && session.results.dpa && <span className="sidebar-badge">DPA</span>}
                          {session.reviewSelection.dpia && session.results.dpia && <span className="sidebar-badge">DPIA</span>}
                          {session.reviewSelection.ropa && session.results.ropa && <span className="sidebar-badge">ROPA</span>}
                        </>
                      )}
                    </span>
                  </button>
                )}
                {renamingSessionId !== session.id && (
                  <button
                    type="button"
                    className="sidebar-rename-btn"
                    aria-label="Rename session"
                    onClick={(e) => startRenaming(session, e)}
                  >
                    ✎
                  </button>
                )}
              </div>
            ))
            )}
          </div>
          )}
        </aside>
      <main className={sidebarCollapsed ? "page-shell page-shell-with-sidebar-collapsed" : "page-shell page-shell-with-sidebar"}>
        <div className="page-orb page-orb-left" />
        <div className="page-orb page-orb-right" />
      <main className={showReviewScreen ? "page page-review" : "page"}>
        <div className="topbar-wrapper">
        <header className="topbar">
          {showLogoHomeAction ? (
            <Link to="/" className="brand-lockup brand-lockup-button" aria-label="Return to front page">
              <img className="topbar-logo" src="/comp_ai-logo.png" alt="Comp AI" />
            </Link>
          ) : (
            <Link to="/" className="brand-lockup brand-lockup-button" aria-label="COMPL.AI">
              <img className="topbar-logo" src="/comp_ai-logo.png" alt="Comp AI" />
            </Link>
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
        </div>
        {loading ? (
          <section className="review-mode" aria-busy="true">
            <div className="review-mode-copy">
              <div className="review-mode-meta">
                <span className="review-mode-pill">Active analysis</span>
                {targetHost ? <span className="review-mode-pill">{targetHost}</span> : null}
              </div>
              <h1 className="review-mode-heading">{reviewModeTitle}</h1>
              <p className="review-mode-body">
                {getLoadingMessage(reviewSelection)}
              </p>

              <div className="review-mode-notes">
                <article className="review-mode-note">
                  <strong>Coverage</strong>
                  <p>Scanning the legal surface area that defines the vendor relationship.</p>
                </article>
                <article className="review-mode-note">
                  <strong>Output</strong>
                  <p>{getOutputDescription(reviewSelection)}</p>
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
                  {results.dpia && (
                    <button
                      type="button"
                      role="tab"
                      aria-selected={visibleResultTab === "dpia"}
                      aria-label="Show D P I A results"
                      className={visibleResultTab === "dpia" ? "results-tab results-tab-active" : "results-tab"}
                      onClick={() => setActiveResultTab("dpia")}
                    >
                      <span>DPIA</span>
                    </button>
                  )}
                  {results.ropa && (
                    <button
                      type="button"
                      role="tab"
                      aria-selected={visibleResultTab === "ropa"}
                      aria-label="Show R O P A results"
                      className={visibleResultTab === "ropa" ? "results-tab results-tab-active" : "results-tab"}
                      onClick={() => setActiveResultTab("ropa")}
                    >
                      <span>ROPA</span>
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
              {visibleResultTab === "terms" && results.terms && (
                <TermsPanel
                  results={results.terms}
                  riskCounts={termsRiskCounts!}
                  getCoverageLabel={getCoverageLabel}
                />
              )}
              {visibleResultTab === "dpa" && results.dpa && (
                <DpaPanel
                  results={results.dpa}
                  checklistCounts={dpaChecklistCounts!}
                  supportingLinkPreviews={supportingLinkPreviews}
                  getCoverageLabel={getCoverageLabel}
                  getSupportingLinkHref={getSupportingLinkHref}
                  getChecklistStatusLabel={getChecklistStatusLabel}
                />
              )}
              {visibleResultTab === "dpia" && results.dpia && (
                <DpiaPanel
                  results={results.dpia}
                  thresholdCounts={dpiaThresholdCounts!}
                  supportingLinkPreviews={supportingLinkPreviews}
                  getSupportingLinkHref={getSupportingLinkHref}
                  getThresholdStatusLabel={getThresholdStatusLabel}
                />
              )}
              {visibleResultTab === "ropa" && results.ropa && (
                <RopaPanel
                  results={results.ropa}
                  fieldCounts={ropaFieldCounts!}
                />
              )}
            </section>
          </section>
        ) : (
          <>
            <header className="hero">
              <div className="hero-copy">
                <h1>Compliant Software Onboarding</h1>
                <p className="hero-body">
                  Screen any software in minutes instead of days.
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
                  <div className="review-type-switch" role="group" aria-label="Review type">
                    <label className={reviewSelection.terms ? "review-type-card review-type-card-selected" : "review-type-card"}>
                      <input
                        type="checkbox"
                        checked={reviewSelection.terms}
                        onChange={() => toggleReviewType("terms")}
                      />
                      <span>
                        <strong>T&amp;C Review</strong>
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
                      </span>
                    </label>
                    <label className={reviewSelection.dpia ? "review-type-card review-type-card-selected" : "review-type-card"}>
                      <input
                        type="checkbox"
                        checked={reviewSelection.dpia}
                        onChange={() => toggleReviewType("dpia")}
                      />
                      <span>
                        <strong>DPIA Screening</strong>
                      </span>
                    </label>
                    <label className={reviewSelection.ropa ? "review-type-card review-type-card-selected" : "review-type-card"}>
                      <input
                        type="checkbox"
                        checked={reviewSelection.ropa}
                        onChange={() => toggleReviewType("ropa")}
                      />
                      <span>
                        <strong>ROPA Synthesis</strong>
                      </span>
                    </label>
                  </div>
                </fieldset>

                <form onSubmit={onSubmit} className="form">
                  <label htmlFor="url">Insert software URL</label>
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
                    placeholder="Optional. Add your business model, customer profile, or legal concerns so the review is prioritized correctly."
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
    </>
  );
}
