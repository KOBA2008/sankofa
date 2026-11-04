import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api, type Health } from '../lib/api'
import { AmbientMusic } from './AmbientMusic'

export function Logo({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <path d="M32 14c-9 0-15 6-15 13 0 6 4 10 10 10 4 0 7-3 7-6 0-3-2-5-5-5" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      <path d="M32 14c9 0 15 6 15 13 0 6-4 10-10 10" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      <path d="M32 37v13M24 50h16" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  )
}

export function Nav() {
  const [health, setHealth] = useState<Health | null>(null)
  const loc = useLocation()
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)) }, [])
  return (
    <header className="fixed inset-x-0 top-4 z-50 flex justify-center px-4">
      <nav className="glass glass-refract flex w-full max-w-6xl items-center justify-between rounded-full py-2 pl-4 pr-2">
        <Link to="/" className="flex items-center gap-2.5">
          <Logo className="h-7 w-7 text-gold" />
          <span className="font-serif text-2xl tracking-wide">Sankofa</span>
        </Link>
        <div className="hidden items-center gap-1 text-sm text-white/70 md:flex">
          <NavLink to="/" active={loc.pathname === '/' || loc.pathname.startsWith('/lieu')}>Villes</NavLink>
          <NavLink to="/pays" active={loc.pathname.startsWith('/pays')}>Pays</NavLink>
          <NavLink to="/methode" active={loc.pathname === '/methode'}>Méthode</NavLink>
        </div>
        <div className="flex items-center gap-2">
        <AmbientMusic />
        <div
          className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-xs ${health?.text_live ? 'bg-proof/15 text-proof' : 'bg-white/8 text-white/60'}`}
          title={health?.meta_live ? 'Modèles Meta branchés' : health?.text_live ? `Texte et vision : ${health.text_engine}. Segmentation et génération d'image : moteur local.` : 'Aucune clé API : moteur local de démonstration'}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${health?.text_live ? 'bg-proof' : 'bg-white/40'}`} />
          <span className="hidden sm:inline">{health ? (health.meta_live ? 'Meta Model API' : health.text_live ? 'Muse Spark · Baseten' : 'Mode local') : 'Hors ligne'}</span>
        </div>
        </div>
      </nav>
    </header>
  )
}

function NavLink({ to, active, children }: { to: string; active: boolean; children: React.ReactNode }) {
  return (
    <Link to={to} className={`rounded-full px-4 py-1.5 transition ${active ? 'bg-white/12 text-white' : 'hover:bg-white/6 hover:text-white'}`}>
      {children}
    </Link>
  )
}

/** Fond plein écran : les archives défilent en fondu, sous un voile sombre. */
export function Backdrop({ images, dim = 0.62 }: { images: string[]; dim?: number }) {
  const [i, setI] = useState(0)
  useEffect(() => {
    if (images.length < 2) return
    const id = setInterval(() => setI(v => (v + 1) % images.length), 7000)
    return () => clearInterval(id)
  }, [images.length])
  const src = images[i]
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden" aria-hidden="true">
      <AnimatePresence mode="sync">
        {src && (
          <motion.img
            key={src}
            src={src}
            alt=""
            className="absolute inset-0 h-full w-full object-cover"
            initial={{ opacity: 0, scale: 1.08 }}
            animate={{ opacity: 1, scale: 1.0 }}
            exit={{ opacity: 0 }}
            transition={{ opacity: { duration: 1.8 }, scale: { duration: 9, ease: 'linear' } }}
            style={{ filter: 'sepia(0.35) saturate(0.85)' }}
          />
        )}
      </AnimatePresence>
      <div className="absolute inset-0" style={{ background: `linear-gradient(180deg, rgba(7,8,11,${dim - 0.2}) 0%, rgba(7,8,11,${dim}) 45%, rgba(7,8,11,0.97) 100%)` }} />
      <div className="absolute inset-0" style={{ background: 'radial-gradient(70% 60% at 50% 30%, transparent, rgba(7,8,11,0.6))' }} />
    </div>
  )
}

export function Footer() {
  return (
    <footer className="mx-auto mt-24 max-w-6xl px-4 pb-10 text-xs text-white/40">
      <div className="glass flex flex-col gap-3 rounded-3xl p-6 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          <Logo className="h-5 w-5 text-gold" />
          <span>SANKOFA · Meta AI Developer Hackathon 2026</span>
        </div>
        <p className="max-w-xl">
          Archives : Wikimedia Commons (recherche par mots et par coordonnées GPS), Europeana (Rijksmuseum, archives nationales
          européennes), dont les Archives de la Planète du musée Albert-Kahn, la Library of Congress et la BnF.
          Chaque image garde sa licence et son lien d'origine. Cartes © OpenStreetMap, CARTO.
        </p>
      </div>
    </footer>
  )
}
