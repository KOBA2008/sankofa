import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useRef, useState } from 'react'
import { STATUS_META, type RunResult, type Tag, type TagStatus } from '../lib/api'

type Props = {
  before: string
  after: string
  size: [number, number]
  tags: Tag[]
  year: number
  sourceTitles: Record<string, string>
  alternatives?: RunResult['nearest']
}

/** Curseur avant / après, avec les zones étiquetées superposées à l'image du passé. */
export function CompareViewer({ before, after, size, tags, year, sourceTitles, alternatives = [] }: Props) {
  const [pos, setPos] = useState(55)
  const [mode, setMode] = useState<string>('reconstruction')
  const alt = alternatives.find(a => a.id === mode)
  const pastImage = alt ? alt.image : after
  const pastYear = alt ? alt.year : year
  const [showTags, setShowTags] = useState(true)
  const [filter, setFilter] = useState<TagStatus | 'all'>('all')
  const [hover, setHover] = useState<Tag | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)

  const move = useCallback((clientX: number) => {
    const r = ref.current?.getBoundingClientRect()
    if (!r) return
    setPos(Math.min(100, Math.max(0, ((clientX - r.left) / r.width) * 100)))
  }, [])

  const visible = tags.filter(t => t.label !== 'ciel' && (filter === 'all' || t.status === filter))

  return (
    <div className="space-y-3">
      {alternatives.length > 0 && (
        <div className="scrollbar-thin flex gap-1.5 overflow-x-auto pb-1 text-xs">
          <button onClick={() => setMode('reconstruction')} className={`shrink-0 rounded-full px-3.5 py-1.5 transition ${mode === 'reconstruction' ? 'bg-gold-soft text-ink' : 'glass glass-button text-white/70'}`}>
            Reconstruction de l'agent
          </button>
          {alternatives.map(a => (
            <button key={a.id} onClick={() => setMode(a.id)} title={a.title} className={`flex shrink-0 items-center gap-1.5 rounded-full px-3.5 py-1.5 transition ${mode === a.id ? 'bg-gold-soft text-ink' : 'glass glass-button text-white/70'}`}>
              {a.aligned && <span className="h-1.5 w-1.5 rounded-full bg-proof" />}
              Archive réelle {a.year}
            </button>
          ))}
        </div>
      )}
      <div
        ref={ref}
        className="glass relative w-full touch-none select-none overflow-hidden rounded-[28px] p-0"
        style={{ aspectRatio: `${size[0]} / ${size[1]}` }}
        onPointerDown={e => { dragging.current = true; move(e.clientX); (e.target as HTMLElement).setPointerCapture?.(e.pointerId) }}
        onPointerMove={e => dragging.current && move(e.clientX)}
        onPointerUp={() => { dragging.current = false }}
      >
        <img src={before} alt="Vue actuelle" className="absolute inset-0 h-full w-full object-cover" draggable={false} />
        <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}>
          <img src={pastImage} alt={alt ? alt.title : `Reconstruction vers ${year}`} className="absolute inset-0 h-full w-full object-cover" draggable={false} />
          {showTags && !alt && (
            <svg viewBox={`0 0 ${size[0]} ${size[1]}`} className="absolute inset-0 h-full w-full" preserveAspectRatio="none">
              {visible.map(t => (
                <polygon
                  key={t.id}
                  points={t.polygon.map(p => p.join(',')).join(' ')}
                  fill={STATUS_META[t.status].color}
                  fillOpacity={hover?.id === t.id ? 0.32 : 0.14}
                  stroke={STATUS_META[t.status].color}
                  strokeOpacity={0.9}
                  strokeWidth={size[0] / 400}
                  strokeDasharray={t.status === 'hypothese' ? `${size[0] / 120} ${size[0] / 200}` : undefined}
                  style={{ cursor: 'help', transition: 'fill-opacity .2s' }}
                  onPointerEnter={() => setHover(t)}
                  onPointerLeave={() => setHover(null)}
                />
              ))}
            </svg>
          )}
        </div>

        <div className="pointer-events-none absolute left-4 top-4 rounded-full bg-black/45 px-3 py-1 font-mono text-xs text-gold-soft backdrop-blur">
          {alt ? `${pastYear} · archive` : `≈ ${year}`}
        </div>
        <div className="pointer-events-none absolute right-4 top-4 rounded-full bg-black/45 px-3 py-1 font-mono text-xs text-white/80 backdrop-blur">
          aujourd'hui
        </div>

        {/* poignée en verre */}
        <div className="pointer-events-none absolute inset-y-0" style={{ left: `${pos}%` }}>
          <div className="absolute inset-y-0 -left-px w-0.5 bg-white/80" />
          <div className="glass glass-refract absolute top-1/2 left-0 flex h-12 w-12 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full">
            <svg viewBox="0 0 24 24" className="h-5 w-5 text-white"><path d="M9 6l-6 6 6 6M15 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </div>
        </div>

        <AnimatePresence>
          {hover && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="glass glass-strong pointer-events-none absolute bottom-4 left-4 max-w-sm rounded-2xl p-4 text-sm"
            >
              <div className="mb-1 flex items-center gap-2">
                <span className="h-2 w-2 rounded-full" style={{ background: STATUS_META[hover.status].color }} />
                <span className="font-medium">{STATUS_META[hover.status].label}</span>
                <span className="text-white/50">· {hover.label}</span>
                <span className="ml-auto font-mono text-xs text-white/60">{Math.round(hover.confidence * 100)} %</span>
              </div>
              <p className="text-white/75">{hover.note}</p>
              {hover.sources.length > 0 && (
                <p className="mt-2 text-xs text-white/50">Source : {hover.sources.map(s => sourceTitles[s] || s).join(' · ')}</p>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <button onClick={() => setShowTags(v => !v)} className="glass glass-button rounded-full px-3.5 py-1.5">
          {showTags ? 'Masquer' : 'Afficher'} les étiquettes
        </button>
        {(['all', 'documente', 'inchange', 'hypothese'] as const).map(k => (
          <button
            key={k}
            onClick={() => setFilter(k)}
            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 transition ${filter === k ? 'bg-white/15 text-white' : 'text-white/55 hover:text-white'}`}
          >
            {k !== 'all' && <span className="h-2 w-2 rounded-full" style={{ background: STATUS_META[k].color }} />}
            {k === 'all' ? 'Toutes' : STATUS_META[k].label}
            {k !== 'all' && <span className="text-white/40">{tags.filter(t => t.status === k && t.label !== 'ciel').length}</span>}
          </button>
        ))}
        <span className="ml-auto text-white/40">Glissez pour voyager dans le temps</span>
      </div>
    </div>
  )
}
