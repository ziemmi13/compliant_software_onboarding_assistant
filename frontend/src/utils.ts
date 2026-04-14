export type ReviewSelection = {
  terms: boolean;
  dpa: boolean;
  dpia: boolean;
  ropa: boolean;
};

/**
 * Generic utility to count items by a status/key property
 * @param items Array of items to count
 * @param statusKey The property name to count by
 * @param defaultCounts Default count object with all keys initialized to 0
 * @returns Object with counts for each status value
 */
export function countBy<T, K extends Record<string, number>>(
  items: T[],
  statusKey: keyof T,
  defaultCounts: K
): K {
  return items.reduce((acc, item) => {
    const status = String(item[statusKey]);
    if (status in acc) {
      acc[status as keyof K]++;
    }
    return acc;
  }, { ...defaultCounts });
}

/**
 * Format status/key labels by replacing underscores with spaces
 * @param status Status string with underscores
 * @returns Formatted label with spaces
 */
export function formatStatusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

/**
 * Parse a URL and get the hostname
 * @param url URL string to parse
 * @returns Hostname or the original URL if parsing fails
 */
export function parseUrlHostname(url: string): string {
  try {
    return new URL(url.trim()).hostname;
  } catch {
    return url.trim();
  }
}

/**
 * Parse a URL and get the host (hostname + port if present)
 * @param url URL string to parse
 * @returns Host or null if parsing fails
 */
export function parseUrlHost(url: string): string | null {
  try {
    return url.trim() ? new URL(url.trim()).host : null;
  } catch {
    return null;
  }
}

/**
 * Create a lookup map from an array of objects
 * @param array Array of objects
 * @param key The key property to use as the lookup key
 * @returns Object mapping key values to items
 */
export function createLookupMap<T, K extends PropertyKey>(
  array: T[],
  key: keyof T
): Record<K, T> {
  return array.reduce((acc, item) => {
    acc[String(item[key]) as K] = item;
    return acc;
  }, {} as Record<K, T>);
}

/**
 * Apply constraints to review selection
 * ROPA requires both DPA and DPIA to be selected
 * @param selected Current review selection
 * @param toggled The review type being toggled
 * @returns Updated selection with constraints applied
 */
export function applyReviewConstraints(
  selected: { terms: boolean; dpa: boolean; dpia: boolean; ropa: boolean },
  toggled: keyof typeof selected
): { terms: boolean; dpa: boolean; dpia: boolean; ropa: boolean } {
  const next = { ...selected, [toggled]: !selected[toggled] };

  // ROPA requires both DPA and DPIA
  if (next.ropa && (!next.dpa || !next.dpia)) {
    next.ropa = false;
  }

  // Disable ROPA if DPA or DPIA is disabled
  if (toggled === "dpa" && !next.dpa) {
    next.ropa = false;
  }
  if (toggled === "dpia" && !next.dpia) {
    next.ropa = false;
  }

  return next;
}

/**
 * Compute overall risk level from analysis results
 * Aggregates risk across all modules and returns high/medium/low
 * @param results Analysis results from all modules
 * @returns Risk level or null if no results
 */
export function computeRiskLevel(results: {
  terms: { highlights: Array<{ risk_level: string }> } | null;
  dpa: { checklist: Array<{ status: string }> } | null;
  dpia: { threshold_criteria: Array<{ status: string }> } | null;
  ropa: unknown;
} | null): "high" | "medium" | "low" | null {
  if (!results) return null;

  const highlightLevels: string[] = results.terms?.highlights.map((h) => h.risk_level) ?? [];
  const dpaCounts = { missing: 0, partial: 0, unclear: 0, satisfied: 0 };
  const dpiaCounts = { detected: 0, not_detected: 0, insufficient_info: 0 };

  if (results.dpa?.checklist) {
    results.dpa.checklist.forEach((item) => {
      if (item.status === "missing") dpaCounts.missing++;
      else if (item.status === "partial") dpaCounts.partial++;
      else if (item.status === "unclear") dpaCounts.unclear++;
      else if (item.status === "satisfied") dpaCounts.satisfied++;
    });
  }

  if (results.dpia?.threshold_criteria) {
    results.dpia.threshold_criteria.forEach((item) => {
      if (item.status === "detected") dpiaCounts.detected++;
      else if (item.status === "not_detected") dpiaCounts.not_detected++;
      else if (item.status === "insufficient_info") dpiaCounts.insufficient_info++;
    });
  }

  // Check for high-risk indicators
  const hasHighRiskTerms = highlightLevels.includes("high");
  const hasHighMissingDpa = dpaCounts.missing > 0;
  const hasHighDetectedDpia = dpiaCounts.detected > 0;

  if (hasHighRiskTerms || hasHighMissingDpa || hasHighDetectedDpia) {
    return "high";
  }

  // Check for medium-risk indicators
  const hasMediumRiskTerms = highlightLevels.includes("medium");
  const hasPartialDpa = dpaCounts.partial > 0 || dpaCounts.unclear > 0;
  const hasInsufficientDpia = dpiaCounts.insufficient_info > 0;

  if (hasMediumRiskTerms || hasPartialDpa || hasInsufficientDpia) {
    return "medium";
  }

  // Otherwise low risk
  return "low";
}
