# dm-vpm — DIS_MONI VPM Repository

Listing URL: `https://displaymonitor.github.io/dm-vpm/index.json` (listing id `com.dismoni.vpm`)

Packages: `com.dismoni.yamaplayer.localplaylist` (DM YamaPlayer Local Playlist; terms in the package's LICENSE.md,
Japanese authoritative, and LICENSE.en.md). The dummy package `com.dismoni.vpm.publictest` (0.0.1, 0.0.2) of the
public test stays listed (ZIPs, listing, ledger entries and history kept).

Product ZIPs may contain `.cs .asmdef .asset .prefab .unity .png` besides `.json .meta .md` (`entry_types` in
`publish.json`). The gate refuses any `WebUnit/Client.dm*` entry and the bytes of the DM Modified WebUnit Clients.

## Layout

| Path | Role |
|---|---|
| `site/` | Exactly what GitHub Pages serves: `index.json`, `index.html`, `robots.txt`, `packages/<id>/<id>-<version>.zip` |
| `ledger.json` | Every `id@version` ever published with its SHA-256. Append-only; an entry may be unlisted, never changed or removed |
| `publish.json` | Listing name / id / URL, allowed package ids, allowed static files |
| `tools/check_site.py` | Publication gate (exact file set, allowed ids, SHA-256 = ledger, listing built only from the ledger, append-only ledger, forbidden-text scan) |
| `tools/verify_live.py` | After a deploy: fetches the site without credentials and compares bytes, media types and 404s |
| `tools/preflight.py` | For users: run before installing; stops when another registered listing or the package cache has the same `id@version` with other bytes |
| `tools/make_dummy.py` | Builds a dummy version (deterministic ZIP, never overwrites) |
| `.github/workflows/pages.yml` | Push to `main` → gate → deploy. Minimal permissions, actions pinned by commit SHA, no repository secrets |

## Rules

- A published `id@version` is never replaced. Fixes are new versions.
- The same `id@version` must have one SHA-256 across every DIS_MONI listing.
- Nothing is placed on Pages outside the workflow, and nothing is deployed if the gate fails.
- If `tools/preflight.py` prints STOP, do not install or update until it passes.

## Stop publication

1. **One version**: set `"listed": false` for it in `ledger.json`, delete its ZIP from `site/`, run
   `python tools/check_site.py --write-index`, commit and push. New installs of that version stop after the deploy.
2. **The whole site, immediately**: repository Settings → Pages → *Unpublish site*
   (or `gh api -X DELETE repos/DISPLAYMONITOR/dm-vpm/pages`). Then disable the workflow
   (`gh workflow disable pages.yml -R DISPLAYMONITOR/dm-vpm`) so a push does not publish again.
3. **Keep it down**: archive the repository (read-only) after 2.

ZIPs already downloaded, cached by VCC / ALCOM or installed in projects cannot be recalled.

## Recover

- Wrong listing content: do **not** `git revert` a commit that added ledger entries (the append-only history check
  refuses a removed entry). Stop the version as in "Stop publication" 1 (`"listed": false`, keep the entry and its
  SHA-256, delete its ZIP from `site/`, `python tools/check_site.py --write-index --history`), commit and push.
  A commit that only changed static files (`index.html`, README) may be reverted.
- To withdraw `com.dismoni.yamaplayer.localplaylist@1.0.1-rc.11`: that same procedure. Fixes come as a new version.
- After *Unpublish*: Settings → Pages → Source *GitHub Actions*, enable the workflow, run it
  (`gh workflow run pages.yml -R DISPLAYMONITOR/dm-vpm`), then `python tools/verify_live.py`.
- Do not change the listing URL: users would have to register it again.
