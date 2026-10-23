import SubQuestion from "./SubQuestion.tsx";

export default function QueuedRow({
  id,
  label,
  question,
}: {
  id: string;
  label: string;
  question: string;
}) {
  return (
    <div id={id} className="item-card item-queued">
      <div className="item-header">
        <span className="spinner" aria-hidden="true" />
        <span className="item-question">{label}</span>
      </div>
      <SubQuestion label={label} question={question} />
      <div className="item-status-text">Waiting to run…</div>
    </div>
  );
}
