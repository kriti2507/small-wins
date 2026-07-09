import { Node } from "@tiptap/core";
import { TextSelection } from "@tiptap/pm/state";

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

  addKeyboardShortcuts() {
    return {
      // Enter in the caption exits into a new paragraph below the figure
      // (splitting is impossible because the node is isolating).
      Enter: () => {
        const { state } = this.editor;
        const { $from } = state.selection;
        if (!state.selection.empty || $from.parent.type.name !== this.name) {
          return false;
        }
        return this.editor.commands.command(({ tr, dispatch }) => {
          const after = tr.selection.$from.after();
          if (dispatch) {
            tr.insert(after, state.schema.nodes.paragraph.create());
            tr.setSelection(TextSelection.create(tr.doc, after + 1));
            tr.scrollIntoView();
          }
          return true;
        });
      },
    };
  },
});
