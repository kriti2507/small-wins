import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import TopicForm from "./TopicForm";
import type { Topic } from "../types";

const topic: Topic = {
  slug: "workout",
  name: "Workout",
  color: "green",
  layout: "photo-top",
  fields: [
    { key: "title", label: "Title", type: "text", direction: "none" },
    { key: "duration", label: "Duration", type: "number", direction: "higher" },
  ],
};

const noop = () => {};

function render() {
  return renderToStaticMarkup(<TopicForm topic={topic} onSaved={noop} onCancel={noop} />);
}

describe("TopicForm (edit mode)", () => {
  it("shows the topic's existing fields with their labels and a locked type tag", () => {
    const html = render();
    expect(html).toContain('value="Title"');
    expect(html).toContain('value="Duration"');
    // Existing fields show a type tag, not an editable type <select>.
    expect(html.match(/class="f-type-tag"/g)).toHaveLength(2);
    expect(html).not.toContain('class="f-type"');
  });

  it("disables Move up on the first row and Move down on the last row", () => {
    const html = render();
    expect(html).toMatch(/aria-label="Move Title up"[^>]*disabled/);
    expect(html).toMatch(/aria-label="Move Duration down"[^>]*disabled/);
  });
});
