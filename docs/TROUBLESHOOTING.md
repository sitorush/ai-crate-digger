# Troubleshooting & Known Quirks

## Common Issues

### Slow Scanning

**Problem:** Scanning 1000+ tracks takes a long time.

**Solution:** Use parallel workers:
```bash
crate scan ~/Music --workers 4
```

The default uses all CPU cores minus one. For very large libraries, consider scanning without analysis first, then analysing:

```bash
crate scan ~/Music --no-analyze  # Fast metadata extraction
crate scan ~/Music --force       # Then full analysis
```

### BPM Doesn't Match Rekordbox

**Problem:** BPM values differ from Rekordbox/Traktor.

**Cause:** Different algorithms. ai-crate-digger uses Essentia's RhythmExtractor2013, which is optimised for electronic music and should match Rekordbox closely.

**If values still differ:** The track may have tempo changes or unusual time signatures.

### Tags Not Splitting

**Problem:** Tags like "Garage / Bassline / Grime" appear as one tag.

**Cause:** Tag normalisation happens during scanning. Existing tracks need re-normalisation.

**Solution:** Re-scan with force:
```bash
crate scan ~/Music --force
```

### Search Returns Nothing

**Problem:** `crate search --tags garage` returns 0 results.

**Note:** Tag search is fuzzy - "garage" matches "UK Garage", "Speed Garage", etc. Check your tags with:
```bash
crate stats --group-by tags
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

### Worker Crashes / "Process pool was terminated abruptly"

**Problem:** Scan shows repeated "Worker failed" errors and tracks get skipped.

**Cause:** A known numpy/BLAS crash on Apple Silicon. Worker processes segfault during audio analysis. ai-crate-digger will automatically fall back to sequential analysis for any remaining tracks, so the scan will complete -- just slower.

**If the fallback is too slow or crashes persist:**
```bash
crate scan ~/Music --workers 1
```

This skips the process pool entirely and analyses tracks one at a time in the main process. Slower, but stable.

**After a crashed scan, tracks may be in the database but missing BPM/key/energy data.** Re-analyse them with:
```bash
crate scan ~/Music --force --workers 1
```

`--force` re-analyses every track already in the database, not just new ones.

### Memory Issues with Large Libraries

**Problem:** Out of memory when scanning 10,000+ tracks.

**Solution:** Scan in batches by subfolder:
```bash
crate scan ~/Music/House
crate scan ~/Music/Techno
crate scan ~/Music/DnB
```

## Mix Identification

### "The fingerprint index is empty"

**Cause:** No tracks have been fingerprinted yet.

**Solution:**
```bash
crate fingerprint
```

Only tracks without a fingerprint are processed, so re-running it is cheap. Run it again after scanning new tracks.

### "...over the safety limit" / index too large

**Cause:** Matching loads every fingerprint into memory. The index is capped at about 200 million hashes (roughly 600 hours of audio, about 5 GB of RAM while loading) to avoid exhausting memory.

**Solution:** Identify against a smaller library (use a separate database with `CRATE_DB_PATH`), or ask for the hash density to be lowered in `FingerprintParams`, which needs `FINGERPRINT_VERSION` bumped and `crate fingerprint --force` re-run.

### Identifying a long mix is slow or uses a lot of memory

**Cause:** A 99-minute stereo MP3 took about 7 minutes and peaked near 7.5 GB of RAM in one test. Decoding the recording and loading the index both need memory.

**Solution:** Close other heavy apps, or split the recording into shorter files. Over MCP the call returns a `job_id` at once; poll `get_job_status` until it finishes. Jobs are forgotten if the MCP server restarts, so re-run `identify_mix` if that happens.

### A track I played was not found

Check, in order:
1. Is the track in your library and fingerprinted? `crate stats` shows the library; run `crate fingerprint`.
2. Try `crate identify <file> --min-confidence low`. Weak matches are hidden by default.
3. Short samples, heavy looping, and different edits of the same song (extended versus radio) can match partly or not at all.
4. A very large tempo change (over 8%) is outside the search range. Widen `CRATE_MIX_SPEED_RANGE`.

### The same track appears several times in a row

**Cause:** The timeline lists every matched stretch, and stretches break where the match is weaker. They are the same track; read them as one run.

### Lots of "libmpg123 ... No extra frame text" lines

**Cause:** Some MP3 files have unusual ID3 tags. The warnings come from the audio decoder and are harmless.

### Fingerprinting stopped part way

**Solution:** Run `crate fingerprint` again. Finished tracks are skipped, so it resumes where it stopped. Tracks that cannot be decoded are listed at the end of the run.

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
crate clean
```

### 6. M3U Paths Are Absolute

Exported M3U files contain absolute paths. If you move your music library, the playlists will break.

### 7. Rekordbox XML is One-Way

Exported Rekordbox XML can be imported into Rekordbox, but ai-crate-digger cannot import from Rekordbox.

## Reset Everything

To start fresh:
```bash
crate reset -y
```

This deletes the database and vector store. You'll need to re-scan.

## Getting Help

1. Check this troubleshooting guide
2. Run with verbose logging: `crate scan ~/Music 2>&1 | tee scan.log`
3. Open an issue with the log file
