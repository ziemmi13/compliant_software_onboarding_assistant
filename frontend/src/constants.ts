/**
 * Module label mapping for display names
 */
export const MODULE_LABELS: Record<string, string> = {
  terms: "T&C",
  dpa: "DPA",
  dpia: "DPIA",
  ropa: "ROPA",
};

/**
 * Error recovery hints for each module type
 */
export const ERROR_HINTS: Record<string, string> = {
  terms: "a direct terms URL",
  dpa: "a direct DPA URL",
  dpia: "a direct privacy policy URL",
  ropa: "rerunning the DPA and DPIA review",
};

/**
 * Loading messages for different review selections
 */
export const LOADING_MESSAGES: Record<string, string> = {
  "ropa": "COMPL.AI is running the DPA and DPIA reviews first, then synthesizing them into an Article 30 record of processing activities.",
  "dpia": "COMPL.AI is screening the vendor's data processing against the WP29 threshold criteria and preparing a DPIA assessment.",
  "terms-dpa": "COMPL.AI is running both the contractual review and the DPA review before assembling the combined report.",
  "dpa": "COMPL.AI is reviewing the DPA package and linked annexes before generating an Article 28 checklist.",
  "terms": "COMPL.AI is running a focused legal intake pass before generating the final summary and ranked highlights.",
};

/**
 * Output description for different review selections
 */
export const OUTPUT_DESCRIPTIONS: Record<string, string> = {
  "ropa": "Preparing a registry-style Article 30 record from the DPA checklist and DPIA findings.",
  "terms-dpa": "Preparing a combined report with ranked T&C issues and a cited DPA checklist.",
  "dpa": "Preparing a structured Article 28 checklist with cited privacy control findings.",
  "terms": "Preparing a concise T&C report with ranked issues and linked source pages.",
  "default": "Preparing analysis results.",
};
