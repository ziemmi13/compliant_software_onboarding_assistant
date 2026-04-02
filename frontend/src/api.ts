export type RiskLevel = "low" | "medium" | "high" | "unknown";

export interface ClauseHighlight {
  title: string;
  rationale: string;
  risk_level: RiskLevel;
}

export interface AnalyzeResponse {
  input_url: string;
  normalized_domain: string;
  summary: string;
  highlights: ClauseHighlight[];
  source_links: string[];
  blocked_links: string[];
  confidence_notes: string[];
  raw_analysis: string;
}

export interface ErrorResponse {
  error: string;
  details: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export async function analyzeUrl(url: string, companyContext?: string): Promise<AnalyzeResponse> {
  const trimmedContext = companyContext?.trim();
  const response = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      url,
      company_context: trimmedContext || undefined,
    }),
  });

  if (!response.ok) {
    let errorPayload: ErrorResponse = {
      error: "request_failed",
      details: "Unexpected error.",
    };

    try {
      const parsed = await response.json();
      if (parsed?.detail?.error) {
        errorPayload = parsed.detail;
      }
    } catch {
      // Keep fallback error payload.
    }

    throw new Error(`${errorPayload.error}: ${errorPayload.details}`);
  }

  return response.json() as Promise<AnalyzeResponse>;
}
