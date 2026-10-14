"""Creates one version of the public test dummy package com.dismoni.vpm.publictest (no code, no dependencies).

    python tools/make_dummy.py 0.0.1 "first version"

The ZIP is deterministic (fixed file times, sorted entries). An existing ZIP is never overwritten: a published
id@version is never replaced. Afterwards: python tools/check_site.py --write-index (adds it to the listing).
"""
import hashlib, json, os, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = 'com.dismoni.vpm.publictest'
META = 'fileFormatVersion: 2\nguid: %s\nDefaultImporter:\n  externalObjects: {}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n'

version, note = sys.argv[1], sys.argv[2]
manifest = {'name': PKG, 'displayName': 'DM VPM Public Test (dummy)', 'version': version, 'unity': '2022.3',
            'description': 'Dummy package for testing the DIS_MONI public VPM listing. Contains no code and no assets.',
            'author': {'name': 'DIS_MONI'}, 'license': 'CC0-1.0', 'vpmDependencies': {}}
files = {
    'package.json': json.dumps(manifest, indent=2) + '\n',
    'package.json.meta': META % hashlib.md5((PKG + '/package.json').encode()).hexdigest(),
    'README.md': '# DM VPM Public Test (dummy) %s\n\n%s.\n\nTest fixture for the DIS_MONI public VPM listing. It contains no code and no assets.\nSafe to remove.\n' % (version, note),
    'README.md.meta': META % hashlib.md5((PKG + '/README.md').encode()).hexdigest(),
}
folder = os.path.join(ROOT, 'site', 'packages', PKG)
os.makedirs(folder, exist_ok=True)
path = os.path.join(folder, '%s-%s.zip' % (PKG, version))
if os.path.exists(path): sys.exit('STOP: already exists, not overwritten: ' + os.path.relpath(path, ROOT))
with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
    for rel in sorted(files):
        info = zipfile.ZipInfo(rel, (2026, 10, 14, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, files[rel])
print('created', os.path.relpath(path, ROOT).replace(os.sep, '/'), hashlib.sha256(open(path, 'rb').read()).hexdigest())
