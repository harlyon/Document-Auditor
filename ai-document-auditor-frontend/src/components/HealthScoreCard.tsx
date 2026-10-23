import type { HealthScore } from "../lib/scoring";

function scoreTier(score: number): "good" | "warn" | "bad" {
  if (score >= 80) return "good";
  if (score >= 50) return "warn";
  return "bad";
}

export default function HealthScoreCard({ health }: { health: HealthScore }) {
  const { score, passed, failed, contradictory, notFound, applicableTotal } = health;

  return (
    <div className="health-score-card">
      <div className={`health-score-value health-score-${score === null ? "none" : scoreTier(score)}`}>
        {score === null ? "—" : `${score}%`}
      </div>
      <div className="health-score-details">
        <div className="health-score-label">
          {score === null
            ? "No scoreable checks yet"
            : `${passed} of ${applicableTotal} applicable checks passed`}
        </div>
        <div className="health-score-breakdown">
          {failed > 0 && <span className="health-score-chip health-score-chip-bad">{failed} failed</span>}
          {contradictory > 0 && (
            <span className="health-score-chip health-score-chip-bad">{contradictory} contradictory</span>
          )}
          {notFound > 0 && (
            <span className="health-score-chip health-score-chip-neutral">{notFound} not applicable</span>
          )}
        </div>
      </div>
    </div>
  );
}
