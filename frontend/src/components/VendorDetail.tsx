import { TermsPanel } from "./TermsPanel";
import { DpaPanel } from "./DpaPanel";
import { DpiaPanel } from "./DpiaPanel";
import { RopaPanel } from "./RopaPanel";
import { computeRiskLevel, formatStatusLabel, countBy } from "../utils";
import type { LinkPreview, AnalyzeResponse, DpaAnalyzeResponse, DpiaAnalyzeResponse, RopaAnalyzeResponse, DpaChecklistItem, DpiaThresholdItem } from "../api";

export type ResultTab = "terms" | "dpa" | "dpia" | "ropa";

export interface SavedSession {
  id: string;
  createdAt: string;
  url: string;
  normalizedDomain: string;
  name?: string;
  companyContext: string;
  reviewSelection: { terms: boolean; dpa: boolean; dpia: boolean; ropa: boolean };
  results: {
    terms: AnalyzeResponse | null;
    dpa: DpaAnalyzeResponse | null;
    dpia: DpiaAnalyzeResponse | null;
    ropa: RopaAnalyzeResponse | null;
  };
  activeResultTab: ResultTab;
  status?: "processing" | "complete" | "error";
  decision?: "approved" | "conditional" | "rejected";
}

export interface VendorDetailProps {
  session: SavedSession;
  showFullReport: boolean;
  setShowFullReport: (v: boolean) => void;
  activeResultTab: ResultTab;
  setActiveResultTab: (tab: ResultTab) => void;
  onDecisionChange: (decision: "approved" | "conditional" | "rejected") => void;
  onReanalyze: () => void;
  supportingLinkPreviews: Record<string, LinkPreview>;
}

