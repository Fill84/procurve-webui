# Launch checklist — order and timing

Suggested cadence to spread the launch over ~2 weeks without burning out
HN/Reddit/awesome-list maintainer goodwill.

## Day 0 (already done)

- [x] GitHub repo public at https://github.com/Fill84/procurve-webui
- [x] v0.1.0 release with README screenshots
- [x] Repo description + topics + homepage URL set on GitHub
- [x] Forgejo repo `FiLL/procurve-webui` mirrors GitHub history
- [x] All Claude/Anthropic references stripped from history

## Week 1

- [ ] **Activate the GitHub Actions Docker workflow.** Follow
  `release-docker.yml.template` instructions in `tools/promotion/README.md`.
  Once it's running and you've made the package public, edit the main
  README's quick-start to use `docker pull ghcr.io/fill84/procurve-webui`
  instead of `git clone && docker build`.

- [ ] **Newsletters** (15 min total, blind submissions, see `newsletters.md`):
  - [ ] Console.dev
  - [ ] Self-Hosted Weekly
  - [ ] Hacker Newsletter
  - [ ] Changelog Weekly
  - [ ] Awesome Newsletters

- [ ] **First awesome-list PR.** Pick `awesome-sysadmin` (most likely to
  accept). Entry + PR description in `awesome-list-entries.md`.

- [ ] **Hacker News Show HN.** Post once, Tuesday–Thursday morning US
  time. Body + title in `hn-show.md`. Don't post Reddit content the same
  48 hours.

## Week 2

- [ ] **Reddit r/homelab.** Post in `reddit-homelab.md`.

- [ ] **Reddit r/ReverseEngineering.** Different angle (Phase 0
  reverse-engineering), post in `reddit-reverseengineering.md`. Wait at
  least 2–3 days after r/homelab so the same audience doesn't see the
  same thing twice.

- [ ] **Second awesome-list PR.** Pick `awesome-network-automation`
  (the Python client angle). Entry in `awesome-list-entries.md`.

## Week 3

- [ ] **dev.to article.** Long-form, ~5 min read. Full content in
  `dev-to-article.md`. Cover image: `docs/screenshots/03-status.png`.
  Set canonical URL to the GitHub repo.

- [ ] **Reddit r/networking** *or* r/selfhosted (pick whichever feels
  right based on how the previous posts went). Drafts in
  `reddit-networking.md` and `reddit-selfhosted.md`.

## Week 4 and after

- [ ] Third awesome-list PR if the first two went smoothly
  (`awesome-selfhosted`, hardest to land but biggest audience).

- [ ] Reach out to networking blogs if you feel like it: PacketPushers
  (https://packetpushers.net/), IPSpace (https://ipspace.net/). Single
  email, polite, "thought this might interest your audience".

- [ ] Then stop. Let it sit. Issues from real users will be the only
  thing that drives v0.2.0 priorities, and they'll come slowly.

## Things NOT to do

- Don't post to multiple subreddits the same day — bot-detection
  triggers and posts get auto-removed.
- Don't ask for upvotes anywhere. HN/Reddit detect this and downrank.
- Don't "follow up" your own posts with comments from a second account
  saying "yes I tried this it's great". Sock-puppet detection is good
  on these platforms now.
- Don't email vendors. HPE doesn't care, and antagonizing them wastes
  your time.
- Don't open issues on other repos to advertise this one. That's spam
  even if your project is relevant.
