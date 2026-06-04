// Run-status → Tailwind badge classes, shared wherever a status chip appears
// (TrainingProgress, RunsTable). One map so the colors can never drift apart.
export const STATUS_STYLES = {
  queued: 'bg-slate-500/20 text-slate-300',
  running: 'bg-amber-500/20 text-amber-300',
  done: 'bg-emerald-500/20 text-emerald-300',
  error: 'bg-red-500/20 text-red-300',
}
