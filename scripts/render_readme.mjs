// Recreate the editable SVG illustrations and GitHub-friendly PNG exports.
// Run from the repository root: node scripts/render_readme.mjs
import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const require = createRequire(path.join(root, 'apps/web/package.json'));
const sharp = require('sharp');
const output = path.join(root, 'assets/readme');
const logo = await sharp(path.join(root, 'apps/web/public/assets/icon.svg'))
  .resize(144, 144).png().toBuffer();
const logoUri = `data:image/png;base64,${logo.toString('base64')}`;
const ink = '#24272e';
const muted = '#626874';
const esc = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const text = (x, y, value, size = 20, color = ink, weight = 400, extra = '') =>
  `<text x="${x}" y="${y}" font-size="${size}" fill="${color}" font-weight="${weight}" ${extra}>${esc(value)}</text>`;
const lines = (x, y, values, size = 20, color = muted, gap = 29, weight = 400) =>
  values.map((value, i) => text(x, y + i * gap, value, size, color, weight)).join('\n');
const rect = (x, y, w, h, fill = '#fff', radius = 18, stroke = '#e2e5ec') =>
  `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${radius}" fill="${fill}" stroke="${stroke}"/>`;
const mark = (x, y, size = 48) => `<image x="${x}" y="${y}" width="${size}" height="${size}" href="${logoUri}"/>`;
const pathLine = (d, arrow = false, color = '#9ca6b8', both = false) =>
  `<path d="${d}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ${arrow ? 'marker-end="url(#arrow)"' : ''} ${both ? 'marker-start="url(#arrow)"' : ''}/>`;
const circle = (x, y, r, fill) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}"/>`;
function svg(height, title, description, body) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="${height}" viewBox="0 0 1200 ${height}" role="img" aria-labelledby="title desc">
<title id="title">${esc(title)}</title><desc id="desc">${esc(description)}</desc>
<defs>
  <linearGradient id="rim" x2="1" y2="1"><stop stop-color="#b9edf0"/><stop offset=".5" stop-color="#dad7f3"/><stop offset="1" stop-color="#ffe4cc"/></linearGradient>
  <linearGradient id="blue" x2="1" y2="1"><stop stop-color="#def4fb"/><stop offset="1" stop-color="#eae4fa"/></linearGradient>
  <linearGradient id="green" x2="1" y2="1"><stop stop-color="#daf5eb"/><stop offset="1" stop-color="#fff1d9"/></linearGradient>
  <linearGradient id="pink" x2="1" y2="1"><stop stop-color="#f6def2"/><stop offset="1" stop-color="#ffe6d7"/></linearGradient>
  <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1L8 5L1 9" fill="none" stroke="#9ca6b8" stroke-width="1.5"/></marker>
</defs>
${rect(0, 0, 1200, height, 'url(#rim)', 24, 'none')}
${rect(8, 8, 1184, height - 16, '#fbfcfe', 18, 'none')}
<g font-family="Segoe UI,Arial,sans-serif">${body}</g></svg>\n`;
}

const hero = svg(260, 'Grok Invoices — your accounting team, through Grok Bots',
  'A personal Grok Bot is the client interface. Specialist bots work through one shared accounting platform.', `
${mark(40, 34, 66)}
${text(128, 58, 'GROK BOT HACKATHON / WROCŁAW 2026', 13, muted, 500, 'letter-spacing="1.4"')}
${text(128, 104, 'Grok Invoices', 42, ink, 600, 'letter-spacing="-1.3"')}
${text(44, 158, 'Your accounting team, through Grok Bots.', 25, ink, 400)}
${pathLine('M44 192H1156', false, '#e2e5ec')}
${text(44, 226, 'Share context', 17, muted)}${text(285, 226, 'Answer in chat', 17, muted)}${text(542, 226, 'Check progress', 17, muted)}
${text(1156, 226, 'Agent as a Service', 16, muted, 400, 'text-anchor="end"')}`);

const customer = svg(840, 'Your part is a conversation',
  'Illustrative client journey: connect a company and KSeF privately, answer a question about a 246 PLN fuel invoice for GD 9R247, then request progress. The answer is saved for accounting review; it is not itself a posting.', `
${text(44, 60, '01 / THE CLIENT EXPERIENCE', 14, muted, 600, 'letter-spacing="1.6"')}
${text(44, 117, 'Your part is a conversation.', 43, ink, 600, 'letter-spacing="-1.3"')}
${text(44, 157, 'Company context in. Clear questions back. Progress when you ask.', 21, muted)}

${circle(66, 235, 22, 'url(#blue)')}${text(66, 242, '1', 20, ink, 600, 'text-anchor="middle"')}
${text(44, 292, 'Connect your company', 23, ink, 600)}
${lines(44, 327, ['Share your NIP and company name.', 'Keep the KSeF token in the', 'private vault, outside the chat.'], 19)}
${circle(66, 447, 22, 'url(#pink)')}${text(66, 454, '2', 20, ink, 600, 'text-anchor="middle"')}
${text(44, 504, 'Answer in your own words', 23, ink, 600)}
${lines(44, 539, ['Tell the assistant what happened.', 'Your answer stays attached', 'to the right invoice and case.'], 19)}
${circle(66, 659, 22, 'url(#green)')}${text(66, 666, '3', 20, ink, 600, 'text-anchor="middle"')}
${text(44, 716, 'Ask for an update', 23, ink, 600)}
${lines(44, 751, ['Get current counts in chat.', 'Inspect decisions in the dashboard.'], 19)}

