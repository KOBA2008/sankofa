import { motion } from 'framer-motion'
import { Archive, Brain, Check, Crop, Feather, Loader2, Palette, ScanSearch, ShieldCheck } from 'lucide-react'
import type { AgentEvent } from '../lib/api'

export const STEPS = [
  { id: 'enquete', label: 'Enquête dans les archives', icon: Archive },
  { id: 'annotation', label: 'Annotation de la vue actuelle', icon: Crop },
  { id: 'alignement', label: 'Re-photographie', icon: ScanSearch },
  { id: 'style', label: 'Style de la ville', icon: Palette },
  { id: 'reconstruction', label: 'Reconstruction', icon: Brain },
  { id: 'evaluation', label: 'Auto-évaluation', icon: ShieldCheck },
  { id: 'recit', label: 'Récit sourcé', icon: Feather },
]

function engineLabel(e: string) {
  if (e.startsWith('meta:')) return e.replace('meta:', 'Meta · ')
  return 'local'
}

export function AgentTimeline({ events, steps = STEPS }: { events: AgentEvent[]; steps?: typeof STEPS }) {
  return (
    <ol className="relative space-y-1">
      {steps.map((s, idx) => {
        const evs = events.filter(e => e.step === s.id)
        const done = evs.find(e => e.status === 'done')
        const running = evs.length > 0 && !done
        const last = done ?? evs[evs.length - 1]
        const logs = evs.filter(e => e.status === 'log')
        const engine = done?.engine ?? last?.engine
        const Icon = s.icon
        return (
          <motion.li
            key={s.id}
            initial={false}
            animate={{ opacity: evs.length ? 1 : 0.38 }}
            className="relative flex gap-3 rounded-2xl px-2 py-2"
          >
            {idx < steps.length - 1 && (
              <span className={`absolute left-[25px] top-11 h-[calc(100%-28px)] w-px ${done ? 'bg-gold/50' : 'bg-white/10'}`} />
            )}
            <span
              className={`relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border ${
                done ? 'border-gold/60 bg-gold/15 text-gold' : running ? 'border-white/40 bg-white/10 text-white' : 'border-white/10 bg-white/5 text-white/40'
              }`}
            >
              {done ? <Check size={16} /> : running ? <Loader2 size={16} className="animate-spin" /> : <Icon size={15} />}
            </span>
            <div className="min-w-0 flex-1 pt-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{s.label}</span>
                {engine && evs.length > 0 && (
                  <span className={`rounded-full px-2 py-0.5 font-mono text-[11px] ${engine.startsWith('meta') ? 'bg-sky-400/15 text-sky-300' : 'bg-white/8 text-white/50'}`}>
                    {engineLabel(engine)}
                  </span>
                )}
              </div>
              {last && <p className="mt-0.5 text-xs leading-relaxed text-white/60">{last.message}</p>}
              {logs.length > 0 && (
                <details className="mt-1 text-xs text-white/45">
                  <summary className="cursor-pointer select-none hover:text-white/70">{logs.length} détail(s)</summary>
                  <ul className="scrollbar-thin mt-1 max-h-32 space-y-0.5 overflow-auto font-mono text-xs">
                    {logs.map((l, i) => <li key={i}>› {l.message}</li>)}
                  </ul>
                </details>
              )}
            </div>
          </motion.li>
        )
      })}
    </ol>
  )
}
