"""Run on your PC BEFORE installing or updating a package from this listing (VCC and ALCOM closed is best).

Stops when a package id and version of this listing is also offered by another listing registered in VCC / ALCOM with
a different ZIP, or when the package cache already holds a ZIP of that id@version with different bytes. In that state
VCC / ALCOM may install the other ZIP without warning. Exit code 1 = STOP: do not install or update.

    python tools/preflight.py                      # compares with site/index.json of this clone
    python tools/preflight.py <path to index.json> # or with a downloaded copy

Reads %LOCALAPPDATA%/VRChatCreatorCompanion/settings.json, the cached listings it points to and the package cache
folders of this listing's ids. Request headers stored in settings.json are dropped right after loading and are never
printed; listing URLs are never printed (only host names). Nothing is written.
"""
import glob, hashlib, json, os, sys
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
target_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'site', 'index.json')
vcc = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'VRChatCreatorCompanion')
settings_path = os.path.join(vcc, 'settings.json')


def versions_of(listing):
    out = {}
    for package, body in (listing.get('packages') or {}).items():
        for version, item in (body.get('versions') or {}).items():
            out['%s@%s' % (package.lower(), version)] = (item.get('zipSHA256') or '').lower()
    return out


def host_of(url):
    try: return urlsplit(url or '').hostname or '?'
    except ValueError: return '?'


def same_place(a, b):
    try:
        x, y = urlsplit(a or ''), urlsplit(b or '')
        return (x.scheme, x.hostname, x.path) == (y.scheme, y.hostname, y.path) and bool(x.hostname)
    except ValueError: return False


target = json.loads(open(target_path, 'rb').read().decode('utf-8-sig'))
wanted = versions_of(target)
if not os.path.exists(settings_path): sys.exit('STOP: settings.json not found at ' + settings_path)
settings = json.loads(open(settings_path, 'rb').read().decode('utf-8-sig'))
repos = []
for r in settings.get('userRepos') or []:
    r.pop('headers', None)                                  # never used, never printed
    repos.append(r)
del settings

problems, unreadable, checked, own = [], [], 0, 0
for number, r in enumerate(repos, 1):
    label = 'listing #%d (id %s, host %s)' % (number, str(r.get('id') or '?')[:60], host_of(r.get('url')))
    is_own = same_place(r.get('url'), target.get('url'))
    own += is_own
    path = r.get('localPath')
    if not path or not os.path.exists(path):
        unreadable.append(label); continue
    try:
        cached = json.loads(open(path, 'rb').read().decode('utf-8-sig'))
        listing = cached.get('repo', cached)                 # ALCOM stores {"repo": {...}, ...}; VCC stores the listing
        listing.pop('headers', None); cached.pop('headers', None)
    except (ValueError, OSError, AttributeError):
        unreadable.append(label); continue
    checked += 1
    for key, digest in versions_of(listing).items():
        if key in wanted and digest != wanted[key]:
            problems.append('%s is also in %s%s with %s' % (key, label, ' [the cached copy of this listing]' if is_own else '', 'no zipSHA256' if not digest else 'a different ZIP'))

# Package cache: <Repos>/<package id>/<id>-<version>.zip and vrc-get-<id>-<version>.zip (VCC and ALCOM)
cached_zips = 0
for key, digest in wanted.items():
    pkg, version = key.split('@', 1)
    for path in glob.glob(os.path.join(vcc, 'Repos', pkg, '*.zip')):
        name = os.path.basename(path)
        if name not in ('%s-%s.zip' % (pkg, version), 'vrc-get-%s-%s.zip' % (pkg, version)): continue
        cached_zips += 1
        if hashlib.sha256(open(path, 'rb').read()).hexdigest() != digest:
            problems.append('%s: the package cache holds %s with different bytes' % (key, name))

print('this listing: %s, %d versions; registered listings read: %d (of them this listing itself: %d); cached ZIPs compared: %d'
      % (target.get('id'), len(wanted), checked, own, cached_zips))
print('not covered by this check: the built-in Official / Curated listings and local user packages')
if own > 1: problems.append('this listing is registered %d times; keep one registration' % own)
if unreadable: print('no cached copy (not checked): ' + ', '.join(unreadable))
if problems:
    print('STOP: do not install or update. The same package id and version exists with another ZIP:')
    for p in problems: print('  ' + p)
    print('Remove the other listing (or the conflicting version / cached ZIP) first, then run this again.')
    sys.exit(1)
print('PREFLIGHT: PASS' if not unreadable else 'PREFLIGHT: PASS for the listings that could be read (see the unchecked ones above)')
