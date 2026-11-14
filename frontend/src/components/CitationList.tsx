import type { Citation } from "@/lib/types";

interface CitationListProps {
  citations: Citation[];
}

/** Provenance chips - every factual claim can be traced back to an official document. */
export default function CitationList({ citations }: CitationListProps) {
  if (!citations.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {citations.map((citation) => (
        <span
          key={`${citation.schemeId}-${citation.sectionId}`}
          title={`${citation.title} — ${citation.source}${citation.page ? ` p.${citation.page}` : ""}`}
          className="chip border border-brand-200 bg-brand-50 text-brand-800"
        >
          <span aria-hidden="true">{citation.icon}</span>
          <span className="font-semibold">{citation.citation}</span>
          <span className="hidden font-normal text-brand-700/80 sm:inline">
            · {citation.source}
          </span>
        </span>
      ))}
    </div>
  );
}
