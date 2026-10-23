import { useEffect } from "react";

export default function DocumentViewerModal({
  documentUrl,
  page,
  onClose,
}: {
  documentUrl: string;
  page?: number;
  onClose: () => void;
}) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const src = page ? `${documentUrl}#page=${page}` : documentUrl;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span>Source document{page ? ` — page ${page}` : ""}</span>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>
        <iframe key={src} className="modal-iframe" src={src} title="Source document" />
      </div>
    </div>
  );
}
