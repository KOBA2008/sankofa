import { AnimatePresence, motion } from 'framer-motion'
import { ImagePlus, Mic, X } from 'lucide-react'
import { useState } from 'react'
import { api, type Source } from '../lib/api'

export function ContributeModal({ open, placeId, onClose, onDone }: { open: boolean; placeId: string; onClose: () => void; onDone: (s: Source) => void }) {
  const [kind, setKind] = useState<'photo' | 'audio'>('photo')
  const [file, setFile] = useState<File | null>(null)
  const [year, setYear] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const s = await api.contribute(placeId, { kind, file, note, year: year ? Number(year) : undefined })
      onDone(s)
      setFile(null); setNote(''); setYear('')
      onClose()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[70] flex items-end justify-center bg-black/60 p-4 backdrop-blur-sm md:items-center" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div
            className="glass glass-strong w-full max-w-lg rounded-[28px] p-6"
            initial={{ y: 40, scale: 0.97 }} animate={{ y: 0, scale: 1 }} exit={{ y: 40, opacity: 0 }}
            transition={{ type: 'spring', bounce: 0.2 }}
            onClick={e => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h3 className="font-serif text-3xl">Add to the memory</h3>
                <p className="mt-1 text-sm text-white/55">Your contribution joins the corpus marked “unverified” until it is reviewed.</p>
              </div>
              <button onClick={onClose} className="glass glass-button flex h-9 w-9 items-center justify-center rounded-full" aria-label="Close"><X size={16} /></button>
            </div>

            <div className="mb-4 grid grid-cols-2 gap-2">
              {([['photo', 'Old photo', ImagePlus], ['audio', 'Oral testimony', Mic]] as const).map(([k, label, Icon]) => (
                <button key={k} onClick={() => { setKind(k); setFile(null) }} className={`flex items-center justify-center gap-2 rounded-2xl px-3 py-3 text-sm transition ${kind === k ? 'bg-gold/15 text-gold ring-1 ring-gold/50' : 'bg-black/25 text-white/60 hover:text-white'}`}>
                  <Icon size={16} /> {label}
                </button>
              ))}
            </div>

            <label className="mb-3 flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-white/20 bg-black/20 px-4 py-6 text-center text-sm text-white/60 hover:border-gold/50">
              <input type="file" className="hidden" accept={kind === 'photo' ? 'image/*' : 'audio/*'} onChange={e => setFile(e.target.files?.[0] ?? null)} />
              {file ? <span className="text-white">{file.name}</span> : <span>{kind === 'photo' ? 'Choose a photo' : 'Choose a recording (Fon, Gungbe, Wolof, French…)'}</span>}
            </label>

            <div className="mb-3 grid grid-cols-3 gap-2">
              <input value={year} onChange={e => setYear(e.target.value.replace(/\D/g, '').slice(0, 4))} placeholder="Year" className="rounded-2xl bg-black/25 px-4 py-3 text-sm outline-none ring-1 ring-white/10 focus:ring-gold/50" />
              <input value={note} onChange={e => setNote(e.target.value)} placeholder="What this document shows or tells" className="col-span-2 rounded-2xl bg-black/25 px-4 py-3 text-sm outline-none ring-1 ring-white/10 focus:ring-gold/50" />
            </div>
            {error && <p className="mb-3 text-sm text-red-300">{error}</p>}
            <button disabled={!file || busy} onClick={submit} className="gold-button w-full rounded-full px-5 py-3 text-sm font-semibold">
              {busy ? 'Sending…' : 'Add to the corpus'}
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
