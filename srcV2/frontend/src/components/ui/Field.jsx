// A labeled form control: small label on top, any input below.

/**
 * @param {object} props
 * @param {string} props.label
 * @param {import('react').ReactNode} props.children - The input/select itself.
 */
export default function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1 text-sm text-slate-400">
      <span>{label}</span>
      {children}
    </label>
  )
}
