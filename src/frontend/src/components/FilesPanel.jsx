// Lists the source files behind a stage, grouped (Backend / Frontend / …), each
// with its repo path and a detailed note on what it does. Reused by every stage.
//
//   groups = [{ label, files: [{ path, desc }] }]

export default function FilesPanel({ groups }) {
  return (
    <div className="space-y-6">
      {groups.map((g) => (
        <div key={g.label}>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            {g.label}
          </h4>
          <ul className="space-y-2">
            {g.files.map((f) => (
              <li
                key={f.path}
                className="rounded-lg border border-slate-800 bg-slate-950/40 p-3"
              >
                <code className="break-all text-sm text-sky-300">{f.path}</code>
                <p className="mt-1 text-sm leading-relaxed text-slate-400">{f.desc}</p>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
