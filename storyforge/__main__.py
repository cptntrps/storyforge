"""storyforge CLI. Every command exits non-zero on a schema error and prints the path of the invalid field."""

import argparse
import json
import sys
from pathlib import Path


def _load(p):
    return json.loads(Path(p).read_text())


def _dump(obj, p):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


def _valid(kind, obj):
    from . import schema
    errs = schema.validate(kind, obj)
    if errs:
        print(f'invalid {kind}:', file=sys.stderr)
        for e in errs:
            print('  ' + e, file=sys.stderr)
        sys.exit(1)
    return obj


def cmd_ingest(a):
    src = Path(a.file)
    ext = src.suffix.lower()
    if ext == '.pptx':
        from .ingest.pptx import ingest_pptx as f
        deck = f(src)
    elif ext in ('.html', '.htm'):
        from .ingest.html import ingest_html as f
        deck = f(src)
    elif ext == '.json':
        from .ingest.gslides import ingest_gslides as f
        deck = f(_load(src), source=str(src))
    else:
        sys.exit(f'cannot ingest {ext}; use .pptx, .html or Google Slides .json')
    _valid('deck', deck)
    _dump(deck, a.out)
    print(f"{a.out}: {len(deck['slides'])} slides, {sum(1 for s in deck['slides'] if s.get('unreadable'))} unreadable")


def cmd_ratecard(a):
    from .ratecard import build_ratecard, render_md
    deck = _valid('deck', _load(a.deck))
    frame = _valid('frame', _load(a.frame)) if a.frame else None
    judg = _valid('judgments', _load(a.judgments)) if a.judgments else None
    rc = build_ratecard(deck, frame, judg)
    _dump(rc, a.out)
    md = Path(a.out).with_suffix('.md')
    md.write_text(render_md(rc))
    fails = [c['id'] for c in rc['checks'] if c['result'] in ('FAIL', 'DISAGREE')]
    print(f"{md}: {len(fails)} FAIL/DISAGREE {fails}; {len(rc['questions'])} question(s)")


def cmd_judgments(a):
    from .ratecard import join_passes
    out = join_passes(_load(a.pass_a), _load(a.pass_b))
    _dump(out, a.out)
    dis = [k for k, v in out.items() if k.startswith('R') and v['pass_a'] != v['pass_b']]
    print(f"{a.out}: {len([k for k in out if k.startswith('R')])} judged checks, disagree on {dis}")


def _rows(a):
    if not getattr(a, 'rows', None):
        return None
    from .checks.numbers import load_rows
    return load_rows(a.rows)


def cmd_validate(a):
    from .gates import story_checks
    story = _valid('story', _load(a.story))
    checks = story_checks(story, _rows(a))
    bad = 0
    for cid in sorted(checks):
        c = checks[cid]
        print(f'{cid} {c.result}' + (f'  {json.dumps(c.evidence[:3], ensure_ascii=False)[:300]}' if c.result != 'PASS' else ''))
        bad += c.result in ('FAIL', 'DISAGREE')
    sys.exit(1 if bad else 0)


def cmd_storylines(a):
    from .storylines import score_storylines
    cands = [_valid('story', _load(p)) for p in a.candidates]
    frame = _valid('frame', _load(a.frame)) if a.frame else None
    judg = _load(a.judgments) if a.judgments else None
    out = score_storylines(cands, frame, _rows(a), judg)
    _dump(out, a.out)
    print(f"chosen: {out['chosen']}; tie: {out['tie']}; why: {out['why']}")


def cmd_charts(a):
    from .charts import render_charts
    story = _valid('story', _load(a.story))
    res = render_charts(story, a.out, png=not a.no_png)
    _dump({k: {kk: str(vv) for kk, vv in v.items()} for k, v in res.items()}, Path(a.out) / 'index.json')
    print(f"{len([v for v in res.values() if 'svg' in v])} chart(s) rendered; {len([v for v in res.values() if 'table' in v])} as table")


