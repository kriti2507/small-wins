import { Link } from "react-router-dom";
import type { Topic, Entry } from "../types";
import SummaryGraph from "./SummaryGraph";
import { buttonColorFor } from "../lib/palette";

interface AspectData {
  topic: Topic;
  colorIndex: number;
  entries: Entry[];
}

interface Props {
  topicsData: AspectData[];
  onAddMore: () => void;
}

// Grid of per-topic summary boxes plus an "+ Add more" tile.
export default function AspectGrid({ topicsData, onAddMore }: Props) {
  return (
    <div className="aspect-grid">
      {topicsData.map(({ topic, colorIndex, entries }) => {
        const tint = buttonColorFor(topic, colorIndex);
        return (
          <div className="aspect-box" key={topic.slug}>
            <h2>{topic.name}</h2>
            <div className="graph">
              <SummaryGraph topic={topic} entries={entries} colorIndex={colorIndex} />
            </div>
            <Link
              className="btn primary"
              to={`/topic/${topic.slug}`}
              style={{ backgroundColor: tint, borderColor: tint }}
            >
              Learn more
            </Link>
          </div>
        );
      })}
      <div className="aspect-box add-more" onClick={onAddMore}>
        + Add more
      </div>
    </div>
  );
}
