import { memo } from "react";
import { DpiaAnalyzeResponse, LinkPreview } from "../api";

interface DpiaPanelProps {
  results: DpiaAnalyzeResponse;
  thresholdCounts: { detected: number; not_detected: number; insufficient_info: number };
  supportingLinkPreviews: Record<string, LinkPreview>;
  getSupportingLinkHref: (link: string, preview?: LinkPreview | null) => string;
  getThresholdStatusLabel: (item: any) => string;
}

export const DpiaPanel = memo(function DpiaPanel({
  results,
  thresholdCounts,
  supportingLinkPreviews,
  getSupportingLinkHref,
  getThresholdStatusLabel,
}: DpiaPanelProps) {
  if (!results) {
    return null;
  }

  const mapThresholdStatus = (status: string): string => {
    if (status === "detected") return "missing";
    if (status === "not_detected") return "satisfied";
    return "unclear";
  };

  return (
    <section className="result-block">
      <section className="results-topbar simple-topbar">
        <div className="topbar-metrics compact-metrics">
          <span className="topbar-pill topbar-pill-high">Detected {thresholdCounts.detected}</span>
          <span className="topbar-pill topbar-pill-low">Not detected {thresholdCounts.not_detected}</span>
          <span className="topbar-pill topbar-pill-medium">Insufficient {thresholdCounts.insufficient_info}</span>
          <span className={`topbar-pill ${results.dpia_required ? "topbar-pill-high" : "topbar-pill-satisfied"}`}>
            {results.dpia_required ? "DPIA Required" : "DPIA Not Required"}
          </span>
          <span className="topbar-pill topbar-pill-coverage">Score {results.threshold_score}/9</span>
        </div>
      </section>

      <div className="results-primary">
        <article className="card summary-card narrative-card">
          <div className="card-header">
            <h2>DPIA Screening Summary</h2>
          </div>
          <p className="summary-copy">{results.summary}</p>
        </article>

        <article className="card highlights-card narrative-card">
          <div className="card-header">
            <h2>WP29 Threshold Criteria ({results.threshold_score}/9 detected)</h2>
          </div>
          {results.threshold_criteria.length === 0 ? (
            <p>No threshold criteria were evaluated.</p>
          ) : (
            <ul className="highlights editorial-highlights dpa-checklist">
              {results.threshold_criteria.map((item) => (
                <li key={item.criterion_key} className={`highlight-card dpa-checklist-item dpa-checklist-item-${mapThresholdStatus(item.status)}`}>
                  <div className="title-row">
                    <strong>{item.criterion_name}</strong>
                    <span className={`check-status check-status-${mapThresholdStatus(item.status)}`}>
                      {getThresholdStatusLabel(item)}
                    </span>
                  </div>
                  <p>{item.evidence}</p>
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

        {results.dpia_sections.length > 0 && (
          <article className="card highlights-card narrative-card">
            <div className="card-header">
              <h2>Preliminary DPIA</h2>
            </div>
            <ul className="highlights editorial-highlights">
              {[...results.dpia_sections]
                .sort((a, b) => {
                  const order: Record<string, number> = { high: 0, medium: 1, low: 2 };
                  return (order[a.risk_level ?? ""] ?? 3) - (order[b.risk_level ?? ""] ?? 3);
                })
                .map((section) => (
                  <li key={section.section_key} className={`highlight-card highlight-card-${section.risk_level ?? "unknown"}`}>
                    <div className="title-row">
                      <strong>{section.section_title}</strong>
                      {section.risk_level && (
                        <span className={`risk risk-${section.risk_level}`}>{section.risk_level}</span>
                      )}
                    </div>
                    <ul className="dpia-findings">
                      {section.findings.map((f, i) => (
                        <li key={i} className="dpia-finding">
                          <strong>{f.title}:</strong> {f.detail}
                        </li>
                      ))}
                    </ul>
                    {section.source_url && (
                      <p className="highlight-source">
                        Source:{" "}
                        <a href={section.source_url} target="_blank" rel="noreferrer">
                          {section.source_url}
                        </a>
                      </p>
                    )}
                  </li>
                ))}
            </ul>
          </article>
        )}

        <article className="card evidence-card narrative-card">
          <div className="card-header">
            <h2>Evidence &amp; Coverage</h2>
          </div>

          <div className="evidence-section">
            <h3>Source links</h3>
            {results.source_links.length === 0 ? (
              <p className="muted-copy">No source links were confirmed.</p>
            ) : (
              <ul className="source-list evidence-link-list">
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

          {results.supporting_links.length > 0 && (
            <div className="evidence-section">
              <h3>Supporting links</h3>
              <ul className="source-list evidence-link-list">
                {results.supporting_links.map((link) => {
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
        </article>
      </div>
    </section>
  );
});
