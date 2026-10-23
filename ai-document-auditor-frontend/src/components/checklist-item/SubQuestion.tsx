export default function SubQuestion({ label, question }: { label: string; question: string }) {
  if (question === label) return null;
  return <p className="item-subquestion">{question}</p>;
}
