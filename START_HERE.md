# ai-crate-digger - Installation Instructions

**For Mac Users**

---

## Step 1: Install Python (One Time Only)

1. Go to: **https://www.python.org/downloads/**
2. Click the big yellow button **"Download Python 3.11"**
3. Open the downloaded file and follow the installer
4. Done! You never need to do this again

---

## Step 2: Install ai-crate-digger

1. **Find the folder** you received with these files
2. **Double-click** the file called **`install.sh`**
3. Wait 5-10 minutes while it installs
4. When it says "Installation Complete", you're done!

---

## Step 3: Use ai-crate-digger

Look on your **Desktop** for an icon called **"ai-crate-digger"**

**Double-click it** to open the app!

You'll see a simple menu:

```
1. Scan Music Library    ← Start here! Point it to your music folder
2. Search Tracks         ← Find songs by genre, BPM, artist, etc.
3. Generate Playlist     ← Create a DJ set automatically
4. View Stats            ← See your music library statistics
5. Quit
```

---

## First Time Use

1. **Launch "ai-crate-digger"** from your Desktop
2. Choose **option 1** (Scan Music Library)
3. **Drag your music folder** into the window (or type the path)
   - Example: `/Users/YourName/Music`
4. Wait while it scans (could be 10-30 minutes for large libraries)
5. Done! Now you can search and create playlists

---

## Quick Examples

### Search for techno tracks:
- Launch app → option 2 → type "techno"

### Create a 60-minute house playlist:
- Launch app → option 3
- Type "house" for genre
- Type "60" for duration
- Type where to save (example: `~/Desktop/my-set.m3u`)

### See your library stats:
- Launch app → option 4

---

## Troubleshooting

**"Python 3.11 not found"**
→ Go back to Step 1 and install Python

**"Permission denied"**
→ Right-click `install.sh` → Open With → Terminal

**App won't open**
→ Right-click "ai-crate-digger" → Open (first time only)

---

## What This App Does

- **Scans** your music collection (MP3, FLAC, WAV, etc.)
- **Analyses** BPM, musical key, energy levels
- **Searches** by any criteria (genre, BPM, key, artist, mood)
- **Generates playlists** with harmonic mixing (songs that flow well together)
- **Exports** to formats DJs use (M3U, Rekordbox XML)

Good for organising your music collection and building DJ sets.

---

## Advanced (Optional)

If you want to use the command-line version:

1. Open **Terminal** (in Applications/Utilities)
2. Type: `source ~/ai-crate-digger/venv/bin/activate`
3. Now you can use commands like:
   - `crate scan ~/Music`
   - `crate search --tags techno --bpm-min 125`
   - `crate playlist --tags house --duration 60`

But the Desktop app does everything for you!
