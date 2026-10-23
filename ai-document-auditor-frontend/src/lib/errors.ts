export function friendlyErrorMessage(raw: string): string {
  const lower = raw.toLowerCase();

  if (lower.includes("429") || lower.includes("resourceexhausted") || lower.includes("quota")) {
    return "The AI service is temporarily busy. Try re-running this check in a moment.";
  }
  if (lower.includes("validation error") || lower.includes("pydantic") || lower.includes("int_parsing")) {
    return "The AI returned a response in an unexpected format and it couldn't be verified.";
  }
  if (lower.includes("failed after") && lower.includes("attempts")) {
    return "This check couldn't be verified after several attempts.";
  }
  return "This check couldn't be completed.";
}
