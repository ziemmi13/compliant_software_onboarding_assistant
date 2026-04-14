import { FormEvent } from "react";
import type { ReviewSelection } from "../utils";

export interface NewVendorModalProps {
  url: string;
  setUrl: (url: string) => void;
  companyContext: string;
  setCompanyContext: (context: string) => void;
  reviewSelection: ReviewSelection;
  toggleReviewType: (reviewType: keyof ReviewSelection) => void;
  applyPreset: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  onClose: () => void;
  error: string | null;
  loading: boolean;
  contextPresets: Array<{ label: string; value: string }>;
}

export function NewVendorModal({
  url,
  setUrl,
  companyContext,
  setCompanyContext,
  reviewSelection,
  toggleReviewType,
  applyPreset,
  onSubmit,
  onClose,
  error,
  loading,
  contextPresets,
}: NewVendorModalProps) {
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit(e);
    onClose();
  };

  return (
    <>
      <div className="modal-overlay" onClick={onClose} role="presentation" />
      <div className="modal-dialog" role="alertdialog" aria-modal="true" aria-labelledby="modal-title" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 id="modal-title">New Vendor Analysis</h2>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label htmlFor="modal-url">Vendor URL</label>
            <input
              id="modal-url"
              type="url"
              placeholder="https://example.com"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>Select analyses</label>
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
          </div>

          <div className="form-group">
            <label htmlFor="modal-context">Company context (optional)</label>
            <textarea
              id="modal-context"
              className="context-input"
              placeholder="Add your business model, customer profile, or legal concerns so the review is prioritized correctly."
              value={companyContext}
              onChange={(e) => setCompanyContext(e.target.value)}
              rows={3}
            />
            <div className="preset-group">
              <p className="preset-label">Quick presets</p>
              <div className="preset-list">
                {contextPresets.map((preset) => (
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
          </div>

          {error && <p className="error">{error}</p>}

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" disabled={loading}>
              {loading ? "Analyzing..." : "Run Analysis"}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
