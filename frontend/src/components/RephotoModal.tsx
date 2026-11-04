import { AnimatePresence, motion } from 'framer-motion'
import { Aperture, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Source } from '../lib/api'

/** Guide de re-photographie : l'archive en transparence sur la caméra, pour retrouver l'angle du photographe d'époque. */
export function RephotoModal({ open, archives, onClose, onCapture }: { open: boolean; archives: Source[]; onClose: () => void; onCapture: (f: File) => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [ref, setRef] = useState<Source | null>(null)
  const [opacity, setOpacity] = useState(0.45)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setRef(r => r ?? archives[0] ?? null)
    let s: MediaStream | null = null
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1920 } }, audio: false })
      .then(st => { s = st; setStream(st); if (video.current) video.current.srcObject = st })
      .catch(() => setError("Camera unavailable. Allow access, or use “My photo” with a picture you already took."))
    return () => { s?.getTracks().forEach(t => t.stop()); setStream(null) }
  }, [open, archives])

  const capture = () => {
    const v = video.current
    if (!v || !v.videoWidth) return
    const c = document.createElement('canvas')
    c.width = v.videoWidth
    c.height = v.videoHeight
    c.getContext('2d')!.drawImage(v, 0, 0)
    c.toBlob(b => {
      if (b) onCapture(new File([b], `rephoto-${Date.now()}.jpg`, { type: 'image/jpeg' }))
      onClose()
    }, 'image/jpeg', 0.92)
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[70] flex flex-col bg-black" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="relative flex-1 overflow-hidden">
            <video ref={video} autoPlay playsInline muted className="absolute inset-0 h-full w-full object-cover" />
            {ref && <img src={ref.image} alt="" className="pointer-events-none absolute inset-0 h-full w-full object-cover mix-blend-screen" style={{ opacity, filter: 'grayscale(1) contrast(1.2)' }} />}
            {!stream && !error && <p className="absolute inset-0 flex items-center justify-center text-white/60">Opening the camera…</p>}
            {error && <p className="absolute inset-x-6 top-1/2 text-center text-white/75">{error}</p>}
            <div className="glass glass-strong absolute left-4 right-4 top-4 flex items-center gap-3 rounded-full py-2 pl-5 pr-2 text-sm md:left-1/2 md:right-auto md:w-[520px] md:-translate-x-1/2">
              <span className="text-white/80">Line up the buildings with the archive, then take the shot.</span>
              <button onClick={onClose} className="glass glass-button ml-auto flex h-9 w-9 shrink-0 items-center justify-center rounded-full" aria-label="Close"><X size={16} /></button>
            </div>
          </div>
          <div className="glass glass-strong space-y-3 rounded-t-[28px] p-4">
            <div className="scrollbar-thin flex gap-2 overflow-x-auto">
              {archives.slice(0, 12).map(a => (
                <button key={a.id} onClick={() => setRef(a)} className={`h-14 w-20 shrink-0 overflow-hidden rounded-xl transition ${ref?.id === a.id ? 'ring-2 ring-gold' : 'opacity-55'}`}>
                  <img src={a.image} alt={a.title} className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
            <div className="flex items-center gap-4">
              <span className="text-xs text-white/50">Opacity</span>
              <input type="range" min={0} max={0.9} step={0.05} value={opacity} onChange={e => setOpacity(Number(e.target.value))} className="timeline flex-1" style={{ ['--fill' as string]: `${(opacity / 0.9) * 100}%` }} />
              <button onClick={capture} disabled={!stream} className="gold-button flex h-14 w-14 items-center justify-center rounded-full" aria-label="Take the photo"><Aperture size={22} /></button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
