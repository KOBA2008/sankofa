# SANKOFA (static showcase site)

Ready-to-serve build of the SANKOFA interface with precomputed content: places, showcase
reconstructions, place histories, country chronicles, documentaries and music.
The live agent is off in this version; the full app is on the `main` branch.

Deploy on Vercel: import this repository, set the production branch to `site`,
framework preset **Other**, no build command, output directory `.` (repository root).
`vercel.json` maps `/api/*` to the static JSON files in `static-api/`.
