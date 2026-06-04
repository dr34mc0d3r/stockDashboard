// The numbered section card every stage page is built from.

/**
 * @param {object} props
 * @param {number} props.n - Section number shown in the circle badge.
 * @param {string} props.title
 * @param {import('react').ReactNode} props.children
 */
export default function Section({ n, title, children }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/30 p-6">
      <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-500/20 text-sm text-sky-300">
          {n}
        </span>
        {title}
      </h3>
      {children}
    </section>
  )
}
