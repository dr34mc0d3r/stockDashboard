import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Renders lesson markdown (the What / Why / Writeup parts of each stage page).
export default function LessonPanel({ source }) {
  return (
    <div className="lesson">
      <Markdown remarkPlugins={[remarkGfm]}>{source}</Markdown>
    </div>
  )
}
