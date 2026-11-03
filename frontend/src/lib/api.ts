export type Source = {
  id: string
  n?: number
  title: string
  year: number | null
  date_raw?: string
  license: string
  artist?: string
  page_url?: string
  source?: string
  description?: string
  image: string
  verified?: boolean
  kind?: string
  transcript?: string
  note?: string
}

export type PlaceSummary = {
  id: string
  continent: string
  city: string
  country: string
  name: string
  lat: number
  lon: number
  era: number
  context: string
  n_archives: number
  n_currents: number
  n_contributions: number
  span: [number, number] | null
  cover: string | null
  current_cover: string | null
}

export type PlaceDetail = PlaceSummary & {
  archives: Source[]
  currents: Source[]
  contributions: Source[]
}

export type TagStatus = 'documente' | 'inchange' | 'hypothese'

export type Tag = {
  id: string
  label: string
  status: TagStatus
  note: string
  confidence: number
  coverage: number
  sources: string[]
  polygon: [number, number][]
  bbox: [number, number, number, number]
}

export type Evaluation = {
  reliability: number
  evidence_share: number
  holdout: { archive: string; title: string; year: number; ssim: number; baseline: number; others: number }[]
  holdout_score: number | null
  source_richness: number
  n_sources: number
  gaps: { tag: string; side: string; question: string }[]
}

export type RunResult = {
  run: string
  place: PlaceSummary
  year: number
  current: string
  reconstruction: string
  size: [number, number]
  tags: Tag[]
  counts: Record<TagStatus, number>
  evaluation: Evaluation
  story: { title: string; fr: string; en: string }
  sources: Source[]
  aligned: string[]
  nearest: (Source & { inliers: number; aligned: boolean })[]
  engines: Record<string, string>
  style: { decade: number; tint: number[] }
}

export type AgentEvent = {
  t: number
  step: string
  status: 'running' | 'log' | 'done' | 'error'
  message: string
  engine: string
  data: Record<string, unknown>
}

export type Health = { ok: boolean; meta_live: boolean; text_live: boolean; text_engine: string; last_error: string | null; models: Record<string, string> }

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Erreur ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: () => fetch('/api/health').then(r => json<Health>(r)),
  places: () => fetch('/api/places').then(r => json<PlaceSummary[]>(r)),
  place: (id: string) => fetch(`/api/places/${id}`).then(r => json<PlaceDetail>(r)),
  startRun: (id: string, opts: { year: number; currentId?: string; photo?: File }) => {
    const fd = new FormData()
    fd.append('year', String(opts.year))
    if (opts.currentId) fd.append('current_id', opts.currentId)
    if (opts.photo) fd.append('photo', opts.photo)
    return fetch(`/api/places/${id}/runs`, { method: 'POST', body: fd }).then(r => json<{ run_id: string }>(r))
  },
  run: (runId: string) => fetch(`/api/runs/${runId}`).then(r => json<{ status: string; result: RunResult | null }>(r)),
  stream: (runId: string, onEvent: (e: AgentEvent) => void) => {
    const es = new EventSource(`/api/runs/${runId}/stream`)
    es.onmessage = m => onEvent(JSON.parse(m.data))
    es.onerror = () => es.close()
    return () => es.close()
  },
  contribute: (id: string, data: { kind: 'photo' | 'audio'; year?: number; note: string; file: File }) => {
    const fd = new FormData()
    fd.append('kind', data.kind)
    if (data.year) fd.append('year', String(data.year))
    fd.append('note', data.note)
    fd.append('file', data.file)
    return fetch(`/api/places/${id}/contributions`, { method: 'POST', body: fd }).then(r => json<Source>(r))
  },
}

export type Country = {
  id: string
  name: string
  flag: string
  fr: string
  en: string
  old_names: string[]
  places: string[]
  stats?: ChronicleStats | null
  cover?: string | null
}

export type ChronicleStats = { chapters: number; events: number; corroborated: number; share: number; span: [string, string] | null }

export type ChronicleEvent = { year: number; label: string; text: string; source: number; corroborated: boolean }

export type Chapter = {
  title: string
  url: string
  source: number
  summary: string
  narrative: string
  events: ChronicleEvent[]
  start: number | null
  end: number | null
  photos: { title: string; year: number; license: string; image: string; page_url: string; source: string }[]
}

export type Chronicle = {
  country: Country
  chapters: Chapter[]
  sources: { n: number; title: string; url: string; lang: string; license: string; source: string }[]
  gaps: { from: number | null; to: number | null; text: string }[]
  stats: ChronicleStats
  engines: Record<string, string>
  run: string
}

export const countriesApi = {
  list: () => fetch('/api/countries').then(r => json<Country[]>(r)),
  get: (id: string) => fetch(`/api/countries/${id}`).then(r => json<{ country: Country; chronicle: Chronicle | null }>(r)),
  run: (id: string) => fetch(`/api/countries/${id}/chronicle`, { method: 'POST' }).then(r => json<{ run_id: string }>(r)),
}

export const STATUS_META: Record<TagStatus, { label: string; color: string; dot: string }> = {
  documente: { label: 'Documenté', color: '#34d399', dot: 'bg-proof' },
  inchange: { label: 'Inchangé', color: '#cbd5e1', dot: 'bg-same' },
  hypothese: { label: 'Hypothèse', color: '#fbbf24', dot: 'bg-guess' },
}
