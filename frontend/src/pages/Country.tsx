import { motion } from 'framer-motion'
import { AlertTriangle, ArrowLeft, Clapperboard, BookOpenText, Camera, CheckCircle2, ExternalLink, Feather, FileSearch, GitCompare, Pause, Play, ScrollText, Wand2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AgentTimeline } from '../components/AgentTimeline'
import { announceMedia } from '../components/AmbientMusic'
import { DocumentaryPlayer } from '../components/DocumentaryPlayer'
import { Backdrop, Footer } from '../components/Chrome'
import { Cited } from '../components/ResultPanel'
import { STATIC, api, countriesApi, type AgentEvent, type Chronicle, type Country as CountryT } from '../lib/api'

const STEPS = [
  { id: 'lecture', label: 'Reading the sources', icon: BookOpenText },
  { id: 'extraction', label: 'Extracting dated events', icon: FileSearch },
  { id: 'recoupement', label: 'Cross-checking sources', icon: GitCompare },
  { id: 'lacunes', label: 'Finding gaps', icon: AlertTriangle },
  { id: 'illustration', label: 'Period photos', icon: Camera },
  { id: 'recit', label: 'Cited narrative', icon: Feather },
]

const fmt = (y: number | null) => (y === null ? '' : y < 0 ? `${-y} BC` : String(y))

