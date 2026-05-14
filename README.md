# TE Style

We formally define task-execution (TE) style as the set of behavioral attributes exhibited by an embodied agent while attempting to execute a natural language task.

## Static Viewer (GitHub Pages)

- Entry page: `index.html`
- Data source: `te-style_labels.csv`
- Videos are rendered in-table with HTML5 players.

### Prepare videos for web hosting

Run:

```bash
python scripts/normalize_video_formats.py
```

This script:

- normalizes videos to H.264/AAC `.mp4`
- compresses/reduces scale until each file is <= 50MB
- updates `video` paths inside `te-style_labels.csv` when extensions change