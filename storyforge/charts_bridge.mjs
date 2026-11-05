// node charts_bridge.mjs <path to charts.js> <builder> '<json options>'  -> SVG on stdout
import { pathToFileURL } from 'node:url';

const [, , chartsPath, builder, optionsJson] = process.argv;
if (!chartsPath || !builder || !optionsJson) {
  console.error('usage: node charts_bridge.mjs <charts.js> <builder> <json>');
  process.exit(2);
}
const mod = await import(pathToFileURL(chartsPath).href);
const fn = mod[builder];
if (typeof fn !== 'function') {
  console.error(`builder ${builder} not exported by ${chartsPath}`);
  process.exit(3);
}
const opts = JSON.parse(optionsJson);
// Formatters cannot cross JSON; derive them from the unit.
const unit = String(opts.unit || '');
const grouped = v => Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 });
if (unit.startsWith('$')) opts.fmtY = v => '$' + grouped(v);
// stackedBars receives shares in 0..1 and formats them itself; other builders get plain percent values.
else if (unit === '%' && builder !== 'stackedBars') opts.fmtY = v => grouped(v) + '%';
process.stdout.write(fn(opts));
