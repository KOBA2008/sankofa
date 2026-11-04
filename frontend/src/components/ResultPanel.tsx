import { AnimatePresence, motion } from 'framer-motion'
import { ExternalLink, HelpCircle, Pause, Play } from 'lucide-react'
import { useEffect, useState } from 'react'
import { STATUS_META, type RunResult } from '../lib/api'
import { announceMedia } from './AmbientMusic'

const TABS = [
  { id: 'recit', label: 'Story' },
  { id: 'sources', label: 'Evidence' },
  { id: 'fiabilite', label: 'Reliability' },
  { id: 'lacunes', label: 'Gaps' },
] as const
type TabId = (typeof TABS)[number]['id']

/** Les phrases citent [S1], [S2]… : on les rend cliquables vers la source. */
export function Cited({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  const parts = text.split(/(\[S\d+\])/g)
  return (
    <>
      {parts.map((p, i) => {
        const m = p.match(/\[S(\d+)\]/)
        if (!m) return <span key={i}>{p}</span>
        return (
          <button key={i} onClick={() => onCite(Number(m[1]))} className="mx-0.5 rounded-md bg-gold/15 px-1.5 py-px align-baseline font-mono text-xs text-gold hover:bg-gold/30">
            S{m[1]}
          </button>
        )
      })}
    </>
  )
}

export function ResultPanel({ result, onContribute }: { result: RunResult; onContribute: () => void }) {
  const [tab, setTab] = useState<TabId>('recit')
  const [lang, setLang] = useState<'fr' | 'en'>('en')
  const [speaking, setSpeaking] = useState(false)
  const [focus, setFocus] = useState<number | null>(null)
  const ev = result.evaluation

  useEffect(() => () => window.speechSynthesis?.cancel(), [])

  const speak = () => {
    const synth = window.speechSynthesis
    if (!synth) return
    if (speaking) { synth.cancel(); setSpeaking(false); announceMedia(false); return }
    const u = new SpeechSynthesisUtterance(result.story[lang].replace(/\[S\d+\]/g, ''))
    u.lang = lang === 'fr' ? 'fr-FR' : 'en-US'
    u.rate = 0.96
    u.onend = () => { setSpeaking(false); announceMedia(false) }
    synth.speak(u)
    setSpeaking(true)
    announceMedia(true)
  }

  const cite = (n: number) => { setFocus(n); setTab('sources') }

  return (
    <div className="glass glass-strong rounded-[28px] p-5 md:p-6">
      <div className="mb-5 flex flex-wrap gap-1 rounded-full bg-black/25 p-1">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`relative flex-1 rounded-full px-3 py-1.5 text-sm transition ${tab === t.id ? 'text-ink' : 'text-white/60 hover:text-white'}`}
          >
            {tab === t.id && <motion.span layoutId="tab-pill" className="absolute inset-0 rounded-full bg-gold-soft" transition={{ type: 'spring', bounce: 0.2, duration: 0.5 }} />}
            <span className="relative">{t.label}</span>
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
          {tab === 'recit' && (
            <div>
              <div className="mb-3 flex items-center gap-2">
                <h3 className="font-serif text-3xl">{result.story.title}</h3>
                <div className="ml-auto flex rounded-full bg-black/25 p-0.5 text-xs">
                  {(['en', 'fr'] as const).map(l => (
                    <button key={l} onClick={() => setLang(l)} className={`rounded-full px-2.5 py-1 uppercase ${lang === l ? 'bg-white/15' : 'text-white/50'}`}>{l}</button>
                  ))}
                </div>
                <button onClick={speak} className="glass glass-button flex h-9 w-9 items-center justify-center rounded-full" aria-label="Listen to the story">
                  {speaking ? <Pause size={15} /> : <Play size={15} />}
                </button>
              </div>
              <p className="text-[15px] leading-relaxed text-white/80"><Cited text={result.story[lang]} onCite={cite} /></p>
              <div className="mt-5 grid grid-cols-3 gap-2">
                {(['documente', 'inchange', 'hypothese'] as const).map(k => (
                  <div key={k} className="rounded-2xl bg-black/25 p-3">
                    <div className="flex items-center gap-1.5 text-xs text-white/55"><span className="h-2 w-2 rounded-full" style={{ background: STATUS_META[k].color }} />{STATUS_META[k].label}</div>
                    <div className="mt-1 font-serif text-3xl">{result.counts[k]}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'sources' && (
            <ul className="scrollbar-thin max-h-[460px] space-y-2 overflow-auto pr-1">
              {result.sources.map(s => (
                <li key={s.id} className={`flex gap-3 rounded-2xl p-2 transition ${focus === s.n ? 'bg-gold/12 ring-1 ring-gold/50' : 'bg-black/20'}`}>
                  <img src={s.image} alt="" className="h-16 w-24 shrink-0 rounded-xl object-cover" loading="lazy" />
                  <div className="min-w-0 text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="rounded bg-gold/15 px-1 font-mono text-[11px] text-gold">S{s.n}</span>
                      <span className="truncate text-sm text-white/90">{s.title}</span>
                    </div>
                    <p className="mt-0.5 text-white/50">{s.year} · {s.license} · {s.source}</p>
                    {result.aligned.includes(s.id) && <p className="mt-0.5 text-proof">Overlaid on today's view</p>}
                    {s.page_url && (
                      <a href={s.page_url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-white/45 hover:text-gold">
                        Original record <ExternalLink size={11} />
                      </a>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}

          {tab === 'fiabilite' && (
            <div>
              <div className="flex items-center gap-5">
                <Gauge value={ev.reliability} />
                <div className="text-sm text-white/70">
                  <p className="font-medium text-white">Estimated reliability</p>
                  <p className="mt-1 text-xs leading-relaxed text-white/55">
                    Measured, not claimed: share of buildings backed by evidence, richness of the corpus, and a blind test
                    (the agent hides an archive, reconstructs without it, then compares).
                  </p>
                </div>
              </div>
              <div className="mt-5 space-y-3 text-sm">
                <Bar label="Buildings backed by evidence" value={ev.evidence_share} weight="50%" />
                <Bar label="Corpus richness" value={ev.source_richness} weight="20%" />
                <Bar label="Blind test" value={ev.holdout_score ?? 0} weight="30%" missing={ev.holdout_score === null} />
              </div>
              {ev.holdout.length > 0 && (
                <table className="mt-5 w-full text-left text-xs">
                  <caption className="mb-2 text-left text-white/45">Structural similarity with the hidden archive (1 = identical)</caption>
                  <thead className="text-white/45"><tr><th className="pb-1 font-normal">Hidden archive</th><th className="font-normal">Reconstructed</th><th className="font-normal">Current photo</th></tr></thead>
                  <tbody>
                    {ev.holdout.map(h => (
                      <tr key={h.archive} className="border-t border-white/8"><td className="py-1.5 pr-2 text-white/75">{h.year} · {h.title.slice(0, 34)}{h.others === 0 && <span className="block text-[11px] text-white/40">no other archive: style-only test</span>}</td><td className="font-mono text-proof">{h.ssim.toFixed(2)}</td><td className="font-mono text-white/50">{h.baseline.toFixed(2)}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="mt-4 text-xs text-white/40">
                Engines: segmentation {result.engines.segmentation}, reconstruction {result.engines.reconstruction}, story {result.engines.story}.
              </p>
            </div>
          )}

          {tab === 'lacunes' && (
            <div className="space-y-3">
              <p className="text-sm text-white/65">The agent knows what it doesn't know. Here is what it needs to reconstruct this place better:</p>
              {ev.gaps.length === 0 && <p className="rounded-2xl bg-black/25 p-4 text-sm text-white/60">No major gaps for this view.</p>}
              {ev.gaps.map(g => (
                <div key={g.tag} className="flex gap-3 rounded-2xl bg-guess/8 p-4 ring-1 ring-guess/25">
                  <HelpCircle size={18} className="mt-0.5 shrink-0 text-guess" />
                  <p className="text-sm text-white/80">{g.question}</p>
                </div>
              ))}
              <button onClick={onContribute} className="gold-button w-full rounded-full px-5 py-3 text-sm font-semibold">
                I have a photo or a memory
              </button>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

function Gauge({ value }: { value: number }) {
  const r = 42
  const c = 2 * Math.PI * r
  return (
    <div className="relative h-28 w-28 shrink-0">
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="8" />
        <motion.circle
          cx="50" cy="50" r={r} fill="none" stroke="url(#g)" strokeWidth="8" strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - value) }}
          transition={{ duration: 1.4, ease: [0.2, 0.8, 0.2, 1] }}
        />
        <defs><linearGradient id="g"><stop offset="0" stopColor="#f4dea0" /><stop offset="1" stopColor="#34d399" /></linearGradient></defs>
      </svg>
      <div className="absolute inset-0 flex items-center justify-center font-serif text-3xl">{Math.round(value * 100)}<span className="text-base text-white/50">%</span></div>
    </div>
  )
}

function Bar({ label, value, weight, missing }: { label: string; value: number; weight: string; missing?: boolean }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs"><span className="text-white/70">{label} <span className="text-white/35">· weight {weight}</span></span><span className="font-mono text-white/60">{missing ? 'not possible' : `${Math.round(value * 100)}%`}</span></div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/8">
        <motion.div className="h-full rounded-full bg-gradient-to-r from-gold-soft to-proof" initial={{ width: 0 }} animate={{ width: `${missing ? 0 : value * 100}%` }} transition={{ duration: 1.1 }} />
      </div>
    </div>
  )
}
