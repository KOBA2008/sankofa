import { motion } from 'framer-motion'
import { BookOpenText } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Backdrop, Footer } from '../components/Chrome'
import { countriesApi, type Country } from '../lib/api'

export default function Countries() {
  const [list, setList] = useState<Country[]>([])
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { countriesApi.list().then(setList).catch(e => setError(e.message)) }, [])
  const covers = useMemo(() => list.map(c => c.cover).filter(Boolean) as string[], [list])

  return (
    <div>
      <Backdrop images={covers} dim={0.75} />
      <main className="mx-auto max-w-6xl px-4 pt-32">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold">Chroniques</p>
          <h1 className="mt-2 max-w-4xl text-balance font-serif text-6xl leading-none md:text-7xl">L'histoire d'un pays, racontée seulement par ses sources.</h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-white/70">
            L'agent lit les sources, extrait chaque événement daté mot pour mot, le recoupe avec une source rédigée par
            d'autres auteurs, signale les siècles que personne n'a documentés, puis illustre chaque époque avec des photos d'archives.
          </p>
        </motion.div>

        {error && <p className="mt-8 text-sm text-red-300">{error}</p>}
        <div className="mt-12 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((c, i) => (
            <motion.div key={c.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
              <Link to={`/pays/${c.id}`} className="glass group flex items-center gap-4 rounded-[24px] p-3 pr-5">
                <div className="relative h-20 w-24 shrink-0 overflow-hidden rounded-[18px] bg-black/30">
                  {c.cover ? <img src={c.cover} alt="" className="h-full w-full object-cover transition duration-700 group-hover:scale-110" style={{ filter: 'sepia(.3)' }} /> :
                    <div className="flex h-full items-center justify-center text-4xl">{c.flag}</div>}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 font-serif text-3xl leading-none">{c.name} <span className="text-xl">{c.flag}</span></p>
                  <p className="mt-1.5 truncate text-xs text-white/50">{c.old_names.slice(0, 3).join(' · ')}</p>
                  {c.stats ? (
                    <p className="mt-1 font-mono text-xs text-white/60">{c.stats.events} événements · {Math.round(c.stats.share * 100)} % recoupés</p>
                  ) : (
                    <p className="mt-1 flex items-center gap-1 text-xs text-gold"><BookOpenText size={12} /> à reconstituer</p>
                  )}
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </main>
      <Footer />
    </div>
  )
}
