import type { Topic, Entry } from "../types";
import { tileModel } from "../lib/tile";
import { rampFor } from "../lib/palette";

interface Props {
  topic: Topic;
  entries: Entry[];
  colorIndex: number;
}

// Entries newest-first, rendered as tiles. Layout follows the topic's setting;
// each tile shows its uploaded photo or a topic-color block with the initial.
export default function EntryList({ topic, entries, colorIndex }: Props) {
  const ordered = [...entries].sort((a, b) => (a.date < b.date ? 1 : -1));
  const layout = topic.layout === "thumbnail" ? "thumbnail" : "photo-top";
  const ramp = rampFor(topic, colorIndex);
  const gradient = `linear-gradient(135deg, ${ramp[1]}, ${ramp[3]})`;

  return (
    <div className="tile-grid">
      {ordered.map((entry) => {
        const t = tileModel(topic, entry);
        return (
          <article className={`tile ${layout}`} key={entry.id}>
            <div className="photo" style={{ background: gradient }}>
              <span className="initial">{t.initial}</span>
              {t.image && (
                <img
                  src={t.image}
                  alt={t.heading}
                  onError={(e) => e.currentTarget.remove()}
                />
              )}
            </div>
            <div className="body">
              <h4>{t.heading}</h4>
              <span className="meta">{t.meta}</span>
            </div>
          </article>
        );
      })}
    </div>
  );
}
