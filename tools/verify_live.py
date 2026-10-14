"""After a deploy: fetch the published site WITHOUT any credentials and compare it with this clone.

    python tools/verify_live.py            # exit 1 = mismatch (then follow "Stop publication" in README.md)

Checks: every expected file is served with HTTP 200, the expected media type and the same bytes (SHA-256) as site/;
index.json equals site/index.json and its zipSHA256 values equal the ledger; repository files that are not part of the
site (ledger.json, publish.json, tools/, README.md, .github/) and folder paths return 404 (no directory listing).
"""
import hashlib, json, os, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'site')
cfg = json.load(open(os.path.join(ROOT, 'publish.json'), encoding='utf-8'))
ledger = json.load(open(os.path.join(ROOT, 'ledger.json'), encoding='utf-8'))
base = cfg['base_url']
problems = []
TYPES = {'.json': 'application/json', '.zip': 'application/zip', '.html': 'text/html', '.txt': 'text/plain'}


def get(path):
    req = urllib.request.Request(base + path, headers={'User-Agent': 'dm-vpm-verify/1', 'Cache-Control': 'no-cache'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return r.status, r.headers.get('Content-Type', ''), r.read()
    except urllib.error.HTTPError as e: return e.code, e.headers.get('Content-Type', ''), b''


expected = ['index.json'] + cfg['static_files'] + ['packages/%s/%s-%s.zip' % (k.split('@')[0], k.split('@')[0], k.split('@')[1]) for k, e in ledger.items() if e.get('listed')]
for rel in expected:
    status, ctype, body = get(rel)
    local = open(os.path.join(SITE, rel), 'rb').read()
    want = TYPES[os.path.splitext(rel)[1]]
    ok = status == 200 and ctype.split(';')[0].strip() == want and body == local
    print('%-3s %-62s %s  %-28s %s' % (status, rel, 'same' if body == local else 'DIFFERENT', ctype, hashlib.sha256(body).hexdigest()))
    if not ok: problems.append('%s: status %s, type %s, bytes %s' % (rel, status, ctype, 'same' if body == local else 'different'))

served = json.loads(get('index.json')[2] or b'{}')
for pkg, body in (served.get('packages') or {}).items():
    for version, item in body['versions'].items():
        entry = ledger.get('%s@%s' % (pkg, version))
        if not entry or not entry.get('listed') or entry['sha256'] != item.get('zipSHA256') or not item.get('url', '').startswith(base):
            problems.append('served index.json: %s@%s does not match the ledger' % (pkg, version))

for rel in ('ledger.json', 'publish.json', 'README.md', 'tools/check_site.py', '.github/workflows/pages.yml', 'site/index.json',
            'packages/', 'packages/%s/' % cfg['allowed_package_ids'][0], '.git/config', 'does-not-exist.json'):
    status = get(rel)[0]
    print('%-3s %s (expected 404)' % (status, rel))
    if status != 404: problems.append('%s answered %s, expected 404' % (rel, status))

if problems:
    print('MISMATCH:'); [print('  ' + p) for p in problems]; sys.exit(1)
print('LIVE: PASS (%d files, served bytes equal to the repository)' % len(expected))
