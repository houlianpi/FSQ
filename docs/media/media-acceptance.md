# Public Media Acceptance

## Provenance

- [x] Product screenshots and video are captured from a release-candidate build.
- [x] Synthetic or generated brand art is not presented as product evidence.
- [ ] Commit SHA, wheel SHA-256, OS, browser, FSQ version, and capture date are recorded outside the media frame for the final release candidate.
- [x] Every command, label, and result shown matches the current v0.1.0 release materials.

## Privacy and security

- [x] No token, API key, password, cookie, authorization header, device code, QR code, or Provider response is visible.
- [x] No personal name, account avatar, email, tenant, organization, repository, hostname, device serial, IP address other than loopback, or private URL is visible.
- [x] No absolute personal path, shell history, notification, browser bookmark, autofill suggestion, clipboard content, or unrelated Workspace is visible.
- [x] Run metadata, logs, screenshots, UI trees, and reports have been inspected frame by frame.
- [ ] Image/video metadata has been removed and exported files have been scanned again for the final release candidate.

## Accuracy

- [x] The demo says alpha and does not imply a 1.0 stability guarantee.
- [x] FSQ is described as complementing Playwright, uiautomator2, pywinauto, and Appium.
- [x] Claims are observable in the captured run or supported by linked public documentation.
- [x] No “zero flakiness,” “always,” “perfect,” or unsupported competitor comparison appears.
- [x] AI exploration, evidence, review, and deterministic replay are visually distinguishable.

## Accessibility and delivery

- [x] The story is understandable with audio muted.
- [x] English and Chinese subtitle files match the final edit.
- [x] Captions remain readable at 1280x720 and do not cover evidence.
- [x] Screenshots have descriptive alt text in consuming documents.
- [x] The README uses a static thumbnail plus hosted YouTube video and subtitle file links; it does not depend on GitHub autoplaying repository MP4 files.
- [x] The optional GitHub Pages-ready demo page embeds the hosted YouTube video with muted autoplay; README itself remains static because GitHub sanitizes embeds.
- [ ] Files meet the size targets in [the storyboard](demo-storyboard.md), except the committed MP4 may exceed the optional 12 MB target until a smaller export is produced.

## New-user test

Ask at least three people who did not build FSQ to use only the public materials. Record whether they can:

1. explain FSQ in one sentence after 30 seconds;
2. distinguish FSQ from its platform backends;
3. find and complete installation in five minutes;
4. identify where evidence and Runs are stored;
5. locate prerequisites, privacy guidance, and troubleshooting; and
6. complete the public deterministic Web example within 15 minutes after prerequisites are available.

Do not publish while a repeated comprehension or setup failure has no documented repair.
