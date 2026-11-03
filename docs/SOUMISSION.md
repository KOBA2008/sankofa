# Kit de soumission : Meta Global AI Developer Hackathon

Date limite : 4 novembre 2026, 21 h (heure de New York), soit le 5 novembre à 3 h au Bénin.
Portail : https://cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit

## Nom du projet

SANKOFA

## Accroche (une ligne)

An AI agent that builds a time machine for any city, and tells you what is proven and what is imagined.

## Track et thème

Indie Developer · Build for Your World

## Description (anglais, pour le formulaire)

**The problem.** The visual history of cities, especially African ones, is scattered across distant archives. People in Porto-Novo or Gorée rarely see what their street looked like a century ago. Generative AI can "age" a photo in one click, but it invents silently: a beautiful fake image damages memory instead of serving it.

**What SANKOFA does.** Give it a place. An agent does the work of a historian and an ML engineer, live, in seven visible steps:

1. **Investigates** open archives (Wikimedia Commons, Library of Congress, BnF, Albert Kahn's Archives of the Planet), keeps only open licenses, and asks Muse Spark to check on the image itself that each document really shows the place.
2. **Annotates** the current view into facades, roofs, street and sky with SAM 3.1.
3. **Re-photographs**: finds where each period photographer stood by matching features between the archive and today's view, then warps the archive onto it.
4. **Learns the city's photographic style** for the target decade (tone curve, tint, grain).
5. **Reconstructs** the past: areas proven by an archive come from the archive itself; only areas with no evidence are handed to Muse Image, with a prompt written from the sources.
6. **Evaluates itself**: hides an archive, rebuilds without it, compares, and computes a reliability score from evidence coverage, corpus richness and that blind test.
7. **Narrates** the place in French and English, every factual sentence citing its source.

Every region of the image gets a verdict: **documented**, **unchanged** or **hypothesis**. The agent lists what it does not know and asks the community for the missing photos or oral testimonies (voice transcription for local languages). A **re-photography guide** overlays the archive on the phone camera so anyone can find the exact angle of the 1900 photographer.

**Country chronicles.** The same agent rebuilds the history of a whole country from its sources only: it reads the history articles in French and English, extracts every dated event word for word with a link to its section, marks each event as corroborated when the independently written source gives the same year and the same name, flags the centuries the sources leave in the dark, illustrates each era with archive photos found under the country's former names (Dahomey, Gold Coast, Constantinople), and writes a cited narrative with Muse Spark. Fifteen countries are ready.

**Documentaries.** Every country and place can be watched as a short documentary: archive photos with slow camera moves, events quoted on screen with their corroboration badge, the present-day view dissolving into the past, and a random public-domain soundtrack (Satie, Chopin, Debussy, Bach, Mozart). It plays in the browser and exports to MP4, with full credits for every photo, source and recording.

**Why it matters.** Heritage, education, tourism and restitution debates all need images people can trust. SANKOFA starts in Porto-Novo and Cotonou (Benin) and already covers 16 places in 15 countries: Gorée, Cape Town, the Giza pyramids, the Great Mosque of Djenné, Cape Coast Castle, Jemaa el-Fna, Salvador de Bahia's Pelourinho, Notre-Dame de Paris, Puerta del Sol, Tower Bridge, the Colosseum, Hagia Sophia, the Flatiron Building and the Taj Mahal.

**Meta tooling.** Muse Spark (agent reasoning, archive verification with vision, cited narration), SAM 3.1 (concept segmentation), Muse Image (masked reconstruction limited to unproven areas), Muse voice transcription (community testimonies).

**Archives.** Wikimedia Commons (keyword and GPS search), Europeana. Open licenses only, each image keeps its author, license and source link.

**Built with.** Python, FastAPI, OpenCV, React, Vite, Tailwind, Framer Motion, Leaflet.

## Ce qui a été construit pendant le hackathon

Tout le dépôt : agent, collecte d'archives, vision, auto-évaluation, API, interface, guide de re-photographie, corpus des six lieux.

## Script de la vidéo de démo (2 min 30)

| Temps | Image | Voix off |
|-------|-------|----------|
| 0:00 | Autochrome de Porto-Novo, 1930, plein écran | « L'histoire de nos rues dort dans des archives, loin de chez nous. » |
| 0:10 | Page d'accueil, carte des six villes | « SANKOFA est un agent qui construit la machine à remonter le temps de n'importe quelle ville. » |
| 0:20 | Page Paris, curseur sur 1912, clic « Remonter le temps » | « Je choisis un lieu et une année. L'agent se met au travail. » |
| 0:30 | Journal de l'agent qui défile, étape par étape | « Il fouille les archives, découpe la vue actuelle avec SAM 3.1, retrouve d'où le photographe de 1912 avait pris sa photo. » |
| 0:55 | Révélation : curseur avant/après, la foule de 1912 apparaît | « Et voici le parvis en 1912. Pas une image inventée : une vraie archive, superposée au centimètre près. » |
| 1:10 | Survol des étiquettes vert, gris, jaune | « Chaque zone porte un verdict : documenté, inchangé, ou hypothèse. » |
| 1:25 | Onglet Fiabilité, jauge qui se remplit | « L'agent se teste lui-même : il cache une archive, reconstruit sans elle, et mesure son erreur. » |
| 1:40 | Porto-Novo, guide de re-photographie sur téléphone | « À Porto-Novo, je filme la rue avec l'archive en transparence pour retrouver l'angle exact. » |
| 2:00 | Onglet Lacunes, puis contribution d'un témoignage | « Quand il ne sait pas, il le dit, et demande à la communauté. » |
| 2:15 | Récit lu à voix haute, sources cliquables | « Porto-Novo aujourd'hui. Dakar, Lagos, Hanoï demain. » |

## Liste de contrôle avant envoi

- [ ] Clé Meta dans `.env`, badge « Meta Model API » vert, une exécution complète réussie
- [ ] Photos de Porto-Novo et Cotonou prises avec le guide de re-photographie
- [ ] Dépôt GitHub public avec le README
- [ ] Vidéo de 2 à 3 minutes en ligne (YouTube non répertorié ou Loom)
- [ ] Formulaire rempli, track Indie, membres de l'équipe indiqués
