import { motion } from 'framer-motion'
import { CheckCircle2, ExternalLink } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, type PlaceHistory as History } from '../lib/api'

/** Frise datée du lieu : chaque événement est une citation exacte de l'article, recoupée avec l'article anglais. */
export function PlaceHistory({ placeId }: { placeId: string }) {
  const [hist, setHist] = useState<History | null>(null)
  const [all, setAll] = useState(false)

  useEffect(() => { api.history(placeId).then(setHist).catch(() => setHist(null)) }, [placeId])

  if (!hist || hist.events.length === 0) return null
  const shown = all ? hist.events : hist.events.slice(0, 8)

  return (
    <section className="mt-16">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold">Its history</p>
          <h2 className="mt-1 font-serif text-4xl">{hist.stats.events} dates, quoted word for word</h2>
        </div>
        <p className="text-xs text-white/50">
          {hist.stats.corroborated} corroborated by the {hist.sources[1] ? 'second-language' : 'source'} article ·{' '}
          <a href={hist.sources[0].url} target="_blank" rel="noreferrer" className="underline decoration-white/20 hover:text-gold">{hist.sources[0].title}</a>
        </p>
      </div>
      {hist.intro && <p className="mb-6 max-w-3xl text-[15px] leading-relaxed text-white/70">{hist.intro}</p>}

      <ol className="relative space-y-2 border-l border-white/10 pl-6">
        {shown.map((e, i) => (
          <motion.li
            key={`${e.year}-${i}`}
            initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(i, 8) * 0.04 }}
            className="relative"
          >
            <span className="absolute -left-[29px] top-4 h-2.5 w-2.5 rounded-full border-2 border-gold bg-ink" />
            <div className="glass flex gap-4 rounded-2xl p-3.5">
              <span className="w-24 shrink-0 font-serif text-2xl leading-none text-gold-soft">{e.label}</span>
              <div className="min-w-0 flex-1 text-sm">
                <p className="text-white/85">“{e.text}”</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs">
                  {e.corroborated
                    ? <span className="flex items-center gap-1 text-proof"><CheckCircle2 size={12} /> corroborated</span>
                    : <span className="flex items-center gap-1 text-guess"><span className="h-1.5 w-1.5 rounded-full bg-guess" /> single source</span>}
                  <a href={e.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-white/45 hover:text-gold">
                    {e.section === 'Introduction' ? 'Introduction' : e.section} <ExternalLink size={10} />
                  </a>
                </div>
              </div>
            </div>
          </motion.li>
        ))}
      </ol>
      {hist.events.length > 8 && (
        <button onClick={() => setAll(v => !v)} className="glass glass-button mt-4 rounded-full px-4 py-2 text-sm">
          {all ? 'Show less' : `Show ${hist.events.length - 8} more dates`}
        </button>
      )}
    </section>
  )
}
