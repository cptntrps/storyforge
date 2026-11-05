#!/usr/bin/env python3
"""Harvest the rubric assets from local source files into storyforge/assets, sanitised.

Source paths come from tools/harvest.local.json (gitignored):
  {"mbb_titles": ".../field_examples.json", "element_definitions": ".../element_definitions.agent.json",
   "editorial_standard": ".../editorial-standard.json", "replace": {"Client Word": "Product A", ...}}
Run: python3 tools/harvest.py
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / 'storyforge' / 'assets'
TITLE_FIELDS = ('firm', 'title', 'kind', 'parts', 'pattern', 'why_it_works', 'watch_out', 'reuse_template', 'url', 'published')


def scrub(obj, replace):
    if isinstance(obj, str):
        for a, b in replace.items():
            obj = re.sub(re.escape(a), b, obj, flags=re.I)
        return obj.replace('—', '-').replace('–', '-')
    if isinstance(obj, list):
        return [scrub(x, replace) for x in obj]
    if isinstance(obj, dict):
        return {k: scrub(v, replace) for k, v in obj.items()}
    return obj


def main():
    cfg = json.loads((HERE / 'harvest.local.json').read_text())
    rep = cfg.get('replace', {})
    titles = json.loads(Path(cfg['mbb_titles']).read_text())
    titles = [{k: t[k] for k in TITLE_FIELDS if k in t} for t in titles if t.get('verify', {}).get('status') == 'verified']
    defs = json.loads(Path(cfg['element_definitions']).read_text())
    ed = json.loads(Path(cfg['editorial_standard']).read_text())
    ed.pop('authority', None)
    ed['scope'] = 'All client-facing titles, executive summaries, findings, scenario explanations and recommendations'
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / 'mbb_titles.json').write_text(json.dumps(scrub(titles, rep), indent=1, ensure_ascii=False) + '\n')
    (ASSETS / 'element_definitions.json').write_text(json.dumps(scrub(defs, rep), indent=1, ensure_ascii=False) + '\n')
    (ASSETS / 'editorial_standard.json').write_text(json.dumps(scrub(ed, rep), indent=1, ensure_ascii=False) + '\n')
    print(f'wrote {len(titles)} titles, {len(defs)} element definitions, editorial v{ed.get("version")}')


if __name__ == '__main__':
    sys.exit(main())
