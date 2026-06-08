import type { TimelineEvent } from "../../types/domain";
import { formatDateTime } from "../../utils/format";
import { severityColor } from "../../utils/severity";
import { EmptyState } from "../common/StateBlocks";
import { ClockIcon } from "../icons";

export function CaseTimeline({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) {
    return (
      <EmptyState
        icon={<ClockIcon size={26} className="state-icon" />}
        title="No timeline events"
        detail="Timeline events populate as entities and detections are correlated for this case."
      />
    );
  }

  const sorted = [...events].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
  );

  return (
    <div className="flex-col" style={{ padding: "var(--sp-3) var(--sp-4)" }}>
      {sorted.map((event, idx) => (
        <div key={event.event_id} className="flex gap-3" style={{ position: "relative" }}>
          <div className="flex-col items-center" style={{ width: 14, flex: "none" }}>
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                marginTop: 5,
                background: event.severity ? severityColor(event.severity) : "var(--accent-500)",
                boxShadow: "0 0 0 3px var(--bg-panel)",
                flex: "none",
              }}
            />
            {idx < sorted.length - 1 && (
              <span style={{ flex: 1, width: 1, background: "var(--border-default)" }} />
            )}
          </div>
          <div style={{ paddingBottom: "var(--sp-4)", minWidth: 0 }}>
            <div className="flex items-center gap-2 wrap">
              <span style={{ fontWeight: 600, fontSize: 12.5 }}>{event.title}</span>
              <span className="badge badge-outline">{event.category}</span>
              {event.source && <span className="text-tertiary" style={{ fontSize: 11 }}>{event.source}</span>}
            </div>
            <div className="text-tertiary" style={{ fontSize: 11, marginTop: 2 }}>
              {formatDateTime(event.timestamp)}
            </div>
            <div style={{ fontSize: 12, marginTop: 4, color: "var(--text-secondary)" }}>
              {event.description}
            </div>
            {event.technique_ids && event.technique_ids.length > 0 && (
              <div className="flex gap-1 wrap" style={{ marginTop: 6 }}>
                {event.technique_ids.map((t) => (
                  <span key={t} className="tag-chip">
                    {t}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
