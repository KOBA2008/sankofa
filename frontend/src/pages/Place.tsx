import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, Camera, Clapperboard, ExternalLink, Map, ScanLine, View, Wand2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { AgentTimeline } from '../components/AgentTimeline'
import { Backdrop, Footer } from '../components/Chrome'
import { CompareViewer } from '../components/CompareViewer'
import { ContributeModal } from '../components/ContributeModal'
import { DocumentaryPlayer } from '../components/DocumentaryPlayer'
import { RephotoModal } from '../components/RephotoModal'
import { ResultPanel } from '../components/ResultPanel'
import { api, type AgentEvent, type PlaceDetail, type RunResult } from '../lib/api'

const MIN_YEAR = 1860
const MAX_YEAR = 1960

export default function Place() {
  const { id = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const [place, setPlace] = useState<PlaceDetail | null>(null)
  const [year, setYear] = useState(1900)
  const [currentId, setCurrentId] = useState<string | undefined>()
  const [photo, setPhoto] = useState<File | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [result, setResult] = useState<RunResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [contribOpen, setContribOpen] = useState(false)
  const [rephotoOpen, setRephotoOpen] = useState(false)
  const stopRef = useRef<() => void>(undefined)
  const resultRef = useRef<HTMLDivElement>(null)

  const load = () => api.place(id).then(p => {
    setPlace(p)
    setYear(y => (y === 1900 ? p.era : y))
    setCurrentId(c => c ?? 'auto')
  }).catch(e => setError(e.message))

  useEffect(() => { load(); return () => stopRef.current?.() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  // un lien ?run=… rouvre une reconstruction déjà faite
  useEffect(() => {
    const runId = params.get('run')
    if (!runId || result?.run === runId) return
    api.run(runId).then(r => { if (r.result) { setResult(r.result); setYear(r.result.year) } }).catch(() => {})
  }, [params]) // eslint-disable-line react-hooks/exhaustive-deps

  const photoUrl = useMemo(() => (photo ? URL.createObjectURL(photo) : null), [photo])
  const selectedCurrent = photoUrl ?? (place?.currents.find(c => c.id === currentId) ?? place?.currents[0])?.image

  const launch = async () => {
    if (!place) return
    stopRef.current?.()
    setEvents([]); setResult(null); setError(null); setRunning(true)
    try {
      const { run_id } = await api.startRun(place.id, { year, currentId: photo ? undefined : currentId, photo: photo ?? undefined })
      stopRef.current = api.stream(run_id, ev => {
        setEvents(prev => [...prev, ev])
        if (ev.step === 'done') {
          setResult(ev.data.result as RunResult)
          setParams({ run: run_id }, { replace: true })
          setRunning(false)
          setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300)
        }
        if (ev.step === 'error') { setError(ev.message); setRunning(false) }
      })
    } catch (e) {
      setError((e as Error).message)
      setRunning(false)
    }
  }

  const titles = useMemo(() => Object.fromEntries((place?.archives ?? []).map(a => [a.id, `${a.title} (${a.year})`])), [place])
  const fill = ((year - MIN_YEAR) / (MAX_YEAR - MIN_YEAR)) * 100
  const backdrop = place?.archives.slice(0, 6).map(a => a.image) ?? []

  if (error && !place) return <div className="flex min-h-screen items-center justify-center text-white/60">{error}</div>

  return (
    <div className="grain">
      <Backdrop images={backdrop} dim={0.78} />
      <main className="mx-auto max-w-6xl px-4 pt-28">
        <Link to="/" className="mb-6 inline-flex items-center gap-1.5 text-sm text-white/55 hover:text-white"><ArrowLeft size={15} /> Toutes les villes</Link>

        {place && (
          <motion.header initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-10 grid gap-6 md:grid-cols-[1.4fr_1fr] md:items-end">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold">{place.city} · {place.country}</p>
              <h1 className="mt-2 text-balance font-serif text-5xl leading-none md:text-7xl">{place.name}</h1>
            </div>
            <div>
              <p className="text-sm leading-relaxed text-white/65">{place.context}</p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs">
                <button onClick={() => document.getElementById('documentaire')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} className="gold-button inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 font-semibold">
                  <Clapperboard size={13} /> Documentaire
                </button>
                <a href={`https://www.google.com/maps/search/?api=1&query=${place.lat},${place.lon}`} target="_blank" rel="noreferrer" className="glass glass-button inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5">
                  <Map size={13} /> Google Maps
                </a>
                <a href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${place.lat},${place.lon}`} target="_blank" rel="noreferrer" className="glass glass-button inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5">
                  <View size={13} /> Street View aujourd'hui
                </a>
              </div>
            </div>
          </motion.header>
        )}

        <div className="grid gap-5 lg:grid-cols-[1.55fr_1fr]">
          {/* colonne gauche : la vue */}
          <div className="space-y-4">
            {result ? (
              <CompareViewer before={result.current} after={result.reconstruction} size={result.size} tags={result.tags} year={result.year} sourceTitles={titles} alternatives={result.nearest} />
            ) : (
              <div className="glass relative aspect-[4/3] overflow-hidden rounded-[28px]">
                {selectedCurrent && <img src={selectedCurrent} alt="Vue actuelle" className="h-full w-full object-cover" />}
                <AnimatePresence>
                  {running && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0">
                      <div className="absolute inset-0 bg-black/35" />
                      <motion.div
                        className="absolute inset-x-0 h-24 bg-gradient-to-b from-transparent via-gold/30 to-transparent"
                        animate={{ top: ['-20%', '110%'] }}
                        transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
                      />
                      <div className="glass absolute bottom-4 left-4 right-4 rounded-2xl px-4 py-3 text-sm text-white/85">
                        {events[events.length - 1]?.message ?? "L'agent se met au travail…"}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}

            {!result && place && (
              <div className="glass rounded-[28px] p-4">
                <p className="mb-3 text-xs uppercase tracking-widest text-white/45">Vue de départ</p>
                <div className="scrollbar-thin flex gap-2 overflow-x-auto pb-1">
                  <label className={`flex h-20 w-28 shrink-0 cursor-pointer flex-col items-center justify-center gap-1 rounded-2xl text-xs transition ${photo ? 'bg-gold/15 text-gold ring-1 ring-gold/60' : 'bg-black/25 text-white/60 hover:text-white'}`}>
                    <input type="file" accept="image/*" capture="environment" className="hidden" onChange={e => setPhoto(e.target.files?.[0] ?? null)} />
                    <Camera size={18} /> Ma photo
                  </label>
                  <button onClick={() => setRephotoOpen(true)} className="flex h-20 w-28 shrink-0 flex-col items-center justify-center gap-1 rounded-2xl bg-black/25 text-xs text-white/60 transition hover:text-white">
                    <ScanLine size={18} /> Retrouver l'angle
                  </button>
                  <button onClick={() => { setPhoto(null); setCurrentId('auto') }} className={`flex h-20 w-28 shrink-0 flex-col items-center justify-center gap-1 rounded-2xl text-xs transition ${!photo && currentId === 'auto' ? 'bg-gold/15 text-gold ring-1 ring-gold/60' : 'bg-black/25 text-white/60 hover:text-white'}`}>
                    <Wand2 size={18} /> Meilleur angle
                  </button>
                  {place.currents.map(c => (
                    <button key={c.id} onClick={() => { setPhoto(null); setCurrentId(c.id) }} className={`relative h-20 w-28 shrink-0 overflow-hidden rounded-2xl transition ${!photo && currentId === c.id ? 'ring-2 ring-gold' : 'opacity-60 hover:opacity-100'}`} title={c.title}>
                      <img src={c.image} alt={c.title} className="h-full w-full object-cover" loading="lazy" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* colonne droite : commandes et agent */}
          <div className="space-y-4">
            <div className="glass glass-strong rounded-[28px] p-5">
              <div className="flex items-baseline justify-between">
                <p className="text-xs uppercase tracking-widest text-white/45">Époque visée</p>
                <span className="font-serif text-5xl text-gold-soft">{year}</span>
              </div>
              <input
                type="range" min={MIN_YEAR} max={MAX_YEAR} step={1} value={year}
                onChange={e => setYear(Number(e.target.value))}
                className="timeline mt-4"
                style={{ ['--fill' as string]: `${fill}%` }}
                aria-label="Année"
              />
              <div className="mt-1 flex justify-between font-mono text-[11px] text-white/35"><span>{MIN_YEAR}</span><span>{MAX_YEAR}</span></div>
              <button onClick={launch} disabled={running || !place} className="gold-button mt-5 flex w-full items-center justify-center gap-2 rounded-full px-5 py-3.5 text-sm font-semibold">
                <Wand2 size={16} /> {running ? "L'agent travaille…" : result ? 'Relancer le voyage' : 'Remonter le temps'}
              </button>
              {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
            </div>

            {(events.length > 0 || running) && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-[28px] p-4">
                <p className="mb-2 px-2 text-xs uppercase tracking-widest text-white/45">Journal de l'agent</p>
                <AgentTimeline events={events} />
              </motion.div>
            )}

            {!events.length && place && (
              <div className="glass rounded-[28px] p-5 text-sm text-white/65">
                <p className="font-medium text-white">{place.n_archives} documents d'archives</p>
                <p className="mt-1">Choisissez une vue actuelle (ou prenez votre photo), une année, puis lancez l'agent. Il vous montrera chaque étape.</p>
              </div>
            )}
          </div>
        </div>

        {result && (
          <div ref={resultRef} className="mt-5 scroll-mt-28">
            <ResultPanel result={result} onContribute={() => setContribOpen(true)} />
          </div>
        )}

        {place && (
          <div id="documentaire" className="mt-16 scroll-mt-24">
            <DocumentaryPlayer key={result?.run ?? 'corpus'} kind="place" id={place.id} run={result?.run} title={`${place.city} · ${place.name}`} />
          </div>
        )}

        {place && (
          <section className="mt-16">
            <div className="mb-5 flex items-end justify-between">
              <h2 className="font-serif text-4xl">Le corpus</h2>
              <button onClick={() => setContribOpen(true)} className="glass glass-button rounded-full px-4 py-2 text-sm">Contribuer</button>
            </div>
            <div className="columns-2 gap-3 md:columns-4">
              {[...place.contributions, ...place.archives].map(a => (
                <a key={a.id} href={a.page_url || a.image} target="_blank" rel="noreferrer" className="glass group mb-3 block break-inside-avoid overflow-hidden rounded-2xl p-1.5">
                  <img src={a.image} alt={a.title} loading="lazy" className="w-full rounded-xl" />
                  <div className="px-1.5 py-2 text-xs">
                    <p className="line-clamp-2 text-white/80">{a.title}</p>
                    <p className="mt-0.5 flex items-center gap-1 text-white/40">
                      {a.year ?? 's.d.'} · {a.verified === false ? <span className="text-guess">non vérifié</span> : a.license}
                      <ExternalLink size={10} className="ml-auto opacity-0 transition group-hover:opacity-100" />
                    </p>
                  </div>
                </a>
              ))}
            </div>
          </section>
        )}
      </main>
      <Footer />
      {place && <RephotoModal open={rephotoOpen} archives={place.archives} onClose={() => setRephotoOpen(false)} onCapture={f => setPhoto(f)} />}
      {place && <ContributeModal open={contribOpen} placeId={place.id} onClose={() => setContribOpen(false)} onDone={() => load()} />}
    </div>
  )
}
