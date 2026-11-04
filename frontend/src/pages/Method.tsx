import { motion } from 'framer-motion'
import { Backdrop, Footer } from '../components/Chrome'
import { STEPS } from '../components/AgentTimeline'

const DETAILS: Record<string, { what: string; model: string }> = {
  enquete: { what: 'The agent queries open archives: Wikimedia Commons by keyword and by GPS coordinates (every photo taken within a few hundred meters of the place), and Europeana (Rijksmuseum, European national archives). It keeps only openly licensed material, discards engravings, stamps and namesakes (the “Flatiron” in Florida, the “Puerta del Sol” in Toledo), then asks Muse Spark to check on the image itself that the document really shows the place.', model: 'Muse Spark (vision)' },
  annotation: { what: "Today's view is split into elements: facades, roofs, street, sky, monuments. Each element will then get its own verdict.", model: 'SAM 3.1 (concept segmentation)' },
  alignement: { what: "Re-photography: the agent looks for matching points between each old photo and today's view, then computes the transformation that overlays them. An archive that can be overlaid becomes localized evidence.", model: 'Multi-view geometry (SIFT + RANSAC)' },
  style: { what: "The agent learns the city's photographic look in the target era: tone curve, tint, grain. This profile is saved and reused for every place in the city.", model: 'Profile learned from the corpus' },
  reconstruction: { what: 'Areas proven by an archive are rebuilt from the archive itself. Only areas without evidence are handed to the generative model, with a prompt written from the sources.', model: 'Muse Image (masked editing)' },
  evaluation: { what: 'The agent hides an archive, reconstructs without it, then compares. It computes a reliability score from the share of buildings backed by evidence, the richness of the corpus and this blind test.', model: 'SSIM, evidence coverage' },
  recit: { what: 'A short story, in English and French, where every factual sentence cites its source. Anything that does not come from the sources is presented as context.', model: 'Muse Spark' },
}

export default function Method() {
  return (
    <div>
      <Backdrop images={[]} />
      <main className="mx-auto max-w-4xl px-4 pt-32">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold">Method</p>
        <h1 className="mt-2 text-balance font-serif text-6xl leading-none">Generative AI that separates the proven from the imagined.</h1>
        <p className="mt-6 text-lg leading-relaxed text-white/70">
          Generated images are beautiful, but they make things up. Sankofa flips the logic: archives first,
          imagination only where no evidence exists, and always flagged. Every element of the image gets a verdict.
        </p>
        <div className="mt-8 grid grid-cols-3 gap-3 text-sm">
          {[['#34d399', 'Documented', 'An overlaid archive shows this area as it was.'], ['#cbd5e1', 'Unchanged', 'The archive shows the same structure as today.'], ['#fbbf24', 'Hypothesis', 'No evidence: a plausible reconstruction, still to be confirmed.']].map(([c, t, d]) => (
            <div key={t} className="glass rounded-3xl p-4">
              <div className="mb-2 flex items-center gap-2 font-medium"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />{t}</div>
              <p className="text-xs leading-relaxed text-white/60">{d}</p>
            </div>
          ))}
        </div>

        <ol className="mt-16 space-y-4">
          {STEPS.map((s, i) => (
            <motion.li key={s.id} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.6 }} className="glass flex gap-5 rounded-[28px] p-6">
              <div className="flex flex-col items-center">
                <span className="flex h-11 w-11 items-center justify-center rounded-full bg-gold/15 text-gold"><s.icon size={18} /></span>
                <span className="mt-2 font-mono text-xs text-white/35">0{i + 1}</span>
              </div>
              <div>
                <h2 className="font-serif text-3xl">{s.label}</h2>
                <p className="mt-2 text-sm leading-relaxed text-white/70">{DETAILS[s.id].what}</p>
                <p className="mt-3 inline-block rounded-full bg-sky-400/10 px-3 py-1 font-mono text-xs text-sky-300">{DETAILS[s.id].model}</p>
              </div>
            </motion.li>
          ))}
        </ol>

        <div className="glass mt-16 rounded-[28px] p-6 text-sm leading-relaxed text-white/70">
          <h2 className="mb-2 font-serif text-3xl text-white">Known limits</h2>
          <p>
            When no archive was taken from the same angle as today's view, the blind test is not possible:
            the displayed reliability is then capped at 70% and every facade stays marked as a hypothesis.
            The agent says so, and asks the community for the documents it is missing.
          </p>
        </div>
      </main>
      <Footer />
    </div>
  )
}
