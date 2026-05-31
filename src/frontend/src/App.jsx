import { Link, NavLink, Outlet } from 'react-router-dom'

const navClass = ({ isActive }) =>
  `text-sm transition-colors ${
    isActive ? 'text-gray-900 font-medium' : 'text-gray-500 hover:text-gray-900'
  }`

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="border-b border-gray-200 bg-white">
        <nav className="mx-auto flex max-w-5xl items-center gap-6 px-6 py-4">
          <Link to="/" className="font-semibold">
            📈 Stock OHLCV
          </Link>
          <NavLink to="/" end className={navClass}>
            Home
          </NavLink>
          <NavLink to="/ohlcv" className={navClass}>
            OHLCV
          </NavLink>
          <NavLink to="/ohlcv-live" className={navClass}>
            Live Stream
          </NavLink>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-10">
        <Outlet />
      </main>
    </div>
  )
}
