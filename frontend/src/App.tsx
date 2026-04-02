import { FormEvent, useState } from "react";

import { AnalyzeResponse, analyzeUrl } from "./api";

export default function App() {
  const [url, setUrl] = useState("");
  const [companyContext, setCompanyContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);

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

  return (
    <main className="page">
      <header className="hero">
        <p className="eyebrow">Legal Scout</p>
        <h1>Terms analysis from your agent system</h1>
        <p>
          Submit a website URL to discover Terms and Conditions pages and receive a focused risk-oriented summary.
        </p>
      </header>

      <section className="panel">
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
            placeholder="B2B SaaS for HR teams. Handles employee PII. Most concerned about liability, indemnity, data processing, and termination terms."
            value={companyContext}
            onChange={(e) => setCompanyContext(e.target.value)}
            rows={5}
          />
          <p className="field-note">
            Add business context, product details, or specific legal concerns so the analysis can prioritize the most relevant clauses.
          </p>
        </form>

        {error && <p className="error">{error}</p>}
      </section>

      {result && (
        <section className="results">
          <div className="results-primary">
            <article className="card dialog-card">
              <h2>T&amp;C Summary</h2>
              <p>{result.summary}</p>
            </article>

            <article className="card dialog-card">
              <h2>Key Highlights</h2>
              {result.highlights.length === 0 ? (
                <p>No highlights were extracted.</p>
              ) : (
                <ul className="highlights">
                  {result.highlights.map((item, index) => (
                    <li key={`${item.title}-${index}`}>
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
          </div>

          <article className="card">
            <h2>Source links</h2>
            <ul>
              {result.source_links.map((link) => (
                <li key={link}>
                  <a href={link} target="_blank" rel="noreferrer">
                    {link}
                  </a>
                </li>
              ))}
            </ul>
            {result.blocked_links.length > 0 && (
              <>
                <h3>Blocked links</h3>
                <ul>
                  {result.blocked_links.map((link) => (
                    <li key={link}>{link}</li>
                  ))}
                </ul>
              </>
            )}
          </article>
        </section>
      )}
    </main>
  );
}
