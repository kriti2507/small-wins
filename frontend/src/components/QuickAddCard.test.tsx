import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { Topic } from "../types";
import QuickAddCard from "./QuickAddCard";
import QuickAdd from "./QuickAdd";

const noop = () => {};
const topic = (slug: string, name: string, fields: Topic["fields"] = []): Topic => ({
  slug,
  name,
  color: "green",
  layout: "photo-top",
  fields,
});
const topics = [
  topic("workout", "Workout", [
    { key: "title", label: "Title", type: "text", direction: "none" },
    { key: "duration", label: "Duration (min)", type: "number", direction: "higher" },
  ]),
  topic("journal", "Journal"),
  topic("reading", "Reading"),
];

function card(slug: string | null, values: Record<string, string> = {}, suggestions: string[] = []) {
  return renderToStaticMarkup(
    <QuickAddCard
      topics={topics}
      suggestions={suggestions}
      slug={slug}
      onPick={noop}
      values={values}
      onChange={noop}
      preview=""
      onFile={noop}
      onClearFile={noop}
      onSave={noop}
      onDiscard={noop}
      busy={false}
    />,
  );
}

describe("QuickAddCard", () => {
  it("asks for the topic when none was picked, suggested ones first", () => {
    const html = card(null, {}, ["reading"]);
    expect(html).toContain("Which topic?");
    expect(html.indexOf(">Reading<")).toBeLessThan(html.indexOf(">Workout<"));
    expect(html).not.toContain("aria-pressed=\"true\"");
    expect(html).not.toContain(">Save<");
    expect(html).toContain(">Discard<");
  });

  it("shows the picked topic's fields filled from the draft", () => {
    const html = card("workout", { title: "ran 5k", duration: "27", date: "2026-10-29" });
    expect(html).not.toContain("Which topic?");
    expect(html).toMatch(/aria-pressed="true"[^>]*>Workout</);
    expect(html).toContain("Duration (min)");
    expect(html).toContain('value="ran 5k"');
    expect(html).toContain('value="27"');
    expect(html).toContain('value="2026-10-29"');
    expect(html).toContain(">Save<");
  });
});

describe("QuickAdd", () => {
  it("starts as an empty bar with Add disabled", () => {
    const html = renderToStaticMarkup(<QuickAdd topics={topics} onSaved={noop} />);
    expect(html).toContain('placeholder="What&#x27;s your win today?"');
    expect(html).toMatch(/<button[^>]*disabled[^>]*>Add<\/button>/);
    expect(html).not.toContain("quick-add-card");
  });
});
