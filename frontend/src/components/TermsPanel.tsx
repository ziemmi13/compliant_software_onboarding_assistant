import { memo } from "react";
import { AnalyzeResponse } from "../api";

interface TermsPanelProps {
  results: AnalyzeResponse;
  riskCounts: { high: number; medium: number; low: number; unknown: number };
  getCoverageLabel: (sourceLinks: string[], blockedLinks: string[]) => string;
}

export const TermsPanel = memo(function TermsPanel({ results, riskCounts, getCoverageLabel }: TermsPanelProps) {
  if (!results) {
    return null;
  }

  return (
    <section className="result-block">
      <section className="results-topbar simple-topbar">
        <div className="topbar-metrics compact-metrics">
          <span className="topbar-pill topbar-pill-high">High {riskCounts.high}</span>
          <span className="topbar-pill topbar-pill-medium">Medium {riskCounts.medium}</span>
          <span className="topbar-pill topbar-pill-low">Low {riskCounts.low}</span>
          <span className="topbar-pill topbar-pill-coverage">Coverage {getCoverageLabel(results.source_links, results.blocked_links)}</span>
          <span className="topbar-pill topbar-pill-sources">Sources {results.source_links.length}</span>
        </div>
      </section>

      <div className="results-primary">
        <article className="card summary-card narrative-card">
          <div className="card-header">
            <h2>T&amp;C Summary</h2>
          </div>
          <p className="summary-copy">{results.summary}</p>
        </article>

        <article className="card highlights-card narrative-card">
          <div className="card-header">
            <h2>Key Highlights</h2>
          </div>
          {results.highlights.length === 0 ? (
            <p>No highlights were extracted.</p>
          ) : (
            <ul className="highlights editorial-highlights">
              {results.highlights.map((item, index) => (
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
            {results.source_links.length === 0 ? (
              <p className="muted-copy">No source links were confirmed.</p>
            ) : (
              <ul className="source-list">
                {results.source_links.map((link) => (
                  <li key={link}>
                    <a href={link} target="_blank" rel="noreferrer">
                      {link}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </article>
      </div>
    </section>
  );
});
