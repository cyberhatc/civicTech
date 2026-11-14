import type { ResponseCard } from "@/lib/types";

function StatusPill({ status }: { status?: string }) {
  if (!status) return null;
  const tone: Record<string, string> = {
    NEW: "bg-info-100 text-info-600",
    IN_PROGRESS: "bg-saffron-100 text-saffron-700",
    RESOLVED: "bg-brand-100 text-brand-700",
    REJECTED: "bg-ink-100 text-ink-600",
    ESCALATED: "bg-alert-500/15 text-alert-700",
  };
  const labels: Record<string, string> = {
    NEW: "नई",
    IN_PROGRESS: "कार्यवाही में",
    RESOLVED: "समाधान",
    REJECTED: "अस्वीकृत",
    ESCALATED: "वर्गीकृत",
  };
  return (
    <span className={`chip ${tone[status] ?? "bg-ink-100 text-ink-600"}`}>
      {labels[status] ?? status}
    </span>
  );
}

interface ReplyCardProps {
  card: ResponseCard;
  onAction?: (action: string, payload: string) => void;
}

/** Renders one structured result card (scheme, ticket, application, documents...). */
export default function ReplyCard({ card, onAction }: ReplyCardProps) {
  return (
    <article className="surface animate-float-up overflow-hidden">
      <header className="flex items-start gap-3 border-b border-ink-100 bg-ink-50/70 px-4 py-3">
        <span aria-hidden="true" className="text-2xl leading-none">
          {card.icon || "📄"}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-[15px] font-bold text-ink-900">{card.title}</h3>
          {card.subtitle && (
            <p className="truncate text-xs font-medium text-ink-500">{card.subtitle}</p>
          )}
        </div>
        {card.status && <StatusPill status={card.status} />}
      </header>

      {card.body && (
        <p className="px-4 pt-3 text-sm leading-relaxed text-ink-700">{card.body}</p>
      )}

      {card.fields && card.fields.length > 0 && (
        <dl className="grid grid-cols-1 gap-px bg-ink-100 px-0 py-0">
          {card.fields.map((field) => (
            <div
              key={field.label}
              className="flex flex-col gap-0.5 bg-white px-4 py-2.5 sm:flex-row sm:gap-4"
            >
              <dt className="shrink-0 text-xs font-semibold uppercase tracking-wide text-ink-400 sm:w-40">
                {field.label}
              </dt>
              <dd className="text-sm font-medium text-ink-800">{field.value || "—"}</dd>
            </div>
          ))}
        </dl>
      )}

      {card.timeline && card.timeline.length > 0 && (
        <ol className="space-y-0 border-t border-ink-100 px-4 py-3">
          {card.timeline.map((event, index) => (
            <li key={`${event.date}-${index}`} className="flex gap-3 py-1.5">
              <span
                aria-hidden="true"
                className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                  event.status === "SUCCESS" ? "bg-brand-500" : "bg-saffron-500"
                }`}
              />
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink-800">
                  {event.label_hi || event.label}
                </p>
                <p className="text-[11px] text-ink-400">{event.date}</p>
              </div>
            </li>
          ))}
        </ol>
      )}

      {card.actions && card.actions.length > 0 && (
        <div className="flex flex-wrap gap-2 border-t border-ink-100 px-4 py-3">
          {card.actions.map((action) => (
            <button
              key={`${action.action}-${action.payload}`}
              type="button"
              onClick={() => onAction?.(action.action, action.payload)}
              className="btn btn-ghost !min-h-10 !px-4 !text-sm"
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
