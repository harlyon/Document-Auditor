import { useState } from "react";
import SubQuestion from "./SubQuestion.tsx";
import { friendlyErrorMessage } from "../../lib/errors.ts";

export default function ErrorRow({
  id,
  label,
  question,
  error,
}: {
  id: string;
  label: string;
  question: string;
  error: string | null;
}) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <div id={id} className="item-card item-error">
      <div className="item-header">
        <span className="item-question">{label}</span>
      </div>
      <SubQuestion label={label} question={question} />
      <div className="item-error-text">
        {error ? friendlyErrorMessage(error) : "This check couldn't be completed."}
      </div>
      {error && (
        <div className="citations">
          <button className="link-button" onClick={() => setShowDetails((v) => !v)}>
            {showDetails ? "Hide" : "Show"} technical details
          </button>
          {showDetails && <pre className="error-details">{error}</pre>}
        </div>
      )}
    </div>
  );
}
