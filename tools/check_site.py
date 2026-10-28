"""Publication gate for this repository. GitHub Actions runs it before every deploy; nothing is deployed if it fails.

    python tools/check_site.py                # check only (exit 1 = STOP)
    python tools/check_site.py --write-index  # rebuild site/index.json from ledger.json and the ZIPs, then check
    python tools/check_site.py --history      # also check that ledger.json was append-only in every past commit (needs git)

Rules (any failure = STOP, nothing is published):
  1. site/ holds exactly: index.json, the static files named in publish.json, and the ZIPs of ledger entries that are
     "listed". No other file, no hidden file, no link.
  2. Every ZIP: package id is in allowed_package_ids, its SHA-256 equals the ledger, its package.json name and version
     equal the file name, only plain .json / .meta / .md entries, no absolute or ".." paths, under 1 MiB.
  3. site/index.json equals what this tool builds from the ledger and the ZIPs (so the listing cannot point elsewhere):
     every version URL is inside base_url and every zipSHA256 equals the ledger.
  4. ledger.json is append-only: an id@version once recorded keeps its SHA-256 forever (it may only be unlisted).
  5. No forbidden text in any repository file or ZIP entry (credentials, private names, local paths, product names).
"""
import hashlib, io, json, os, re, subprocess, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'site')
problems = []


def load(rel):
    return json.loads(open(os.path.join(ROOT, rel), 'rb').read().decode('utf-8'))


# Written split so that this file does not match itself.
FORBIDDEN = [re.compile(p, re.I) for p in (
    'gh' + 'p_', 'gh' + 'o_', 'gh' + 's_', 'gh' + 'u_', 'github' + '_pat_', 'auth' + 'orization', 'bear' + 'er ',
    'private' + ' key', 'pass' + 'word', r'secrets\.', r'x-access-' + 'token', r'AKIA[0-9A-Z]{16}', r'xox[bp]-',
    'wrld' + '_', 'usr' + '_',
    'dm-vpm' + '-private', 'vpm' + '.private', 'kit' + 'ai', 'mim' + 'ura', '@gm' + 'ail', r'c:\\' + 'users', 'drop' + 'box',
    'public' + ' room')]
# Bytes of the DM Modified WebUnit Clients (v5.4 / v5.2). They must never be published (redistribution permission PENDING).
FORBIDDEN_SHA256 = {'d13b2ce1976d63c035937151cb0ecec71fc3ed9fab9ce820b81abf8828fd910a',
                    '8dd8b6ded358e88095409e0a0e45eb5538301da18c1ea9b698b5c9a1660785df'}
SCAN_SKIP = {'tools/check_site.py'}           # holds the patterns themselves (split, so it does not match anyway)


def scan(name, text):
    for p in FORBIDDEN:
        m = p.search(text)
        if m: problems.append('forbidden text %r in %s' % (m.group(0), name))


def zip_problems(rel, data, pkg, version, types=('.json', '.meta', '.md')):
    out = []
    try: z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile: return ['%s is not a ZIP' % rel]
    names = z.namelist()
    for info in z.infolist():
        n = info.filename
        if n.startswith('/') or '\\' in n or '..' in n.split('/') or ':' in n: out.append('%s: bad entry path %r' % (rel, n))
        if (info.external_attr >> 16) & 0o170000 == 0o120000: out.append('%s: link entry %r' % (rel, n))
        if not n.endswith('/') and os.path.splitext(n)[1] not in types: out.append('%s: entry type not allowed %r' % (rel, n))
        if n.startswith('WebUnit/Client.dm'): out.append('%s: modified WebUnit Client entry %r' % (rel, n))
        if not n.endswith('/') and hashlib.sha256(z.read(n)).hexdigest() in FORBIDDEN_SHA256: out.append('%s: entry %r has the bytes of a modified WebUnit Client' % (rel, n))
        if not n.endswith('/'):
            scan('%s!%s' % (rel, n), z.read(n).decode('utf-8', 'replace'))
    if 'package.json' not in names: return out + ['%s: no package.json' % rel]
    man = json.loads(z.read('package.json').decode('utf-8'))
    if man.get('name') != pkg or man.get('version') != version: out.append('%s: package.json says %s@%s' % (rel, man.get('name'), man.get('version')))
    return out


def build(cfg, ledger):
    packages = {}
    for key, entry in ledger.items():
        if not entry.get('listed'): continue
        pkg, version = key.split('@', 1)
        rel = 'packages/%s/%s-%s.zip' % (pkg, pkg, version)
        data = open(os.path.join(SITE, rel), 'rb').read()
        man = json.loads(zipfile.ZipFile(io.BytesIO(data)).read('package.json').decode('utf-8'))
        man['url'] = cfg['base_url'] + rel
        man['zipSHA256'] = entry['sha256']
        packages.setdefault(pkg, {'versions': {}})['versions'][version] = man
    doc = dict(cfg['listing'])
    doc['packages'] = packages
    return json.dumps(doc, indent=2, ensure_ascii=False) + '\n'