def _charts_index(path):
    if not path:
        return {}
    idx = Path(path) / 'index.json'
    if not idx.exists():
        return {}
    return {k: {kk: Path(vv) for kk, vv in v.items() if kk in ('svg', 'png')} for k, v in _load(idx).items()}


def cmd_build(a):
    from .render.deckcraft import render_pptx
    story = _valid('story', _load(a.story))
    charts = _charts_index(a.charts)
    pptx = render_pptx(story, charts, a.out, style=a.style)
    print(f'{pptx}')
    if a.html:
        from .render.html import render_html
        print(render_html(story, charts, Path(a.out) / 'deck.html'))


def cmd_handoff(a):
    from .handoff import build_handoff
    story = _valid('story', _load(a.story))
    rc = _valid('ratecard', _load(a.ratecard)) if a.ratecard else None
    out = build_handoff(story, _charts_index(a.charts), rc, a.out)
    print(out)


def cmd_gates(a):
    from .gates import all_pass, run_gates
    from .ratecard import render_md
    story = _valid('story', _load(a.story))
    judg = _valid('judgments', _load(a.judgments)) if a.judgments else None
    rc = run_gates(Path(a.pptx), story, _rows(a), judg, out_dir=a.out)
    out = Path(a.out or Path(a.pptx).parent) / 'ratecard_after.json'
    _dump(rc, out)
    out.with_suffix('.md').write_text(render_md(rc))
    ok = all_pass(rc)
    print(f"{out.with_suffix('.md')}: {'ALL PASS, MBB-ready' if ok else 'NOT all PASS: ' + str([c['id'] + ':' + c['result'] for c in rc['checks'] if c['result'] != 'PASS'])}")
    sys.exit(0 if ok else 1)


def main(argv=None):
    p = argparse.ArgumentParser(prog='storyforge')
    sp = p.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('ingest'); s.add_argument('file'); s.add_argument('-o', '--out', required=True); s.set_defaults(f=cmd_ingest)
    s = sp.add_parser('ratecard'); s.add_argument('deck'); s.add_argument('--frame'); s.add_argument('--judgments'); s.add_argument('-o', '--out', required=True); s.set_defaults(f=cmd_ratecard)
    s = sp.add_parser('judgments'); s.add_argument('pass_a'); s.add_argument('pass_b'); s.add_argument('-o', '--out', required=True); s.set_defaults(f=cmd_judgments)
    s = sp.add_parser('validate'); s.add_argument('story'); s.add_argument('--rows'); s.set_defaults(f=cmd_validate)
    s = sp.add_parser('storylines'); s.add_argument('candidates', nargs='+'); s.add_argument('--frame'); s.add_argument('--rows'); s.add_argument('--judgments'); s.add_argument('-o', '--out', required=True); s.set_defaults(f=cmd_storylines)
    s = sp.add_parser('charts'); s.add_argument('story'); s.add_argument('-o', '--out', required=True); s.add_argument('--no-png', action='store_true'); s.set_defaults(f=cmd_charts)
    s = sp.add_parser('build'); s.add_argument('story'); s.add_argument('--charts'); s.add_argument('-o', '--out', required=True); s.add_argument('--html', action='store_true'); s.add_argument('--style', default='default'); s.set_defaults(f=cmd_build)
    s = sp.add_parser('handoff'); s.add_argument('story'); s.add_argument('--charts'); s.add_argument('--ratecard'); s.add_argument('-o', '--out', required=True); s.set_defaults(f=cmd_handoff)
    s = sp.add_parser('gates'); s.add_argument('pptx'); s.add_argument('--story', required=True); s.add_argument('--rows'); s.add_argument('--judgments'); s.add_argument('-o', '--out'); s.set_defaults(f=cmd_gates)
    a = p.parse_args(argv)
    a.f(a)


if __name__ == '__main__':
    main()
