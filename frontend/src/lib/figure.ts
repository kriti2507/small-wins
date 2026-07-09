import { Node } from "@tiptap/core";

export type FigureWidth = "normal" | "wide";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    figure: {
      insertFigure: (attrs: { src: string }) => ReturnType;
      setFigureWidth: (width: FigureWidth) => ReturnType;
    };
  }
}

// An image with an editable caption and a width setting. Serializes as
// {type: "figure", attrs: {src, width}, content: [caption inline nodes]}.
export const Figure = Node.create({
  name: "figure",
  group: "block",
  content: "inline*", // the caption
  isolating: true,

  addAttributes() {
    return {
      src: { default: null },
      width: { default: "normal" },
    };
  },

  parseHTML() {
    return [
      {
        tag: "figure[data-figure]",
        contentElement: "figcaption",
        getAttrs: (el) => ({
          src: (el as HTMLElement).querySelector("img")?.getAttribute("src"),
          width: (el as HTMLElement).dataset.width ?? "normal",
        }),
      },
    ];
  },

  renderHTML({ node }) {
    return [
      "figure",
      { "data-figure": "", "data-width": node.attrs.width },
      ["img", { src: node.attrs.src, alt: "" }],
      ["figcaption", 0],
    ];
  },

  addCommands() {
    return {
      insertFigure:
        ({ src }) =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            attrs: { src, width: "normal" },
          }),
      setFigureWidth:
        (width) =>
        ({ commands }) =>
          commands.updateAttributes(this.name, { width }),
    };
  },
});
