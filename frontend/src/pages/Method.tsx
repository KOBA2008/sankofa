import { motion } from 'framer-motion'
import { Backdrop, Footer } from '../components/Chrome'
import { STEPS } from '../components/AgentTimeline'

const DETAILS: Record<string, { what: string; model: string }> = {
  enquete: { what: "L'agent interroge les archives ouvertes : Wikimedia Commons par mots-clés et par coordonnées GPS (toutes les photos prises à quelques centaines de mètres du lieu), Europeana (Rijksmuseum, archives nationales européennes). Il ne garde que les licences libres, écarte les gravures, timbres et homonymes (le « Flatiron » de Floride, la « Puerta del Sol » de Tolède), puis demande à Muse Spark de vérifier sur l'image que le document montre bien le lieu.", model: 'Muse Spark (vision)' },
  annotation: { what: 'La vue actuelle est découpée en éléments : façades, toits, rue, ciel, monuments. Chaque élément recevra ensuite son propre verdict.', model: 'SAM 3.1 (segmentation par concepts)' },
  alignement: { what: "Re-photographie : l'agent cherche des points communs entre chaque photo ancienne et la vue actuelle, puis calcule la transformation qui les superpose. Une archive superposable devient une preuve localisée.", model: 'Géométrie multi-vues (SIFT + RANSAC)' },
  style: { what: "L'agent apprend le rendu photographique de la ville à l'époque visée : courbe tonale, teinte, grain. Ce profil est enregistré et réutilisé pour tous les lieux de la ville.", model: 'Profil appris sur le corpus' },
  reconstruction: { what: "Les zones prouvées par une archive sont reconstruites à partir de l'archive elle-même. Seules les zones sans preuve sont confiées au modèle génératif, avec une consigne écrite d'après les sources.", model: 'Muse Image (retouche par masque)' },
  evaluation: { what: "L'agent cache une archive, reconstruit sans elle, puis compare. Il calcule une fiabilité à partir de la part du bâti appuyée sur une preuve, de la richesse du corpus et de ce test à l'aveugle.", model: 'SSIM, recouvrement des preuves' },
  recit: { what: 'Un récit court, en français et en anglais, où chaque phrase factuelle cite sa source. Ce qui ne vient pas des sources est présenté comme contexte.', model: 'Muse Spark' },
}

export default function Method() {
  return (
    <div>
      <Backdrop images={[]} />
      <main className="mx-auto max-w-4xl px-4 pt-32">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold">Méthode</p>
        <h1 className="mt-2 text-balance font-serif text-6xl leading-none">Une IA générative qui sépare le prouvé de l'imaginé.</h1>
        <p className="mt-6 text-lg leading-relaxed text-white/70">
          Les images générées sont belles, mais elles inventent. Sankofa inverse la logique : les archives d'abord,
          l'imagination seulement là où aucune preuve n'existe, et toujours signalée. Chaque élément de l'image reçoit un verdict.
        </p>
        <div className="mt-8 grid grid-cols-3 gap-3 text-sm">
          {[['#34d399', 'Documenté', "Une archive superposée montre cette zone telle qu'elle était."], ['#cbd5e1', 'Inchangé', "L'archive montre la même structure qu'aujourd'hui."], ['#fbbf24', 'Hypothèse', "Aucune preuve : reconstruction plausible, à confirmer."]].map(([c, t, d]) => (
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
          <h2 className="mb-2 font-serif text-3xl text-white">Limites assumées</h2>
          <p>
            Quand aucune archive n'est prise sous le même angle que la vue actuelle, le test à l'aveugle est impossible :
            la fiabilité affichée plafonne alors à 70 % et toutes les façades restent marquées comme hypothèses.
            L'agent le dit, et demande à la communauté les documents qui lui manquent.
          </p>
        </div>
      </main>
      <Footer />
    </div>
  )
}
