import { FormEvent, useEffect, useState } from "react";

import { AnalyzeResponse, analyzeUrl } from "./api";

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

const LOADING_STAGES = ["Finding legal pages", "Analyzing terms", "Ranking business risks"];

function countHighlightsByRisk(result: AnalyzeResponse) {
  return result.highlights.reduce(
    (counts, item) => {
      counts[item.risk_level] += 1;
      return counts;
    },
    { high: 0, medium: 0, low: 0, unknown: 0 }
  );
}

export default function App() {
  const [url, setUrl] = useState("");
  const [companyContext, setCompanyContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStageIndex, setLoadingStageIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);

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
      const analysis = await analyzeUrl(url.trim(), companyContext);
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

  const riskCounts = result ? countHighlightsByRisk(result) : null;
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
            <button type="button" className="top-tab">
              Settings
            </button>
          </nav>
        </header>

        <header className="hero">
          <div className="hero-copy">
            <h1>Compliant Software Onboarding</h1>
            <p className="hero-body">
              Screen any software in minutes, not hours.
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

            <form onSubmit={onSubmit} className="form">
              <label htmlFor="url">Website URL</label>
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

            {loading && (
              <div className="inline-loading">
                <p className="loading-lead">The agent is moving through the review workflow.</p>
                <ol className="loading-steps compact-loading-steps">
                  {LOADING_STAGES.map((stage, index) => (
                    <li key={stage} className={index <= loadingStageIndex ? "loading-step-active" : ""}>
                      <span className="loading-step-index">0{index + 1}</span>
                      <span>{stage}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {!loading && !result && !error && (
              <div className="inline-note">
                <p>
                  Enter a target URL and optional company context to generate a concise compliance brief with ranked contractual risks.
                </p>
              </div>
            )}

            {error && <p className="error">{error}</p>}
          </section>
        </section>

        {result && (
          <section className="results">
            <section className="results-topbar simple-topbar">
              <div>
                <p className="section-kicker">Analysis brief</p>
                <h2>{result.normalized_domain}</h2>
              </div>
              <div className="topbar-metrics compact-metrics">
                <span className="topbar-pill topbar-pill-high">High {riskCounts?.high ?? 0}</span>
                <span className="topbar-pill">Coverage {coverageLabel}</span>
                <span className="topbar-pill">Sources {result.source_links.length}</span>
                {result.blocked_links.length > 0 && <span className="topbar-pill">Blocked {result.blocked_links.length}</span>}
              </div>
            </section>

            <div className="results-primary">
              <article className="card summary-card narrative-card">
                <div className="card-header">
                  <h2>T&amp;C Summary</h2>
                </div>
                <p className="summary-copy">{result.summary}</p>
              </article>

              <article className="card highlights-card narrative-card">
                <div className="card-header">
                  <h2>Key Highlights</h2>
                </div>
                {result.highlights.length === 0 ? (
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
