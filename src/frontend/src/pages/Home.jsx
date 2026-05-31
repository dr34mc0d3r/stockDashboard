import { Link } from 'react-router-dom'

export default function Home() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Stock OHLCV Dashboard
        </h1>
        <p className="mt-2 text-gray-600">
          A Vite + React + Tailwind v4 frontend talking to the FastAPI backend.
        </p>
      </div>
      <Link
        to="/ohlcv"
        className="inline-block rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
      >
        View OHLCV data &rarr;
      </Link>
    </div>
  )
}
