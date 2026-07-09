import { useRef, useState } from "react";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import type { PostDoc } from "../types";
import type { FigureWidth } from "../lib/figure";
import { uploadImage } from "../api/client";
import { postExtensions } from "../lib/tiptap";

interface Props {
  initial: PostDoc;
  saving: boolean;
  onSave: (doc: PostDoc) => void;
  onCancel: () => void;
}

// WYSIWYG post editor: fixed toolbar + one continuous TipTap document.
// Markdown shortcuts (**bold**, ## heading, > quote, - list) come from
// StarterKit's input rules.
export default function RichPostEditor({ initial, saving, onSave, onCancel }: Props) {
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const editor = useEditor({
    extensions: postExtensions(),
    content: initial,
    autofocus: "end",
  });

  if (!editor) return null;

  function onPickPhoto(file: File) {
    setUploadError(null);
    setUploading(true);
    uploadImage(file)
      .then(({ url }) => {
        if (editor!.isDestroyed) return;
        editor!.chain().focus().insertFigure({ src: url }).run();
      })
      .catch((err) => setUploadError(err.message || "Could not upload photo."))
      .finally(() => setUploading(false));
  }

  return (
    <div className="post-editor">
      <Toolbar editor={editor} onPhotoClick={() => fileInput.current?.click()} />
      {uploadError && <p className="upload-error">{uploadError}</p>}
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onPickPhoto(file);
          e.target.value = "";
        }}
      />
      <EditorContent editor={editor} className="post prose" />
      <div className="post-editor-actions">
        <span className="spacer" />
        <button type="button" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
        <button
          type="button"
          className="primary"
          disabled={saving || uploading}
          onClick={() => onSave(editor.getJSON() as unknown as PostDoc)}
        >
          {saving ? "Saving…" : uploading ? "Uploading…" : "Save"}
        </button>
      </div>
    </div>
  );
}

function Toolbar({ editor, onPhotoClick }: { editor: Editor; onPhotoClick: () => void }) {
  const chain = () => editor.chain().focus();

  function editLink() {
    const prev = editor.getAttributes("link").href as string | undefined;
    const url = window.prompt("Link URL (empty to remove)", prev ?? "https://");
    if (url === null) return;
    if (url === "") chain().extendMarkRange("link").unsetLink().run();
    else chain().extendMarkRange("link").setLink({ href: url }).run();
  }

  const figureWidth = editor.getAttributes("figure").width as FigureWidth | undefined;

  const btn = (label: string, title: string, active: boolean, onClick: () => void) => (
    <button
      type="button"
      title={title}
      className={active ? "on" : ""}
      onMouseDown={(e) => e.preventDefault()} // keep the editor selection
      onClick={onClick}
    >
      {label}
    </button>
  );

  return (
    <div className="post-toolbar">
      {btn("B", "Bold", editor.isActive("bold"), () => chain().toggleBold().run())}
      {btn("I", "Italic", editor.isActive("italic"), () => chain().toggleItalic().run())}
      {btn("H2", "Heading", editor.isActive("heading", { level: 2 }), () =>
        chain().toggleHeading({ level: 2 }).run(),
      )}
      {btn("H3", "Subheading", editor.isActive("heading", { level: 3 }), () =>
        chain().toggleHeading({ level: 3 }).run(),
      )}
      {btn("❝", "Quote", editor.isActive("blockquote"), () => chain().toggleBlockquote().run())}
      {btn("•", "Bullet list", editor.isActive("bulletList"), () => chain().toggleBulletList().run())}
      {btn("1.", "Numbered list", editor.isActive("orderedList"), () => chain().toggleOrderedList().run())}
      {btn("Link", "Add or edit link", editor.isActive("link"), editLink)}
      {btn("Photo", "Insert photo", false, onPhotoClick)}
      {editor.isActive("figure") &&
        btn(figureWidth === "wide" ? "Normal width" : "Wide", "Toggle image width", false, () =>
          chain().setFigureWidth(figureWidth === "wide" ? "normal" : "wide").run(),
        )}
    </div>
  );
}
