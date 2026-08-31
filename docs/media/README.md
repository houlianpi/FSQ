# Release Media

This directory owns the v0.1.0 public demo video, product screenshots, subtitles, naming rules, privacy review, and new-user acceptance.

The README uses `fsq-v0.1.0-demo-preview.gif` for an inline animated preview that works on GitHub. It also links to the GitHub-hosted full video at <https://github.com/user-attachments/assets/aa9d0a12-2f93-4894-8349-52a013424939> and the hosted YouTube demo at <https://youtu.be/QqCahxGDdS0>. The GitHub Pages-ready [`docs/demo.html`](../demo.html) page embeds the same YouTube video with muted autoplay for contexts that allow it.

The edited MP4 is hosted outside the Git repository through GitHub media attachment and YouTube. The original local screen recording is intentionally not committed.

## Naming

- `fsq-v0.1.0-demo-thumbnail.png` — linked video thumbnail;
- `fsq-v0.1.0-demo-preview.gif` — lightweight README animation built from approved product screenshots;
- `https://github.com/user-attachments/assets/aa9d0a12-2f93-4894-8349-52a013424939` — GitHub README media preview;
- `../demo.html` — hosted-video demo page with muted YouTube autoplay;
- `01-describe-goal.png` — goal entry and setup;
- `02-execute-workflow.png` — execution timeline;
- `03-capture-evidence.png` — captured evidence;
- `04-generate-candidate.png` — Run-local candidate Case;
- `05-inspect-run.png` — static report inspection;
- `demo.en.srt` and `demo.zh-CN.srt` — subtitles.

Do not commit empty placeholder media files. README references are added only when the corresponding approved artifact exists. Large video files stay outside Git history; the GIF is a short preview, not the canonical full demo.
