import { motion } from 'framer-motion'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { ArrowRight, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { MapContainer, Marker, TileLayer, Tooltip } from 'react-leaflet'
import { Link, useNavigate } from 'react-router-dom'
import { Backdrop, Footer } from '../components/Chrome'
import { STEPS } from '../components/AgentTimeline'
import { api, type PlaceSummary } from '../lib/api'

const pin = L.divIcon({
  className: '',
  html: '<span style="display:block;width:16px;height:16px;border-radius:99px;background:radial-gradient(circle at 35% 30%,#fff,#f4dea0 45%,#c99a2e);box-shadow:0 0 0 6px rgba(233,196,106,.22),0 4px 14px rgba(0,0,0,.6)"></span>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
})

const fade = { initial: { opacity: 0, y: 24 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, margin: '-60px' }, transition: { duration: 0.7, ease: [0.2, 0.8, 0.2, 1] as const } }

export default function Home() {
  const [places, setPlaces] = useState<PlaceSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const nav = useNavigate()
  useEffect(() => { api.places().then(setPlaces).catch(e => setError(e.message)) }, [])
  const covers = useMemo(() => places.map(p => p.cover).filter(Boolean) as string[], [places])
  const total = places.reduce((s, p) => s + p.n_archives, 0)
  const countries = new Set(places.map(p => p.country)).size
  const continents = useMemo(() => [...new Set(places.map(p => p.continent))].sort(), [places])
  const [continent, setContinent] = useState<string>('Tous')
  const shown = continent === 'Tous' ? places : places.filter(p => p.continent === continent)

  return (
    <div className="grain">
      <Backdrop images={covers} />

      <section className="mx-auto flex min-h-[92vh] max-w-6xl flex-col justify-center px-4 pt-28">
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1, ease: [0.2, 0.8, 0.2, 1] }}>
          <div className="glass mb-6 inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs text-white/80">
            <Sparkles size={13} className="text-gold" /> Un agent IA qui construit la machine à remonter le temps de chaque ville
          </div>
          <h1 className="text-balance font-serif text-6xl leading-[0.95] md:text-8xl">
            Retourne chercher<br /><em className="text-gold-soft">ce que le temps a emporté.</em>
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-white/70">
            Donnez un lieu à Sankofa. L'agent fouille les archives, retrouve d'où les photographes d'époque ont pris leurs vues,
            apprend le style de la ville, reconstruit le passé, puis se teste lui-même. Chaque détail porte une étiquette :
            <span className="text-proof"> prouvé</span>, <span className="text-same">inchangé</span> ou <span className="text-guess">imaginé</span>.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <a href="#villes" className="gold-button inline-flex items-center gap-2 rounded-full px-6 py-3.5 text-sm font-semibold">
              Choisir une ville <ArrowRight size={16} />
            </a>
            <Link to="/methode" className="glass glass-button rounded-full px-6 py-3.5 text-sm">Comment l'agent travaille</Link>
          </div>
          <dl className="mt-14 grid max-w-2xl grid-cols-3 gap-3">
            {[[places.length || '…', 'lieux'], [countries || '…', 'pays'], [total || '…', "documents d'archives"]].map(([v, l]) => (
              <div key={String(l)} className="glass rounded-3xl px-5 py-4">
                <dt className="font-serif text-4xl">{v}</dt>
                <dd className="text-xs text-white/55">{l}</dd>
              </div>
            ))}
          </dl>
        </motion.div>
      </section>

      <section id="villes" className="mx-auto max-w-6xl scroll-mt-28 px-4">
        <motion.div {...fade} className="mb-8 flex items-end justify-between gap-4">
          <div>
            <p className="mb-2 font-mono text-xs uppercase tracking-[0.25em] text-gold">{places.length} lieux · {countries} pays · {continents.length} continents</p>
            <h2 className="font-serif text-5xl">De Porto-Novo au Taj Mahal</h2>
          </div>
          {error && <p className="text-sm text-red-300">Backend injoignable : {error}</p>}
        </motion.div>

        <div className="mb-6 flex flex-wrap gap-1.5 text-sm">
          {['Tous', ...continents].map(c => (
            <button
              key={c}
              onClick={() => setContinent(c)}
              className={`rounded-full px-4 py-1.5 transition ${continent === c ? 'bg-gold-soft text-ink' : 'glass glass-button text-white/70'}`}
            >
              {c}
              {c !== 'Tous' && <span className="ml-1.5 text-xs opacity-60">{places.filter(p => p.continent === c).length}</span>}
            </button>
          ))}
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((p, i) => (
            <motion.div key={p.id} {...fade} transition={{ ...fade.transition, delay: i * 0.06 }}>
              <Link to={`/lieu/${p.id}`} className="glass group block overflow-hidden rounded-[28px] p-2">
                <div className="relative aspect-[4/3] overflow-hidden rounded-[22px]">
                  {p.cover && <img src={p.cover} alt={p.name} loading="lazy" className="h-full w-full object-cover transition duration-[1.2s] group-hover:scale-105" style={{ filter: 'sepia(.25)' }} />}
                  {p.current_cover && <img src={p.current_cover} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover opacity-0 transition duration-700 group-hover:opacity-100" />}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-transparent" />
                  <div className="glass glass-refract absolute left-3 top-3 rounded-full px-3 py-1 font-mono text-xs">
                    {p.span ? `${p.span[0]} – ${p.span[1]}` : 's.d.'}
                  </div>
                  <div className="absolute inset-x-4 bottom-3">
                    <p className="text-xs text-white/60">{p.country} · {p.continent}</p>
                    <h3 className="font-serif text-4xl leading-none">{p.city}</h3>
                  </div>
                </div>
                <div className="flex items-center justify-between px-3 py-3 text-sm">
                  <span className="truncate text-white/70">{p.name}</span>
                  <span className="ml-3 shrink-0 font-mono text-xs text-white/45">{p.n_archives} archives</span>
                </div>
              </Link>
            </motion.div>
          ))}
          {places.length === 0 && !error && Array.from({ length: 6 }).map((_, i) => <div key={i} className="glass aspect-[4/3.6] animate-pulse rounded-[28px]" />)}
        </div>
      </section>

      <section className="mx-auto mt-24 max-w-6xl px-4">
        <motion.div {...fade} className="glass overflow-hidden rounded-[32px] p-2">
          <div className="h-[420px] overflow-hidden rounded-[26px]">
            <MapContainer center={[22, -10]} zoom={2} minZoom={2} scrollWheelZoom={false} className="h-full w-full" worldCopyJump>
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                attribution='&copy; OpenStreetMap &copy; CARTO'
              />
              {places.map(p => (
                <Marker key={p.id} position={[p.lat, p.lon]} icon={pin} eventHandlers={{ click: () => nav(`/lieu/${p.id}`) }}>
                  <Tooltip direction="top" offset={[0, -10]}>{p.city} · {p.name}</Tooltip>
                </Marker>
              ))}
            </MapContainer>
          </div>
        </motion.div>
      </section>

      <section className="mx-auto mt-24 max-w-6xl px-4">
        <motion.div {...fade}>
          <p className="mb-2 font-mono text-xs uppercase tracking-[0.25em] text-gold">L'agent</p>
          <h2 className="max-w-3xl font-serif text-5xl">Il fait le travail d'un historien et d'un ingénieur, puis il se contrôle.</h2>
        </motion.div>
        <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <motion.div key={s.id} {...fade} transition={{ ...fade.transition, delay: i * 0.05 }} className="glass rounded-3xl p-5">
              <div className="mb-4 flex items-center justify-between">
                <s.icon size={20} className="text-gold" />
                <span className="font-mono text-xs text-white/35">0{i + 1}</span>
              </div>
              <h3 className="font-medium">{s.label}</h3>
            </motion.div>
          ))}
          <motion.div {...fade} className="glass flex flex-col justify-between rounded-3xl bg-gold/10 p-5">
            <p className="text-sm text-white/75">Modèles : Muse Spark, SAM 3.1, Muse Image, transcription vocale.</p>
            <Link to="/methode" className="mt-3 inline-flex items-center gap-1 text-sm text-gold">La méthode <ArrowRight size={14} /></Link>
          </motion.div>
        </div>
      </section>

      <Footer />
    </div>
  )
}
