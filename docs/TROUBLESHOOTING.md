# Troubleshooting & Known Quirks

## Common Issues

### Slow Scanning

**Problem:** Scanning 1000+ tracks takes a long time.

**Solution:** Use parallel workers:
```bash
dj scan ~/Music --workers 4
```

The default uses all CPU cores minus one. For very large libraries, consider scanning without analysis first, then analyzing:

```bash
dj scan ~/Music --no-analyze  # Fast metadata extraction
dj scan ~/Music --force       # Then full analysis
```

### BPM Doesn't Match Rekordbox

**Problem:** BPM values differ from Rekordbox/Traktor.

**Cause:** Different algorithms. ai-crate-digger uses Essentia's RhythmExtractor2013 which is optimized for electronic music and should match Rekordbox closely.

**If values still differ:** The track may have tempo changes or unusual time signatures.

### Tags Not Splitting

**Problem:** Tags like "Garage / Bassline / Grime" appear as one tag.

**Cause:** Tag normalization happens during scanning. Existing tracks need re-normalization.

**Solution:** Re-scan with force:
```bash
dj scan ~/Music --force
```

### Search Returns Nothing

**Problem:** `crate search --tags garage` returns 0 results.

**Note:** Tag search is fuzzy - "garage" matches "UK Garage", "Speed Garage", etc. Check your tags with:
```bash
dj stats --group-by tags
```

### MCP Export Fails with "Errno 2"

**Problem:** Claude Desktop can't export playlists.

**Cause:** Claude suggested a path inside its container (`/mnt/`, `/home/claude/`) which doesn't exist on your machine.

**Solution:** Use paths on YOUR local machine:
```
~/Desktop/playlist.m3u           # Works
/Users/you/Downloads/set.m3u     # Works
/mnt/user-data/playlist.m3u      # Fails!
```

### "Essentia model not found"

**Problem:** First scan fails downloading models.

**Cause:** Network issue or firewall blocking essentia.upf.edu.

**Solution:** Manually download:
```bash
mkdir -p ~/.ai-crate-digger/models
cd ~/.ai-crate-digger/models
curl -O https://essentia.upf.edu/models/music-style-classification/discogs-effnet/discogs-effnet-bs64-1.pb
curl -O https://essentia.upf.edu/models/music-style-classification/discogs-effnet/discogs-effnet-bs64-1.json
```

### Database Locked

**Problem:** "database is locked" error.

**Cause:** Another process is using the database.

**Solution:**
1. Close Claude Desktop (if using MCP)
2. Kill any running ai-crate-digger processes
3. Retry

### Memory Issues with Large Libraries

**Problem:** Out of memory when scanning 10,000+ tracks.

**Solution:** Scan in batches by subfolder:
```bash
dj scan ~/Music/House
dj scan ~/Music/Techno
dj scan ~/Music/DnB
```

## Known Quirks

### 1. Harmonic Mixing Uses Camelot Wheel

Playlist generation uses Camelot notation for harmonic compatibility:
- Same key (8A → 8A)
- Adjacent keys (8A → 7A, 8A → 9A)
- Relative major/minor (8A → 8B)

### 2. Semantic Search Requires Metadata

ChromaDB semantic search works best when tracks have:
- Title
- Artist
- Tags/genre

Tracks with only filenames will have poor semantic matches.

### 3. Sample Rate Affects Analysis Quality

Audio is resampled to 22050 Hz for analysis (configurable). Lower rates = faster but less accurate.

### 4. Folder Names Become Tags

ai-crate-digger extracts folder names as tags. A track in:
```
/Music/UK Garage/2024/track.mp3
```
Gets "UK Garage" as a tag (but not "2024" - years are filtered).

### 5. Re-scanning Doesn't Delete

`crate scan --force` re-analyzes files but won't remove tracks for deleted files.

To clean orphaned tracks:
```bash
dj clean
```

### 6. M3U Paths Are Absolute

Exported M3U files contain absolute paths. If you move your music library, the playlists will break.

### 7. Rekordbox XML is One-Way

Exported Rekordbox XML can be imported into Rekordbox, but ai-crate-digger cannot import from Rekordbox.

## Reset Everything

To start fresh:
```bash
dj reset -y
```

This deletes the database and vector store. You'll need to re-scan.

## Getting Help

1. Check this troubleshooting guide
2. Run with verbose logging: `crate scan ~/Music 2>&1 | tee scan.log`
3. Open an issue with the log file