function formatSessionDate(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function getSupportingLinkHref(link: string, preview?: LinkPreview | null): string {
  if (preview) {
    return preview.resolved_url || link;
  }
  try {
    return new URL(link).toString();
  } catch {
    return link;
  }
}

function getChecklistStatusLabel(item: DpaChecklistItem): string {
  return formatStatusLabel(item.status);
}

function getThresholdStatusLabel(item: DpiaThresholdItem): string {
  return formatStatusLabel(item.status);
}

export function VendorDetail({
  session,
  showFullReport,
  setShowFullReport,
  activeResultTab,
  setActiveResultTab,
  onDecisionChange,
  onReanalyze,
  supportingLinkPreviews,
}: VendorDetailProps) {
  const { results, decision } = session;
  const riskLevel = computeRiskLevel(results);
  const formattedDate = formatSessionDate(session.createdAt);

  // Collect top 3 findings from all results
  const allFindings: Array<{ title: string; source?: string; severity: string }> = [];

  if (results.terms?.highlights) {
    results.terms.highlights.slice(0, 2).forEach((h) => {
      allFindings.push({ title: h.title, source: h.source_url || undefined, severity: h.risk_level });
    });
  }

  if (results.dpa?.checklist && allFindings.length < 3) {
    const dpaItems = results.dpa.checklist.filter((item) => item.status === "missing" || item.status === "unclear");
    dpaItems.slice(0, 3 - allFindings.length).forEach((item) => {
      allFindings.push({
        title: item.requirement_title,
        source: item.source_url || undefined,
        severity: item.status,
      });
    });
  }

  const topFindings = allFindings.slice(0, 3);

  // Available tabs based on results
  const availableTabs: ResultTab[] = [];
  if (results.terms) availableTabs.push("terms");
  if (results.dpa) availableTabs.push("dpa");
  if (results.dpia) availableTabs.push("dpia");
  if (results.ropa) availableTabs.push("ropa");

  // Roupa field counts for the panel
  const ropaFieldCounts =
    results.ropa?.ropa_fields.reduce(
      (acc, field) => {
        acc[field.status]++;
        return acc;
      },
      { populated: 0, partial: 0, placeholder: 0 }
    ) || { populated: 0, partial: 0, placeholder: 0 };

  return (
    <section className="vendor-detail">
      {/* Compact Risk Summary Card */}
      <div className="risk-summary-card">
        <div className="risk-summary-header">
          <div className="risk-summary-title">
            <h2>{session.name || session.normalizedDomain}</h2>
            {riskLevel && <span className={`risk-badge risk-badge-${riskLevel}`}>{riskLevel.toUpperCase()} RISK</span>}
          </div>
          <div className="risk-summary-meta">
            <span className="review-date">{formattedDate}</span>
          </div>
        </div>

        {/* Decision Buttons */}
        <div className="decision-buttons">
          <button
            className={`decision-btn ${decision === "approved" ? "decision-btn-active" : ""}`}
            onClick={() => onDecisionChange("approved")}
            title="Mark as approved"
          >
            Approve
          </button>
          <button
            className={`decision-btn decision-btn-conditional ${decision === "conditional" ? "decision-btn-active" : ""}`}
            onClick={() => onDecisionChange("conditional")}
            title="Mark as conditional approval"
          >
            Conditional
          </button>
          <button
            className={`decision-btn decision-btn-reject ${decision === "rejected" ? "decision-btn-active" : ""}`}
            onClick={() => onDecisionChange("rejected")}
            title="Mark as rejected"
          >
            Reject
          </button>
        </div>

        {/* Top Findings */}
        {topFindings.length > 0 && (
          <div className="risk-findings">
            <p className="findings-label">Top findings:</p>
            {topFindings.map((finding, idx) => (
              <div key={idx} className="finding-item">
                <span className={`finding-severity finding-severity-${finding.severity}`}>
                  {finding.severity.replace(/_/g, " ")}
                </span>
                <span className="finding-title">{finding.title}</span>
              </div>
            ))}
          </div>
        )}

        {/* Re-analyze Button */}
        <div className="risk-summary-actions">
          <button className="btn-secondary" onClick={onReanalyze}>
            Re-analyze
          </button>
        </div>
      </div>

      {/* Full Report Toggle */}
      {availableTabs.length > 0 && (
        <>
          <button
            className="full-report-toggle"
            onClick={() => setShowFullReport(!showFullReport)}
            aria-expanded={showFullReport}
          >
            <span>{showFullReport ? "▼ Hide" : "▶ Show"} Full Report</span>
          </button>

          {/* Full Report Section */}
          {showFullReport && (
            <section className="results results-stack">
              {/* Tab List */}
              {availableTabs.length > 1 && (
                <div className="results-tablist" role="tablist" aria-label="Result sections">
                  {availableTabs.map((tab) => (
                    <button
                      key={tab}
                      type="button"
                      role="tab"
                      aria-selected={activeResultTab === tab}
                      className={activeResultTab === tab ? "results-tab results-tab-active" : "results-tab"}
                      onClick={() => setActiveResultTab(tab)}
                    >
                      {tab === "terms" && "T&C"}
                      {tab === "dpa" && "DPA"}
                      {tab === "dpia" && "DPIA"}
                      {tab === "ropa" && "ROPA"}
                    </button>
                  ))}
                </div>
              )}

              {/* Tab Content */}
              {activeResultTab === "terms" && results.terms && (() => {
                const riskCounts = countBy(results.terms.highlights, "risk_level", { high: 0, medium: 0, low: 0, unknown: 0 });
                const getCoverageLabel = (sourceLinks: string[], blockedLinks: string[]): string => {
                  if (blockedLinks.length > 0) {
                    return sourceLinks.length > 0 ? "Partial" : "Blocked";
                  }
                  return sourceLinks.length > 0 ? "Good" : "Limited";
                };
                return <TermsPanel results={results.terms} riskCounts={riskCounts} getCoverageLabel={getCoverageLabel} />;
              })()}

              {activeResultTab === "dpa" && results.dpa && (() => {
                const checklistCounts = countBy(results.dpa.checklist, "status", { missing: 0, partial: 0, unclear: 0, satisfied: 0 });
                const getCoverageLabel = (sourceLinks: string[], blockedLinks: string[]): string => {
                  if (blockedLinks.length > 0) {
                    return sourceLinks.length > 0 ? "Partial" : "Blocked";
                  }
                  return sourceLinks.length > 0 ? "Good" : "Limited";
                };
                return (
                  <DpaPanel
                    results={results.dpa}
                    checklistCounts={checklistCounts}
                    getCoverageLabel={getCoverageLabel}
                    supportingLinkPreviews={supportingLinkPreviews}
                    getSupportingLinkHref={getSupportingLinkHref}
                    getChecklistStatusLabel={getChecklistStatusLabel}
                  />
                );
              })()}

              {activeResultTab === "dpia" && results.dpia && (() => {
                const thresholdCounts = countBy(results.dpia.threshold_criteria, "status", { detected: 0, not_detected: 0, insufficient_info: 0 });
                return (
                  <DpiaPanel
                    results={results.dpia}
                    thresholdCounts={thresholdCounts}
                    supportingLinkPreviews={supportingLinkPreviews}
                    getSupportingLinkHref={getSupportingLinkHref}
                    getThresholdStatusLabel={getThresholdStatusLabel}
                  />
                );
              })()}

              {activeResultTab === "ropa" && results.ropa && (() => {
                return (
                  <RopaPanel
                    results={results.ropa}
                    fieldCounts={ropaFieldCounts}
                  />
                );
              })()}
            </section>
          )}
        </>
      )}
    </section>
  );
}
