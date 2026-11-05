# Web Application Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

The owner selected Next.js App Router and Tailwind CSS, running in a separate web container from FastAPI. Keep reusable UI in `src/` and Next.js routes in `app/`. This supersedes the initial Vite/Sites scaffold. Preserve the selected F visual direction during migration.

The outer page background behind the dashboard window uses a soft pastel gradient inspired by the summary cards: cyan, blue, lilac, pink, and peach (owner feedback, 2026-11-05).

Use the shared FastAPI platform as the source of truth. `API_BASE_URL` is server-only runtime configuration. Never put platform credentials in browser code. The dashboard proxy exposes public reads only.

Run `npm test` and `npm run build` before committing a completed feature. Check desktop and mobile behavior in the browser. A container build must be reported separately from a Next.js build.

<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
