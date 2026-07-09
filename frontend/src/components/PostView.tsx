import { EditorContent, useEditor } from "@tiptap/react";
import type { PostDoc } from "../types";
import { postExtensions } from "../lib/tiptap";

// Read-only TipTap instance so the article renders exactly like the editor.
export default function PostView({ doc }: { doc: PostDoc }) {
  const editor = useEditor(
    { extensions: postExtensions(), content: doc, editable: false },
    [doc],
  );
  if (!editor) return null;
  return <EditorContent editor={editor} className="post prose" />;
}
