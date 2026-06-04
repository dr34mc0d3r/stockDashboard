// The standard inline error message. Renders nothing when there's no error,
// so callers can write `<ErrorNote error={error} />` unconditionally.

/**
 * @param {object} props
 * @param {string} [props.error] - Message to show; falsy hides the note.
 * @param {string} [props.className]
 */
export default function ErrorNote({ error, className = 'mt-3' }) {
  if (!error) return null
  return (
    <p className={`rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-300 ${className}`}>
      {error}
    </p>
  )
}
