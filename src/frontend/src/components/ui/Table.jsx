// Tiny table-cell helpers so data tables share one padding/alignment rhythm.

/** Header cell. @param {{children?: import('react').ReactNode, className?: string}} props */
export const Th = ({ children, className = '' }) => (
  <th className={`px-3 py-2 text-left font-medium ${className}`}>{children}</th>
)

/** Body cell. @param {{children?: import('react').ReactNode, className?: string}} props */
export const Td = ({ children, className = '' }) => (
  <td className={`px-3 py-2 ${className}`}>{children}</td>
)
