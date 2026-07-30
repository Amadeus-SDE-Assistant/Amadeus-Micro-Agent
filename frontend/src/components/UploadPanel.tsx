import { useEffect, useRef, useState } from "react";

interface DocumentInfo {
  id: string;
  status: string;
  extraction_method?: string | null;
  error?: string | null;
}

interface CredentialInfo {
  kind: string;
  title: string;
  org?: string | null;
}

const TERMINAL = new Set(["stored", "needs_ocr", "failed"]);

const STATUS_TEXT: Record<string, string> = {
  uploaded: "Uploaded — reading the PDF…",
  extracted: "Text extracted — decomposing into credentials…",
  decomposed: "Decomposed — saving credentials…",
  stored: "Done — credentials saved.",
  needs_ocr: "This looks like a scanned PDF. OCR isn't enabled yet, so it can't be read.",
  failed: "Ingestion failed.",
};

export function UploadPanel() {
  const [doc, setDoc] = useState<DocumentInfo | null>(null);
  const [credentials, setCredentials] = useState<CredentialInfo[]>([]);
  const [deduplicated, setDeduplicated] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!doc || TERMINAL.has(doc.status)) return;
    const timer = setInterval(() => {
      void (async () => {
        const resp = await fetch(`/api/documents/${doc.id}`);
        if (!resp.ok) return;
        const body = (await resp.json()) as {
          document: DocumentInfo;
          credentials: CredentialInfo[];
        };
        setDoc(body.document);
        setCredentials(body.credentials);
      })();
    }, 1500);
    return () => clearInterval(timer);
  }, [doc]);

  async function onFileChosen(file: File) {
    setBusy(true);
    setUploadError(null);
    setDoc(null);
    setCredentials([]);
    setDeduplicated(false);
    try {
      const form = new FormData();
      form.append("file", file);
      const resp = await fetch("/api/documents", { method: "POST", body: form });
      const body = (await resp.json()) as {
        document?: DocumentInfo;
        deduplicated?: boolean;
        detail?: string;
      };
      if (!resp.ok || !body.document) {
        setUploadError(body.detail ?? `Upload failed (${resp.status})`);
        return;
      }
      setDoc(body.document);
      setDeduplicated(body.deduplicated ?? false);
    } catch {
      setUploadError("Could not reach the server.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  const statusTone =
    doc?.status === "stored"
      ? "ok"
      : doc?.status === "failed" || doc?.status === "needs_ocr"
        ? "bad"
        : "busy";

  return (
    <section className="upload">
      <h2>Resume upload</h2>
      <p className="lede">
        Upload a PDF resume and Amadeus will decompose it into structured credentials
        and save them. Uploading is your consent to store the extracted data.
      </p>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        aria-label="Resume PDF"
        disabled={busy}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void onFileChosen(file);
        }}
      />
      {uploadError && <p role="alert">Error: {uploadError}</p>}
      {deduplicated && (
        <p className="status ok">
          <span className="state">Already saved</span> — this exact file was ingested
          before; nothing new to do.
        </p>
      )}
      {doc && (
        <div aria-live="polite">
          <p className={`status ${statusTone}`}>
            <span className="state">{doc.status.replace("_", " ")}</span>
            {" — "}
            {STATUS_TEXT[doc.status] ?? ""}
            {doc.status === "failed" && doc.error ? ` (${doc.error})` : ""}
          </p>
          {credentials.length > 0 && (
            <>
              <p>Stored credentials ({credentials.length}):</p>
              <ul className="credentials">
                {credentials.map((c, i) => (
                  <li key={i}>
                    <span className="kind">{c.kind}</span>
                    <span>
                      {c.title}
                      {c.org ? ` — ${c.org}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}
