import { AnimatePresence, motion } from 'framer-motion'
import {
  Download, Loader2, Maximize, Minimize, Music2, Pause, Play, RectangleHorizontal, Shuffle, SkipBack, SkipForward,
  Square, Volume2, VolumeX,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'

export type Scene = {
  type: 'title' | 'chapter' | 'event' | 'compare' | 'gap' | 'credits'
  image: string | null
  image_b?: string
  title?: string
  subtitle?: string
  eyebrow?: string
  year?: string
  text?: string
  badge?: string
  source?: string
  caption?: string | null
  lines?: string[]
  duration: number
}

export type Storyboard = {
  kind: 'country' | 'place'
  id: string
  title: string
  scenes: Scene[]
  music: { title: string; artist: string; license: string; file: string; instrument: string; page_url: string } | null
  seed: number
  total: number
}

type Size = 'petit' | 'moyen' | 'cinema'
const WIDTHS: Record<Size, string> = { petit: 'max-w-2xl', moyen: 'max-w-4xl', cinema: 'max-w-none' }
const SIZE_KEY = 'sankofa.player.size'

function readSize(): Size {
  try {
    const v = localStorage.getItem(SIZE_KEY)
    return v === 'petit' || v === 'cinema' ? v : 'moyen'
  } catch { return 'moyen' }
}

type Props = { kind: 'country' | 'place'; id: string; run?: string; title: string }

/** Lecteur intégré à la page, façon YouTube : archives en mouvement, texte à l'écran, musique libre de droits. */
export function DocumentaryPlayer({ kind, id, run, title }: Props) {
  const [board, setBoard] = useState<Storyboard | null>(null)
  const [index, setIndex] = useState(0)
  const [offset, setOffset] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [started, setStarted] = useState(false)
  const [volume, setVolume] = useState(0.8)
  const [muted, setMuted] = useState(false)
  const [size, setSize] = useState<Size>(readSize)
  const [fullscreen, setFullscreen] = useState(false)
  const [controls, setControls] = useState(true)
  const [exporting, setExporting] = useState<number | null>(null)
  const [video, setVideo] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const audio = useRef<HTMLAudioElement>(null)
  const frame = useRef<HTMLDivElement>(null)
  const hideTimer = useRef<number>(undefined)
  const stopExport = useRef<() => void>(undefined)

  const load = useCallback((seed?: number) => {
    const q = new URLSearchParams()
    if (seed !== undefined) q.set('seed', String(seed))
    if (run) q.set('run', run)
    setError(null)
    fetch(`/api/documentary/${kind}/${id}?${q}`)
      .then(async r => { if (!r.ok) throw new Error((await r.json()).detail); return r.json() })
      .then((b: Storyboard) => { setBoard(b); setVideo(null) })
      .catch(e => setError(e.message))
  }, [kind, id, run])

  useEffect(() => { load(); return () => { audio.current?.pause(); stopExport.current?.() } }, [load])

  const starts = useMemo(() => {
    let t = 0
    return board?.scenes.map(s => { const v = t; t += s.duration; return v }) ?? []
  }, [board])
  const elapsed = (starts[index] ?? 0) + offset

  // horloge : avance de plan en plan
  useEffect(() => {
    if (!playing || !board) return
    const scene = board.scenes[index]
    const t0 = performance.now() - offset * 1000
    const tick = setInterval(() => {
      const t = (performance.now() - t0) / 1000
      if (t >= scene.duration) {
        if (index + 1 < board.scenes.length) { setIndex(index + 1); setOffset(0) }
        else { setPlaying(false); setOffset(scene.duration); audio.current?.pause() }
      } else setOffset(t)
    }, 100)
    return () => clearInterval(tick)
  }, [playing, index, board]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (audio.current) audio.current.volume = muted ? 0 : volume }, [volume, muted])

  useEffect(() => {
    const onFs = () => setFullscreen(document.fullscreenElement === frame.current)
    document.addEventListener('fullscreenchange', onFs)
    return () => document.removeEventListener('fullscreenchange', onFs)
  }, [])

  const play = () => {
    setStarted(true); setPlaying(true)
    audio.current?.play().catch(() => {})
  }
  const pause = () => { setPlaying(false); audio.current?.pause() }
  const toggle = () => (playing ? pause() : play())

  const seekTo = (t: number) => {
    if (!board) return
    const clamped = Math.max(0, Math.min(board.total - 0.05, t))
    let i = starts.findIndex((s, k) => clamped >= s && clamped < s + board.scenes[k].duration)
    if (i < 0) i = board.scenes.length - 1
    setIndex(i); setOffset(clamped - starts[i])
    if (audio.current && audio.current.duration) audio.current.currentTime = clamped % audio.current.duration
    setStarted(true)
  }
  const jump = (d: number) => board && seekTo(starts[Math.max(0, Math.min(board.scenes.length - 1, index + d))] ?? 0)

  const changeSize = (s: Size) => {
    setSize(s)
    try { localStorage.setItem(SIZE_KEY, s) } catch { /* stockage indisponible : la taille n'est pas mémorisée */ }
  }
  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen()
    else frame.current?.requestFullscreen?.()
  }

  const reshuffle = () => { pause(); setStarted(false); setIndex(0); setOffset(0); load(Math.floor(Math.random() * 1e6)) }

  const exportVideo = async () => {
    if (!board) return
    setExporting(0); setVideo(null); setError(null)
    const fd = new FormData()
    fd.append('seed', String(board.seed))
    if (run) fd.append('run', run)
    try {
      const r = await fetch(`/api/documentary/${kind}/${id}/video`, { method: 'POST', body: fd })
      if (!r.ok) throw new Error((await r.json()).detail)
      const { run_id } = await r.json()
      stopExport.current = api.stream(run_id, ev => {
        if (typeof ev.data.progress === 'number') setExporting(ev.data.progress as number)
        if (ev.step === 'done') { setVideo((ev.data.result as { video: string }).video); setExporting(null) }
        if (ev.step === 'error') { setError(ev.message); setExporting(null) }
      })
    } catch (e) { setError((e as Error).message); setExporting(null) }
  }

  // les commandes s'effacent pendant la lecture, comme sur YouTube
  const wake = () => {
    setControls(true)
    window.clearTimeout(hideTimer.current)
    hideTimer.current = window.setTimeout(() => setControls(false), 2600)
  }

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === ' ' || e.key === 'k') { e.preventDefault(); toggle() }
    if (e.key === 'ArrowRight') jump(1)
    if (e.key === 'ArrowLeft') jump(-1)
    if (e.key === 'f') toggleFullscreen()
    if (e.key === 'm') setMuted(m => !m)
    wake()
  }

  const scene = board?.scenes[index]
  const chapters = board?.scenes.map((s, i) => ({ s, i })).filter(({ s }) => s.type === 'chapter' || s.type === 'title' || s.type === 'compare' || s.type === 'gap' || s.type === 'credits') ?? []
  const showControls = controls || !playing

  return (
    <section className={`mx-auto w-full transition-[max-width] duration-500 ${fullscreen ? '' : WIDTHS[size]}`}>
      <div
        ref={frame}
        tabIndex={0}
        onKeyDown={onKey}
        onMouseMove={wake}
        onMouseLeave={() => playing && setControls(false)}
        className={`group relative overflow-hidden bg-black outline-none [container-type:inline-size] ${fullscreen ? 'h-screen w-screen' : 'aspect-video rounded-[24px] shadow-[0_30px_80px_-30px_rgba(0,0,0,.9)] ring-1 ring-white/10'}`}
        style={{ cursor: playing && !controls ? 'none' : undefined }}
      >
        {board?.music && <audio ref={audio} src={board.music.file} loop preload="auto" />}

        <div className="absolute inset-0" onClick={() => (started ? toggle() : play())}>
          <AnimatePresence mode="sync">
            {scene && <SceneView key={index} scene={scene} index={index} playing={playing || !started} />}
          </AnimatePresence>
        </div>

        {!started && board && (
          <button onClick={play} className="absolute inset-0 flex items-center justify-center bg-black/30" aria-label="Lire le documentaire">
            <span className="gold-button flex items-center justify-center rounded-full" style={{ width: 'max(56px, 9cqw)', height: 'max(56px, 9cqw)' }}>
              <Play style={{ width: '38%', height: '38%' }} />
            </span>
          </button>
        )}
        {!board && !error && <div className="absolute inset-0 flex items-center justify-center text-white/60"><Loader2 className="animate-spin" /></div>}
        {error && <p className="absolute inset-x-0 top-1/2 px-6 text-center text-sm text-red-300">{error}</p>}

        {/* barre de commandes */}
        {board && started && (
          <div className={`absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/40 to-transparent px-3 pb-2 pt-10 transition-opacity duration-300 ${showControls ? 'opacity-100' : 'opacity-0'}`}>
            <Progress board={board} starts={starts} elapsed={elapsed} onSeek={seekTo} />
            <div className="mt-1.5 flex items-center gap-1 text-white">
              <IconBtn label="Plan précédent" onClick={() => jump(-1)}><SkipBack size={18} /></IconBtn>
              <IconBtn label={playing ? 'Pause (espace)' : 'Lecture (espace)'} onClick={toggle}>{playing ? <Pause size={20} /> : <Play size={20} />}</IconBtn>
              <IconBtn label="Plan suivant" onClick={() => jump(1)}><SkipForward size={18} /></IconBtn>
              <div className="group/vol flex items-center">
                <IconBtn label={muted ? 'Activer le son (m)' : 'Couper le son (m)'} onClick={() => setMuted(m => !m)}>{muted || volume === 0 ? <VolumeX size={18} /> : <Volume2 size={18} />}</IconBtn>
                <input
                  type="range" min={0} max={1} step={0.05} value={muted ? 0 : volume} aria-label="Volume"
                  onChange={e => { setVolume(Number(e.target.value)); setMuted(false) }}
                  className="timeline w-0 opacity-0 transition-all duration-300 group-hover/vol:ml-1 group-hover/vol:w-20 group-hover/vol:opacity-100"
                  style={{ ['--fill' as string]: `${(muted ? 0 : volume) * 100}%` }}
                />
              </div>
              <span className="ml-2 font-mono text-xs text-white/80">{fmt(elapsed)} / {fmt(board.total)}</span>
              {scene && <span className="ml-3 hidden truncate text-xs text-white/60 sm:inline">· {currentChapter(board, index)}</span>}
              <div className="ml-auto flex items-center gap-1">
                {!fullscreen && (['petit', 'moyen', 'cinema'] as const).map(s => (
                  <IconBtn key={s} label={`Taille : ${s === 'cinema' ? 'cinéma' : s}`} onClick={() => changeSize(s)} active={size === s}>
                    {s === 'petit' ? <Square size={13} /> : s === 'moyen' ? <Square size={17} /> : <RectangleHorizontal size={20} />}
                  </IconBtn>
                ))}
                <IconBtn label={fullscreen ? 'Quitter le plein écran (f)' : 'Plein écran (f)'} onClick={toggleFullscreen}>{fullscreen ? <Minimize size={18} /> : <Maximize size={18} />}</IconBtn>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* sous la vidéo : titre, informations, chapitres, actions */}
      {board && !fullscreen && (
        <div className="mt-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="font-serif text-3xl leading-tight">{title}</h2>
              <p className="mt-1 text-sm text-white/55">
                Documentaire · {fmt(board.total)} · {board.scenes.length} plans · archives et texte à l'écran
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button onClick={reshuffle} className="glass glass-button inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm"><Shuffle size={14} /> Autre musique</button>
              {video ? (
                <a href={video} download className="gold-button inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold"><Download size={14} /> Télécharger le MP4</a>
              ) : (
                <button onClick={exportVideo} disabled={exporting !== null} className="gold-button inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold">
                  {exporting !== null ? <><Loader2 size={14} className="animate-spin" /> Montage {Math.round(exporting * 100)} %</> : <><Download size={14} /> Exporter en MP4</>}
                </button>
              )}
            </div>
          </div>

          <div className="glass mt-4 grid gap-4 rounded-[22px] p-4 md:grid-cols-[1fr_1.2fr]">
            <div className="text-sm text-white/70">
              {board.music && (
                <p className="flex items-start gap-2">
                  <Music2 size={15} className="mt-0.5 shrink-0 text-gold" />
                  <span>
                    <span className="text-white/90">{board.music.title}</span>
                    <span className="block text-xs text-white/45">{board.music.artist || 'Interprète non crédité'} · {board.music.license} ·{' '}
                      <a href={board.music.page_url} target="_blank" rel="noreferrer" className="underline decoration-white/20 hover:text-gold">notice</a>
                    </span>
                  </span>
                </p>
              )}
              <p className="mt-3 text-xs leading-relaxed text-white/45">
                Raccourcis : espace lecture/pause · ← → plan précédent/suivant · f plein écran · m son.
                Aucune image n'est inventée : chaque photo porte sa date et sa source au générique.
              </p>
            </div>
            <ol className="scrollbar-thin max-h-56 space-y-0.5 overflow-auto pr-1">
              {chapters.map(({ s, i }) => (
                <li key={i}>
                  <button
                    onClick={() => { seekTo(starts[i]); if (!playing) play() }}
                    className={`flex w-full items-center gap-3 rounded-xl px-2.5 py-1.5 text-left text-sm transition hover:bg-white/6 ${currentChapterIndex(board, index) === i ? 'bg-white/8 text-white' : 'text-white/70'}`}
                  >
                    <span className="w-11 shrink-0 font-mono text-xs text-gold">{fmt(starts[i])}</span>
                    <span className="truncate">{s.title ?? s.type}</span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </section>
  )
}

function currentChapterIndex(board: Storyboard, index: number) {
  for (let i = index; i >= 0; i--) {
    if (['chapter', 'title', 'compare', 'gap', 'credits'].includes(board.scenes[i].type)) return i
  }
  return 0
}

function currentChapter(board: Storyboard, index: number) {
  return board.scenes[currentChapterIndex(board, index)].title ?? ''
}

function IconBtn({ label, onClick, active, children }: { label: string; onClick: () => void; active?: boolean; children: React.ReactNode }) {
  return (
    <button
      onClick={e => { e.stopPropagation(); onClick() }}
      title={label}
      aria-label={label}
      className={`flex h-9 min-w-9 items-center justify-center rounded-full px-1.5 transition hover:bg-white/15 ${active ? 'text-gold' : ''}`}
    >
      {children}
    </button>
  )
}

/** Barre de progression cliquable, avec un repère à chaque chapitre. */
function Progress({ board, starts, elapsed, onSeek }: { board: Storyboard; starts: number[]; elapsed: number; onSeek: (t: number) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<number | null>(null)
  const at = (x: number) => {
    const r = ref.current!.getBoundingClientRect()
    return Math.max(0, Math.min(1, (x - r.left) / r.width)) * board.total
  }
  const marks = board.scenes.map((s, i) => ({ s, t: starts[i] })).filter(({ s, t }) => t > 0 && (s.type === 'chapter' || s.type === 'gap' || s.type === 'credits' || s.type === 'compare'))
  return (
    <div
      ref={ref}
      className="group/bar relative flex h-4 cursor-pointer items-center"
      onClick={e => { e.stopPropagation(); onSeek(at(e.clientX)) }}
      onMouseMove={e => setHover(at(e.clientX))}
      onMouseLeave={() => setHover(null)}
    >
      <div className="relative h-1 w-full overflow-hidden rounded-full bg-white/25 transition-all group-hover/bar:h-1.5">
        {hover !== null && <div className="absolute inset-y-0 left-0 bg-white/30" style={{ width: `${(hover / board.total) * 100}%` }} />}
        <div className="absolute inset-y-0 left-0 bg-gold" style={{ width: `${(elapsed / board.total) * 100}%` }} />
        {marks.map(({ t }) => <span key={t} className="absolute inset-y-0 w-0.5 bg-black/70" style={{ left: `${(t / board.total) * 100}%` }} />)}
      </div>
      <span className="absolute h-3.5 w-3.5 -translate-x-1/2 scale-0 rounded-full bg-gold transition group-hover/bar:scale-100" style={{ left: `${(elapsed / board.total) * 100}%` }} />
      {hover !== null && (
        <span className="pointer-events-none absolute -top-7 -translate-x-1/2 rounded-md bg-black/80 px-1.5 py-0.5 font-mono text-xs" style={{ left: `${(hover / board.total) * 100}%` }}>{fmt(hover)}</span>
      )}
    </div>
  )
}

function fmt(s: number) {
  const m = Math.floor(s / 60)
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

/** Un plan. Les tailles de texte sont en cqw : elles suivent la largeur du lecteur, du petit format au plein écran. */
function SceneView({ scene, index, playing }: { scene: Scene; index: number; playing: boolean }) {
  const zoomIn = index % 2 === 0
  const appear = { initial: { opacity: 0, y: 14 }, animate: { opacity: 1, y: 0 }, transition: { delay: 0.45, duration: 0.9 } }
  const shade = scene.type === 'event' || scene.type === 'compare'
    ? 'linear-gradient(180deg, transparent 32%, rgba(0,0,0,.9))'
    : 'linear-gradient(180deg, rgba(0,0,0,.2), rgba(0,0,0,.72))'
  return (
    <motion.div className="absolute inset-0" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 1 }}>
      {scene.image ? (
        <motion.img
          src={scene.image} alt="" draggable={false}
          className="absolute inset-0 h-full w-full object-cover"
          style={{ filter: scene.type === 'gap' || scene.type === 'credits' ? 'blur(8px) brightness(.5)' : undefined }}
          initial={{ scale: zoomIn ? 1.02 : 1.15, x: zoomIn ? '-1.5%' : '1.5%' }}
          animate={playing ? { scale: zoomIn ? 1.15 : 1.02, x: zoomIn ? '1.5%' : '-1.5%' } : undefined}
          transition={{ duration: scene.duration + 1.2, ease: 'linear' }}
        />
      ) : (
        <div className="absolute inset-0" style={{ background: 'radial-gradient(80% 70% at 35% 30%, #2a2f38, #0b0c10 70%)' }} />
      )}
      {scene.image_b && (
        <motion.img
          src={scene.image_b} alt="" draggable={false} className="absolute inset-0 h-full w-full object-cover"
          initial={{ opacity: 0 }} animate={{ opacity: playing ? 1 : 0 }}
          transition={{ delay: scene.duration * 0.3, duration: scene.duration * 0.4 }}
        />
      )}
      <div className="absolute inset-0" style={{ background: shade }} />

      <div className="absolute inset-0 flex flex-col justify-end" style={{ padding: '6cqw 7cqw 9cqw' }}>
        {scene.caption && <p className="absolute font-mono text-white/65" style={{ right: '7cqw', top: '4cqw', fontSize: 'max(10px, 1.15cqw)' }}>{scene.caption}</p>}
        {scene.type === 'title' && (
          <motion.div {...appear} style={{ marginBottom: '12cqw' }}>
            <p className="font-mono uppercase tracking-[0.25em] text-gold" style={{ fontSize: 'max(10px, 1.3cqw)' }}>{scene.eyebrow}</p>
            <h3 className="font-serif leading-none" style={{ fontSize: '10cqw' }}>{scene.title}</h3>
            <p className="font-serif italic text-gold-soft" style={{ fontSize: '3.4cqw', marginTop: '1cqw' }}>{scene.subtitle}</p>
          </motion.div>
        )}
        {scene.type === 'chapter' && (
          <motion.div {...appear} style={{ marginBottom: '4cqw' }}>
            <p className="font-mono text-gold" style={{ fontSize: 'max(11px, 1.7cqw)' }}>{scene.year}</p>
            <h3 className="font-serif leading-[1.05]" style={{ fontSize: '6.2cqw', maxWidth: '80cqw' }}>{scene.title}</h3>
          </motion.div>
        )}
        {(scene.type === 'event' || scene.type === 'compare') && (
          <motion.div {...appear} style={{ maxWidth: '82cqw' }}>
            <div className="flex items-end justify-between gap-4">
              <p className="font-serif text-gold-soft" style={{ fontSize: '5.4cqw', lineHeight: 1 }}>{scene.year}</p>
              {scene.badge && (
                <span
                  className={`shrink-0 rounded-full ${scene.badge === 'recoupé' ? 'bg-proof/20 text-proof' : scene.badge === 'source unique' ? 'bg-guess/20 text-guess' : 'bg-white/12 text-white/80'}`}
                  style={{ fontSize: 'max(10px, 1.2cqw)', padding: '0.35cqw 1cqw' }}
                >
                  ● {scene.badge}{scene.source ? ` · ${scene.source}` : ''}
                </span>
              )}
            </div>
            {scene.type === 'compare' && scene.title && <p className="font-serif italic" style={{ fontSize: '2.8cqw', marginTop: '0.8cqw' }}>{scene.title}</p>}
            {scene.text && (
              <p className="font-medium text-white/95 [text-shadow:0_1px_12px_rgba(0,0,0,.6)]" style={{ fontSize: 'max(13px, 2.05cqw)', lineHeight: 1.45, marginTop: '1.2cqw' }}>
                « {scene.text} »
              </p>
            )}
          </motion.div>
        )}
        {scene.type === 'gap' && (
          <motion.div {...appear} style={{ marginBottom: '8cqw', maxWidth: '75cqw' }}>
            <h3 className="font-serif text-guess" style={{ fontSize: '5cqw', lineHeight: 1.05 }}>{scene.title}</h3>
            <p className="font-medium text-white/90" style={{ fontSize: 'max(13px, 2.1cqw)', lineHeight: 1.45, marginTop: '1.5cqw' }}>{scene.text}</p>
          </motion.div>
        )}
        {scene.type === 'credits' && (
          <motion.div {...appear} className="mb-auto" style={{ maxWidth: '86cqw' }}>
            <h3 className="font-serif text-gold-soft" style={{ fontSize: '4.4cqw' }}>{scene.title}</h3>
            <ul className="text-white/70" style={{ fontSize: 'max(9px, 1.15cqw)', lineHeight: 1.6, marginTop: '1.2cqw' }}>
              {scene.lines?.map(l => <li key={l} className="truncate">{l}</li>)}
            </ul>
            <p className="font-mono text-gold" style={{ fontSize: 'max(9px, 1.1cqw)', marginTop: '1.5cqw' }}>SANKOFA · aucune image n'a été inventée</p>
          </motion.div>
        )}
      </div>
    </motion.div>
  )
}
