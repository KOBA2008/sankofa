import { Music2, VolumeX } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

type Track = { id: string; title: string; artist: string; license: string; file: string; mood: string; instrument: string }

const KEY = 'sankofa.ambient'
const VOLUME = 0.22

function readEnabled() {
  try { return localStorage.getItem(KEY) !== 'off' } catch { return true }
}

/** Signale aux autres lecteurs qu'un média sonore démarre ou s'arrête (documentaire, lecture à voix haute). */
export function announceMedia(playing: boolean) {
  window.dispatchEvent(new CustomEvent('sankofa:media', { detail: { playing } }))
}

/**
 * Musique d'ambiance du site : morceaux calmes du domaine public, tirés au hasard, à faible volume.
 * Les navigateurs interdisent le son automatique : elle démarre au premier clic sur la page.
 * Elle s'efface quand un documentaire ou une lecture à voix haute commence.
 */
export function AmbientMusic() {
  const [enabled, setEnabled] = useState(readEnabled)
  const [track, setTrack] = useState<Track | null>(null)
  const [playing, setPlaying] = useState(false)
  const tracks = useRef<Track[]>([])
  const audio = useRef<HTMLAudioElement | null>(null)
  const fade = useRef<number>(undefined)
  const busy = useRef(false) // un autre média joue

  const fadeTo = (target: number, then?: () => void) => {
    const a = audio.current
    if (!a) return
    window.clearInterval(fade.current)
    fade.current = window.setInterval(() => {
      const step = target > a.volume ? 0.02 : -0.03
      const next = a.volume + step
      if ((step > 0 && next >= target) || (step < 0 && next <= target)) {
        a.volume = Math.max(0, Math.min(1, target))
        window.clearInterval(fade.current)
        then?.()
      } else a.volume = Math.max(0, Math.min(1, next))
    }, 60)
  }

  const pick = (avoid?: string) => {
    const pool = tracks.current.filter(t => t.id !== avoid)
    return pool[Math.floor(Math.random() * pool.length)] ?? null
  }

  const start = (t: Track | null) => {
    const a = audio.current
    if (!a || !t) return
    if (a.src !== new URL(t.file, location.href).href) { a.src = t.file; setTrack(t) }
    a.volume = 0
    a.play().then(() => { setPlaying(true); fadeTo(VOLUME) }).catch(() => setPlaying(false))
  }

  const stop = () => fadeTo(0, () => { audio.current?.pause(); setPlaying(false) })

  useEffect(() => {
    const a = new Audio()
    a.preload = 'none'
    audio.current = a
    a.addEventListener('ended', () => start(pick(tracks.current.find(t => a.src.endsWith(t.file))?.id)))
    fetch('/api/music').then(r => r.json()).then((list: Track[]) => {
      const calm = list.filter(t => t.mood === 'calme')
      tracks.current = calm.length ? calm : list
    }).catch(() => {})

    // premier geste de l'utilisateur : la seule façon autorisée de lancer le son
    const firstGesture = () => {
      if (readEnabled() && !busy.current && a.paused && tracks.current.length) start(pick())
    }
    window.addEventListener('pointerdown', firstGesture, { once: true })
    window.addEventListener('keydown', firstGesture, { once: true })

    const onMedia = (e: Event) => {
      const other = (e as CustomEvent<{ playing: boolean }>).detail.playing
      busy.current = other
      if (other) stop()
      else if (readEnabled() && a.src) a.play().then(() => { setPlaying(true); fadeTo(VOLUME) }).catch(() => {})
    }
    window.addEventListener('sankofa:media', onMedia)
    return () => {
      window.removeEventListener('pointerdown', firstGesture)
      window.removeEventListener('keydown', firstGesture)
      window.removeEventListener('sankofa:media', onMedia)
      window.clearInterval(fade.current)
      a.pause()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = () => {
    const next = !enabled
    setEnabled(next)
    try { localStorage.setItem(KEY, next ? 'on' : 'off') } catch { /* préférence non mémorisée */ }
    if (next && !busy.current) start(track ?? pick())
    else stop()
  }

  return (
    <button
      onClick={toggle}
      title={playing && track ? `Musique : ${track.title} (${track.license}). Cliquer pour couper.` : enabled ? 'Musique d\'ambiance : démarre au premier clic' : 'Activer la musique d\'ambiance'}
      aria-label={enabled ? 'Couper la musique d\'ambiance' : 'Activer la musique d\'ambiance'}
      className={`flex h-8 items-center gap-1.5 rounded-full px-3 text-xs transition ${enabled ? 'bg-gold/15 text-gold hover:bg-gold/25' : 'bg-white/8 text-white/55 hover:text-white'}`}
    >
      {enabled ? <Music2 size={14} /> : <VolumeX size={14} />}
      <span className="hidden sm:inline">{enabled ? 'Musique' : 'Muet'}</span>
      {enabled && playing && (
        <span className="flex h-3 items-end gap-[2px]" aria-hidden="true">
          {[0, 1, 2].map(i => <span key={i} className="w-[2px] rounded-full bg-gold" style={{ height: `${[60, 100, 40][i]}%` }} />)}
        </span>
      )}
    </button>
  )
}
