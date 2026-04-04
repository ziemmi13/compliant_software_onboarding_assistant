export type RiskLevel = "low" | "medium" | "high" | "unknown";
export type DpaChecklistStatus = "missing" | "partial" | "unclear" | "satisfied";

export interface ClauseHighlight {
  title: string;
  rationale: string;
  risk_level: RiskLevel;
  source_url?: string | null;
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

export interface DpaChecklistItem {
  requirement_key: string;
  requirement_title: string;
  status: DpaChecklistStatus;
  rationale: string;
  source_url?: string | null;
}

export interface DpaAnalyzeResponse {
  input_url: string;
  normalized_domain: string;
  summary: string;
  checklist: DpaChecklistItem[];
  source_links: string[];
  supporting_links: string[];
  blocked_links: string[];
  confidence_notes: string[];
  raw_analysis: string;
}

export interface ErrorResponse {
  error: string;
  details: string;
}

export class ApiRequestError extends Error {
  code: string;
  details: string;
  status: number;

  constructor(code: string, details: string, status = 0) {
    super(`${code}: ${details}`);
    this.name = "ApiRequestError";
    this.code = code;
    this.details = details;
    this.status = status;
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export async function analyzeUrl(url: string, companyContext?: string): Promise<AnalyzeResponse> {
  const trimmedContext = companyContext?.trim();
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url,
        company_context: trimmedContext || undefined,
      }),
    });
  } catch (error) {
    throw new ApiRequestError("request_failed", error instanceof Error ? error.message : "Unexpected network error.");
  }

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

    throw new ApiRequestError(errorPayload.error, errorPayload.details, response.status);
  }

  return response.json() as Promise<AnalyzeResponse>;
}

export async function analyzeDpaUrl(url: string, companyContext?: string): Promise<DpaAnalyzeResponse> {
  const trimmedContext = companyContext?.trim();
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/api/analyze-dpa`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url,
        company_context: trimmedContext || undefined,
      }),
    });
  } catch (error) {
    throw new ApiRequestError("request_failed", error instanceof Error ? error.message : "Unexpected network error.");
  }

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

    throw new ApiRequestError(errorPayload.error, errorPayload.details, response.status);
  }

  return response.json() as Promise<DpaAnalyzeResponse>;
}
