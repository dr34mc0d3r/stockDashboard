import { Outlet } from 'react-router-dom'
import Stepper from './components/Stepper.jsx'

export default function App() {
  return (
    <div className="flex min-h-full bg-slate-950 text-slate-200">
      <aside className="w-64 shrink-0 border-r border-slate-800 p-4">
        <div className="mb-6">
          <h1 className="text-lg font-bold text-white">Market ML Lab</h1>
          <p className="text-xs text-slate-500">build a forecaster, stage by stage</p>
        </div>
        <Stepper />
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-5xl p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
