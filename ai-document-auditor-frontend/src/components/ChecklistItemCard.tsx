import QueuedRow from "./checklist-item/QueuedRow.tsx";
import ErrorRow from "./checklist-item/ErrorRow.tsx";
import DoneRow from "./checklist-item/DoneRow.tsx";
import type { AuditLog, JobItem } from "../lib/types";

export default function ChecklistItemCard({
  item,
  onViewPage,
}: {
  item: JobItem;
  onViewPage?: (page: number) => void;
}) {
  const label = item.label || item.checklist_item;
  const question = item.checklist_item;
  const anchorId = `item-${item.id}`;

  if (item.status === "queued") {
    return <QueuedRow id={anchorId} label={label} question={question} />;
  }
  if (item.status === "error") {
    return <ErrorRow id={anchorId} label={label} question={question} error={item.error} />;
  }

  return (
    <DoneRow
      id={anchorId}
      label={label}
      question={question}
      result={item.result as AuditLog}
      onViewPage={onViewPage}
    />
  );
}
