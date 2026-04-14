import { memo } from "react";
import { RopaAnalyzeResponse } from "../api";

interface RopaPanelProps {
  results: RopaAnalyzeResponse;
  fieldCounts: { populated: number; partial: number; placeholder: number };
}

export const RopaPanel = memo(function RopaPanel({ results, fieldCounts }: RopaPanelProps) {
  if (!results) {
    return null;
  }

  return (
    <section className="result-block">
      <section className="results-topbar simple-topbar">
        <div className="topbar-metrics compact-metrics">
          <span className="topbar-pill topbar-pill-satisfied">Populated {fieldCounts.populated}</span>
          <span className="topbar-pill topbar-pill-partial">Partial {fieldCounts.partial}</span>
          <span className="topbar-pill topbar-pill-coverage">Placeholders {fieldCounts.placeholder}</span>
          <span className="topbar-pill topbar-pill-sources">Completeness {results.completeness_score}%</span>
        </div>
      </section>

      <div className="results-primary">
        <article className="card summary-card narrative-card">
          <div className="card-header">
            <h2>ROPA Summary</h2>
          </div>
          <p className="summary-copy">{results.summary}</p>
          <div className="ropa-summary-meta">
            <span className="topbar-pill topbar-pill-coverage">Vendor {results.vendor_name}</span>
            <span className="topbar-pill topbar-pill-sources">Article 30 record</span>
          </div>
        </article>

        <article className="card highlights-card narrative-card">
          <div className="card-header">
            <h2>Record of Processing Activities</h2>
          </div>
          <div className="ropa-field-list">
            {results.ropa_fields.map((field) => (
              <article key={field.field_key} className={`ropa-field-card ropa-field-card-${field.status}`}>
                <div className="ropa-field-header">
                  <div>
                    <h3>{field.field_title}</h3>
                    <p>{field.article_ref}</p>
                  </div>
                  <span className={`ropa-field-status ropa-field-status-${field.status}`}>{field.status}</span>
                </div>

                {field.entries.length === 0 ? (
                  <p className="muted-copy">No structured entries were returned for this field.</p>
                ) : (
                  <ul className="ropa-entry-list">
                    {field.entries.map((entry, index) => (
                      <li key={`${field.field_key}-${index}`} className="ropa-entry-card">
                        <strong>{entry.title}</strong>
                        <p>{entry.detail}</p>
                      </li>
                    ))}
                  </ul>
                )}

                {field.source_notes.length > 0 && (
                  <div className="ropa-source-notes">
                    <h4>Source notes</h4>
                    <ul>
                      {field.source_notes.map((note, index) => (
                        <li key={`${field.field_key}-note-${index}`}>{note}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </article>
            ))}
          </div>
        </article>

        <article className="card evidence-card narrative-card">
          <div className="card-header">
            <h2>Completeness</h2>
          </div>
          <div className="ropa-completeness-bar" aria-hidden="true">
            <div className="ropa-completeness-fill" style={{ width: `${results.completeness_score}%` }} />
          </div>
          <p className="summary-copy ropa-completeness-copy">
            {results.completeness_score}% of the Article 30 record is populated from the available DPA and DPIA material.
          </p>
          {results.confidence_notes.length > 0 && (
            <ul className="source-list ropa-confidence-list">
              {results.confidence_notes.map((note, index) => (
                <li key={`confidence-${index}`}>{note}</li>
              ))}
            </ul>
          )}
        </article>
      </div>
    </section>
  );
});