${rect(430, 202, 726, 559, '#fff', 20)}
${mark(454, 222, 42)}${text(511, 246, 'Your client assistant', 23, ink, 600)}
${text(511, 274, 'Grok Bot · illustrative conversation', 16, muted)}
${pathLine('M454 293H1132', false, '#edf0f4')}
${rect(706, 314, 426, 48, 'url(#blue)', 14, 'none')}
${text(728, 345, 'Any questions about my invoices?', 20)}
${rect(454, 382, 678, 130, '#f4f5f8', 14, 'none')}
${text(476, 414, 'ORLEN · 246.00 PLN · GD 9R247', 18, muted, 600)}
${lines(476, 451, ['Which car was this for, how is it used,', 'and what was the purchase for?'], 21, ink, 31)}
${rect(522, 532, 610, 86, 'url(#blue)', 14, 'none')}
${lines(544, 566, ['Our Skoda Octavia, mixed business/private use.', 'Diesel for a client delivery.'], 20, ink, 29)}
${rect(454, 638, 678, 94, 'url(#green)', 14, 'none')}
${text(476, 674, 'Answer saved. The case is back in review.', 21, ink, 500)}
${text(476, 707, 'Accounting review comes next.', 18, muted)}
${text(1156, 806, 'Concept illustration · synthetic example · English translation of the Polish demo', 15, muted, 400, 'text-anchor="end"')}`);

function bot(x, fill, label, title, body) {
  return `${rect(x, 278, 344, 210, '#fff', 18)}
${rect(x + 1, 279, 342, 55, fill, 17, 'none')}
${text(x + 22, 314, label, 16, ink, 500)}
${text(x + 22, 372, title, 25, ink, 600)}
${lines(x + 22, 411, body, 19, muted, 28)}`;
}
const team = svg(800, 'One conversation, three Grok Bots',
  'You talk to the client assistant. The Invoice Agent ingests and checks invoices; the Regulations Agent investigates cases and sources. Each Grok Bot reads and writes through its own MCP connection to one shared platform. The platform stores accounting state and does not invoke models. Passes are explicitly requested.', `
${text(44, 60, '02 / THE TEAM BEHIND THE CONVERSATION', 14, muted, 600, 'letter-spacing="1.6"')}
${text(44, 117, 'One conversation. Three Grok Bots.', 43, ink, 600, 'letter-spacing="-1.3"')}
${text(44, 157, 'Your assistant handles the conversation. Specialists handle the accounting work.', 21, muted)}
${rect(455, 188, 290, 54, '#f0f2f7', 27, 'none')}
${text(600, 222, 'You / the company owner', 20, ink, 500, 'text-anchor="middle"')}
${pathLine('M600 246V272', true, '#9ca6b8', true)}
${text(44, 253, 'KSeF TEST →', 18, muted, 500)}
${text(812, 253, 'Official sources + company context', 18, muted, 500)}
${bot(44, 'url(#blue)', 'GROK BOT / INVOICES', 'Invoice Agent', ['Fetches and checks invoices.', 'Reuses applicable precedents', 'or opens a case for review.'])}
${bot(428, 'url(#pink)', 'GROK BOT / YOUR ASSISTANT', 'Client Assistant', ['Collects company facts.', 'Relays questions and answers.', 'Reports current progress.'])}
${bot(812, 'url(#green)', 'GROK BOT / REGULATIONS', 'Regulations Agent', ['Investigates cases and sources.', 'Requests missing facts.', 'Records the decision and basis.'])}
${[216, 600, 984].map(x => `${pathLine(`M${x} 493V553`, true, '#9ca6b8', true)}${rect(x + 11, 504, 62, 28, '#fbfcfe', 8, 'none')}${text(x + 42, 524, 'MCP', 15, muted, 500, 'text-anchor="middle"')}`).join('')}
${rect(44, 558, 1112, 158, '#f4f5f9', 18, '#dde2eb')}
${mark(66, 580, 46)}${text(130, 611, 'Grok Invoices / the shared platform', 27, ink, 600)}
${text(66, 658, 'Invoices · company facts · cases & answers · decisions · precedents · history', 21)}
${text(66, 691, 'One shared record. The dashboard reads it; Grok Bots work through it.', 19, muted)}
${text(44, 746, 'Demo: each bot pass is requested explicitly; platform writes do not wake another bot.', 19, muted)}
${text(44, 777, 'Architecture illustration · the platform stores state and enforces rules; it never calls a model.', 16, muted)}`);

for (const [name, content] of Object.entries({ hero, 'client-experience': customer, 'grok-bot-team': team })) {
  await writeFile(path.join(output, `${name}.svg`), content);
  await sharp(Buffer.from(content), { density: 144 }).png().toFile(path.join(output, `${name}.png`));
  console.log(`Rendered assets/readme/${name}.{svg,png}`);
}

const embedded = await Promise.all(['hero', 'client-experience', 'grok-bot-team'].map(async name => {
  const png = await readFile(path.join(output, `${name}.png`));
  return `<img src="data:image/png;base64,${png.toString('base64')}" alt="${name.replaceAll('-', ' ')}">`;
}));
await writeFile(path.join(output, 'visuals.html'), `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Grok Invoices / README illustrations</title><style>html,body{margin:0;background:transparent}main{display:grid;gap:20px}img{display:block;width:100%;height:auto}</style><main>${embedded.join('')}</main></html>`);
