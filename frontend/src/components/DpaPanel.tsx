import { DpaAnalyzeResponse, LinkPreview } from "../api";

interface DpaPanelProps {
  results: DpaAnalyzeResponse;
  checklistCounts: { missing: number; partial: number; unclear: number; satisfied: number };
  supportingLinkPreviews: Record<string, LinkPreview>;
  getCoverageLabel: (sourceLinks: string[], blockedLinks: string[]) => string;
  getSupportingLinkHref: (link: string, preview?: LinkPreview | null) => string;
  getChecklistStatusLabel: (item: any) => string;
}

export function DpaPanel({
  results,
  checklistCounts,
  supportingLinkPreviews,
  getCoverageLabel,
  getSupportingLinkHref,
  getChecklistStatusLabel,
}: DpaPanelProps) {
  if (!results) {
    return null;
  }

  return (
    <section className="result-block">
      <section className="results-topbar simple-topbar">
        <div className="topbar-metrics compact-metrics">
          <span className="topbar-pill topbar-pill-high">Missing {checklistCounts.missing}</span>
          <span className="topbar-pill topbar-pill-partial">Partial {checklistCounts.partial}</span>
          <span className="topbar-pill topbar-pill-satisfied">Satisfied {checklistCounts.satisfied}</span>
          <span className="topbar-pill topbar-pill-coverage">Coverage {getCoverageLabel(results.source_links, results.blocked_links)}</span>
          <span className="topbar-pill topbar-pill-sources">Sources {results.source_links.length}</span>
          {results.supporting_links.length > 0 && <span className="topbar-pill topbar-pill-sources">Support {results.supporting_links.length}</span>}
        </div>
      </section>

      <div className="results-primary">
        <article className="card summary-card narrative-card">
          <div className="card-header">
            <h2>DPA Summary</h2>
          </div>
          <p className="summary-copy">{results.summary}</p>
        </article>

        <article className="card highlights-card narrative-card">
          <div className="card-header">
            <h2>Article 28 Checklist</h2>
          </div>
          {results.checklist.length === 0 ? (
            <p>No checklist items were extracted.</p>
          ) : (
            <ul className="highlights editorial-highlights dpa-checklist">
              {results.checklist.map((item) => (
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
            {results.source_links.length === 0 ? (
              <p className="muted-copy">
                {results.supporting_links.length > 0
                  ? "No confirmed DPA page was found."
                  : "No source links were confirmed."}
              </p>
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
}
