# Web Application Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

The owner selected Next.js App Router and Tailwind CSS, running in a separate web container from FastAPI. Keep reusable UI in `src/` and Next.js routes in `app/`. This supersedes the initial Vite/Sites scaffold. Preserve the selected F visual direction during migration.

Use the shared FastAPI platform as the source of truth. `API_BASE_URL` is server-only runtime configuration. Never put platform credentials in browser code. The dashboard proxy exposes public reads only.

Run `npm test` and `npm run build` before committing a completed feature. Check desktop and mobile behavior in the browser. A container build must be reported separately from a Next.js build.