def history_check(ledger):
    try:
        commits = subprocess.run(['git', 'log', '--format=%H', '--', 'ledger.json'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError) as e:
        problems.append('ledger history could not be read: %s' % e); return 0
    for c in commits:
        try: old = json.loads(subprocess.run(['git', 'show', '%s:ledger.json' % c], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
        except (subprocess.CalledProcessError, ValueError): continue    # ledger.json deleted in that commit: the current file is checked anyway
        for key, entry in old.items():
            if key not in ledger: problems.append('ledger: %s was removed (recorded in %s); entries are never removed, only unlisted' % (key, c[:7]))
            elif ledger[key]['sha256'] != entry['sha256']: problems.append('ledger: %s changed its SHA-256 since %s; a published id@version is never replaced' % (key, c[:7]))
    return len(commits)


cfg, ledger = load('publish.json'), load('ledger.json')
allowed_ids = set(cfg['allowed_package_ids'])
if not cfg['base_url'].startswith('https://') or not cfg['listing']['url'].startswith(cfg['base_url']): problems.append('publish.json: base_url / listing url not https or not consistent')

# 2 + 4 (current file): ledger entries and their ZIPs
expected = {'index.json'} | set(cfg['static_files'])
for key, entry in ledger.items():
    pkg, _, version = key.partition('@')
    if pkg not in allowed_ids: problems.append('ledger: package id %s is not in allowed_package_ids' % pkg); continue
    if not re.fullmatch(r'[0-9a-f]{64}', entry.get('sha256', '')): problems.append('ledger: %s has no valid sha256' % key); continue
    rel = 'packages/%s/%s-%s.zip' % (pkg, pkg, version)
    path = os.path.join(SITE, rel)
    if not entry.get('listed'):
        if os.path.exists(path): problems.append('%s is unlisted but its ZIP is still in site/' % key)
        continue
    expected.add(rel)
    if not os.path.isfile(path): problems.append('missing ZIP for %s: %s' % (key, rel)); continue
    data = open(path, 'rb').read()
    if len(data) > 1 << 20: problems.append('%s is larger than 1 MiB' % rel)
    if hashlib.sha256(data).hexdigest() != entry['sha256']: problems.append('%s: SHA-256 differs from the ledger' % rel)
    problems.extend(zip_problems(rel, data, pkg, version, tuple(cfg.get('entry_types', {}).get(pkg, ('.json', '.meta', '.md')))))

# 1: exact file set of site/
present = set()
for dirpath, dirnames, filenames in os.walk(SITE):
    for d in dirnames:
        if os.path.islink(os.path.join(dirpath, d)): problems.append('link in site/: %s' % d)
    for f in filenames:
        full = os.path.join(dirpath, f)
        rel = os.path.relpath(full, SITE).replace(os.sep, '/')
        if os.path.islink(full): problems.append('link in site/: %s' % rel)
        present.add(rel)
for rel in sorted(present - expected): problems.append('unexpected file in site/: %s' % rel)
for rel in sorted(expected - present - {'index.json'}):
    if not rel.startswith('packages/'): problems.append('missing static file: %s' % rel)

# 3: index.json is exactly the built listing
if problems:
    problems.append('site/index.json not checked (fix the problems above first)')
else:
    built = build(cfg, ledger)
    index_path = os.path.join(SITE, 'index.json')
    if '--write-index' in sys.argv:
        open(index_path, 'w', encoding='utf-8', newline='\n').write(built)
    if not os.path.isfile(index_path) or open(index_path, encoding='utf-8').read() != built:
        problems.append('site/index.json is not the listing built from ledger.json and the ZIPs (run --write-index)')

# 4 (history)
history = history_check(ledger) if '--history' in sys.argv else None

# 5: forbidden text in every tracked-looking text file of the repository
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d != '.git']
    for f in filenames:
        rel = os.path.relpath(os.path.join(dirpath, f), ROOT).replace(os.sep, '/')
        if rel in SCAN_SKIP or rel.endswith('.zip'): continue
        scan(rel, open(os.path.join(dirpath, f), 'rb').read().decode('utf-8', 'replace'))

print('listing %s -> %s' % (cfg['listing']['id'], cfg['listing']['url']))
print('ledger entries: %d (listed: %d); site files: %d' % (len(ledger), sum(1 for e in ledger.values() if e.get('listed')), len(present | {'index.json'})))
for rel in sorted(expected):
    p = os.path.join(SITE, rel)
    if os.path.isfile(p): print('  %-62s %7d  %s' % (rel, os.path.getsize(p), hashlib.sha256(open(p, 'rb').read()).hexdigest()))
if history is not None: print('ledger history: %d commits checked' % history)
if problems:
    print('STOP:'); [print('  ' + p) for p in problems]; sys.exit(1)
print('CHECK: PASS')