export default function Country() {
  const { id = '' } = useParams()
  const [country, setCountry] = useState<CountryT | null>(null)
  const [chron, setChron] = useState<Chronicle | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [speaking, setSpeaking] = useState(false)
  const [focusSource, setFocusSource] = useState<number | null>(null)
  const stop = useRef<() => void>(undefined)

  useEffect(() => {
    countriesApi.get(id).then(d => { setCountry(d.country); setChron(d.chronicle) }).catch(e => setError(e.message))
    return () => { stop.current?.(); window.speechSynthesis?.cancel() }
  }, [id])

  const launch = async () => {
    setEvents([]); setError(null); setRunning(true)
    try {
      const { run_id } = await countriesApi.run(id)
      stop.current = api.stream(run_id, ev => {
        setEvents(prev => [...prev, ev])
        if (ev.step === 'done') { setChron(ev.data.result as Chronicle); setRunning(false) }
        if (ev.step === 'error') { setError(ev.message); setRunning(false) }
      })
    } catch (e) { setError((e as Error).message); setRunning(false) }
  }

  const speak = () => {
    const synth = window.speechSynthesis
    if (!synth || !chron) return
    if (speaking) { synth.cancel(); setSpeaking(false); announceMedia(false); return }
    const text = chron.chapters.map(c => `${c.title}. ${c.narrative.replace(/\[S\d+\]/g, '')}`).join(' ')
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'en-US'; u.rate = 0.97; u.onend = () => { setSpeaking(false); announceMedia(false) }
    synth.speak(u); setSpeaking(true); announceMedia(true)
  }

  const cite = (n: number) => {
    setFocusSource(n)
    document.getElementById('sources')?.scrollIntoView({ behavior: 'smooth' })
  }

  const backdrop = useMemo(() => chron?.chapters.flatMap(c => c.photos.map(p => p.image)).slice(0, 8) ?? [], [chron])
  const sourceUrl = (n: number) => chron?.sources.find(s => s.n === n)?.url

  if (error && !country) return <div className="flex min-h-screen items-center justify-center text-white/60">{error}</div>

  return (
    <div>
      <Backdrop images={backdrop} dim={0.8} />
      <main className="mx-auto max-w-6xl px-4 pt-28">
        <Link to="/pays" className="mb-6 inline-flex items-center gap-1.5 text-sm text-white/55 hover:text-white"><ArrowLeft size={15} /> All countries</Link>

        {country && (
          <motion.header initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
            <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold">Chronicle · {country.old_names.slice(0, 2).join(' · ')}</p>
            <h1 className="mt-2 flex items-center gap-4 font-serif text-6xl leading-none md:text-8xl">{country.name} <span className="text-5xl">{country.flag}</span></h1>
            {chron && (
              <div className="mt-6 flex flex-wrap gap-2 text-sm">
                {chron.stats.span && <Stat value={`${chron.stats.span[0]} – ${chron.stats.span[1]}`} label="period covered" />}
                <Stat value={chron.stats.chapters} label="chapters" />
                <Stat value={chron.stats.events} label="events quoted" />
                <Stat value={`${Math.round(chron.stats.share * 100)}%`} label="corroborated by a 2nd source" />
              </div>
            )}
            <div className="mt-6 flex flex-wrap gap-2">
{!STATIC && (
              <button onClick={launch} disabled={running} className="gold-button inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-semibold">
                <Wand2 size={16} /> {running ? 'The agent is reading the sources…' : chron ? 'Rebuild again' : 'Rebuild the history'}
              </button>
              )}
              {chron && (
                <button onClick={() => document.getElementById('documentaire')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} className="glass glass-button inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm">
                  <Clapperboard size={15} /> Documentary
                </button>
              )}
              {chron && (
                <button onClick={speak} className="glass glass-button inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm">
                  {speaking ? <Pause size={15} /> : <Play size={15} />} Listen to the chronicle
                </button>
              )}
            </div>
            {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
          </motion.header>
        )}

        {(running || events.length > 0) && (
          <div className="glass mb-10 max-w-xl rounded-[28px] p-4">
            <p className="mb-2 px-2 text-xs uppercase tracking-widest text-white/45">Agent log</p>
            <AgentTimeline events={events} steps={STEPS} />
          </div>
        )}

        {chron && (
          <>
            <div id="documentaire" className="mb-14 scroll-mt-24">
              <DocumentaryPlayer key={chron.run} kind="country" id={id} title={`${chron.country.name}, a history told by its sources`} />
            </div>

            <div className="mb-8 flex flex-wrap items-center gap-4 text-xs text-white/55">
              <span className="flex items-center gap-1.5"><CheckCircle2 size={14} className="text-proof" /> corroborated: a source written by other authors cites the same date and the same name</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-guess" /> single source: needs checking</span>
              {chron.engines.narrative === 'local' && <span className="flex items-center gap-1.5"><ScrollText size={14} /> local mode: story built from excerpts</span>}
            </div>

            <ol className="relative space-y-6 border-l border-white/10 pl-6 md:pl-10">
              {chron.chapters.map((c, i) => (
                <motion.li key={c.title} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-60px' }} transition={{ duration: 0.6 }} className="relative">
                  <span className="absolute -left-[31px] top-7 h-3.5 w-3.5 rounded-full border-2 border-gold bg-ink md:-left-[47px]" />
                  <article className="glass glass-strong rounded-[28px] p-5 md:p-7">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <h2 className="font-serif text-4xl leading-tight">{c.title}</h2>
                      {c.start !== null && <span className="font-mono text-sm text-gold-soft">{fmt(c.start)}{c.end !== c.start && ` – ${fmt(c.end)}`}</span>}
                    </div>
                    {c.narrative && <p className="mt-3 text-[15px] leading-relaxed text-white/80"><Cited text={c.narrative} onCite={cite} /></p>}

                    {c.photos.length > 0 && (
                      <div className="mt-5 grid grid-cols-2 gap-2 md:grid-cols-4">
                        {c.photos.map(p => (
                          <a key={p.image} href={p.page_url || p.image} target="_blank" rel="noreferrer" className="group relative overflow-hidden rounded-2xl" title={`${p.title} · ${p.license}`}>
                            <img src={p.image} alt={p.title} loading="lazy" className="aspect-[4/3] w-full object-cover transition duration-700 group-hover:scale-105" />
                            <span className="absolute bottom-1.5 left-1.5 rounded-full bg-black/60 px-2 py-0.5 font-mono text-[11px] text-white/85 backdrop-blur">{p.year}</span>
                          </a>
                        ))}
                      </div>
                    )}

                    {c.events.length > 0 && (
                      <ul className="mt-5 space-y-2">
                        {c.events.map(e => (
                          <li key={`${e.year}-${e.text.slice(0, 20)}`} className="flex gap-3 rounded-2xl bg-black/25 p-3">
                            <span className="h-fit shrink-0 rounded-full bg-white/10 px-2.5 py-1 font-mono text-xs text-gold-soft">{e.label}</span>
                            <div className="min-w-0 flex-1 text-sm">
                              <p className="italic text-white/80">“{e.text}”</p>
                              <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs">
                                {e.corroborated
                                  ? <span className="flex items-center gap-1 text-proof"><CheckCircle2 size={12} /> corroborated</span>
                                  : <span className="flex items-center gap-1 text-guess"><span className="h-1.5 w-1.5 rounded-full bg-guess" /> single source</span>}
                                {sourceUrl(e.source) && (
                                  <a href={sourceUrl(e.source)} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-white/45 hover:text-gold">S{e.source} <ExternalLink size={10} /></a>
                                )}
                              </div>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                    <p className="mt-3 text-right font-mono text-[11px] text-white/30">chapter {i + 1}</p>
                  </article>
                </motion.li>
              ))}
            </ol>

            {chron.gaps.length > 0 && (
              <section className="mt-14">
                <h2 className="mb-4 font-serif text-4xl">What the sources don't say</h2>
                <div className="grid gap-3 md:grid-cols-2">
                  {chron.gaps.map(g => (
                    <div key={g.text} className="flex gap-3 rounded-2xl bg-guess/8 p-4 ring-1 ring-guess/25">
                      <AlertTriangle size={18} className="mt-0.5 shrink-0 text-guess" />
                      <p className="text-sm text-white/80">{g.text}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section id="sources" className="mt-14 scroll-mt-28">
              <h2 className="mb-4 font-serif text-4xl">Sources</h2>
              <ul className="glass grid gap-1 rounded-[28px] p-3 md:grid-cols-2">
                {chron.sources.map(s => (
                  <li key={s.n}>
                    <a href={s.url} target="_blank" rel="noreferrer" className={`flex items-center gap-3 rounded-2xl px-3 py-2 text-sm transition hover:bg-white/5 ${focusSource === s.n ? 'bg-gold/12 ring-1 ring-gold/50' : ''}`}>
                      <span className="rounded bg-gold/15 px-1.5 font-mono text-xs text-gold">S{s.n}</span>
                      <span className="min-w-0 flex-1 truncate text-white/80">{s.title}</span>
                      <span className="shrink-0 text-xs uppercase text-white/35">{s.lang} · {s.license}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}

        {country && !chron && !running && events.length === 0 && (
          <div className="glass max-w-xl rounded-[28px] p-6 text-sm text-white/70">
            This chronicle hasn't been rebuilt yet. Launch the agent: it reads the sources in French and English,
            then builds the timeline in a few dozen seconds.
          </div>
        )}
      </main>
      <Footer />
    </div>
  )
}

function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="glass rounded-2xl px-4 py-2.5">
      <span className="font-serif text-2xl">{value}</span>
      <span className="ml-2 text-xs text-white/50">{label}</span>
    </div>
  )
}
