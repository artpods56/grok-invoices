<img src="assets/icon.svg" width="64" height="64" alt="">

# Grok Invoices

An Agents as a Service accounting platform for founders in Poland, built for the Grok Bot Hackathon Wroclaw 2026.

The hackathon workflow connects invoice intake, company context, regulatory research, client questions, and traceable decisions. End-to-end accounting is the product ambition; the current checkout contains planning and research, not a working accounting service.

## Project notes

- [Dashboard visual direction](docs/design/dashboard-direction.md)
- [Current context and demo scope](docs/project-context.md)
- [Polish accounting workflow and official sources](docs/research/polish-accounting-and-sources.md)
- [Keeping an AI agent's regulatory knowledge current](docs/research/ai-regulatory-knowledge.md)
- [Live source access checks and limitations](docs/research/source-checks.md)

Repository content and commit messages are written in English. Commit messages should stay short and descriptive.

## Dashboard development

The dashboard implementation is in `dashboard/`. It uses synthetic fixtures; live KSeF, Grok Bot, phone calls, and autonomous accounting are not connected by this frontend.

Requires Node.js 22 or later and npm. From the repository root:

```powershell
cd dashboard
npm ci
npm run dev -- --host 127.0.0.1 --port 4173 --strictPort
```

Open http://localhost:4173. Stop the server with Ctrl+C. Run `npm test` for domain and static-host tests, and `npm run build` for the production bundle. The local demo state resets on page reload.

Created in [T3 Code](https://t3.codes).
