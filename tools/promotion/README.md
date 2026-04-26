# tools/promotion — ready-to-paste launch assets

This directory holds drafts and templates produced during the v0.1.0 launch
preparation. Everything here is "post-and-forget" — no sustained social-media
presence required. Pick what you want to use, paste, done.

## Quick map

| File | What it does | Effort |
|---|---|---|
| `release-docker.yml.template` | GitHub Actions workflow that builds + pushes a multi-arch Docker image to `ghcr.io` on every `v*` tag. | 5 min, see below |
| `hn-show.md` | Hacker News "Show HN" post (title + body, ready to paste). | 30 sec |
| `reddit-homelab.md` | Post for `r/homelab`. | 30 sec |
| `reddit-networking.md` | Post for `r/networking`. | 30 sec |
| `reddit-selfhosted.md` | Post for `r/selfhosted`. | 30 sec |
| `reddit-reverseengineering.md` | Post for `r/ReverseEngineering` (focus: the Phase 0 reverse-engineering of the Java applet). | 30 sec |
| `dev-to-article.md` | Long-form technical article about reverse-engineering `agent.jar`. | 1 click on dev.to |
| `awesome-list-entries.md` | Pre-formatted entries you can copy into PRs against `awesome-selfhosted`, `awesome-sysadmin`, etc. | 5 min per PR |
| `newsletters.md` | List of newsletters that accept third-party submissions, with email templates. | 5 min total |

## Activating the GitHub Actions Docker workflow

The OAuth token used by `gh` CLI does not have `workflow` scope by default,
which is why this file is here as a template instead of in
`.github/workflows/`. To activate:

1. **Refresh `gh` auth with workflow scope:**

   ```bash
   gh auth refresh -h github.com -s workflow
   ```

   Opens a browser once. Takes 30 seconds.

2. **Move the file into place and push:**

   ```bash
   mkdir -p .github/workflows
   mv tools/promotion/release-docker.yml.template .github/workflows/release-docker.yml
   git add .github/workflows/release-docker.yml
   git commit -m "ci: build + publish multi-arch Docker image to ghcr.io on tag push"
   git push origin main
   ```

3. **Trigger a build of the existing v0.1.0 tag (no new tag needed):**

   ```bash
   gh workflow run release-docker.yml --ref v0.1.0
   ```

   The image lands at `ghcr.io/fill84/procurve-webui:0.1.0` and `:latest`
   five minutes later. Update the README's quick-start to use
   `ghcr.io/fill84/procurve-webui` instead of `git clone + docker build`.

4. **Make the package public** (one-time, via the GitHub UI):

   GitHub → Profile → Packages → procurve-webui → "Package settings" →
   "Change visibility" → Public.

From then on every new tag push triggers an automatic image build, no
further action.
