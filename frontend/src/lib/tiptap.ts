import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import { Figure } from "./figure";

// One extension list shared by the editor and the read-only article view so
// writing and reading render identically. H1 is reserved for the entry title.
export function postExtensions() {
  return [
    StarterKit.configure({ heading: { levels: [2, 3] } }),
    Link.configure({ openOnClick: false }),
    Figure,
  ];
}
