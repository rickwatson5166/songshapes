# Phase 3A Replit Deployment Guide

**Goal**: Get Phase 3A live on Replit in 15 minutes with zero payment friction.

---

## Step 1: Create Replit Account (2 minutes)

1. Go to **https://replit.com**
2. Click **"Sign up"** (top right)
3. Choose **"Sign up with email"**
4. Enter email and password (that's it—no credit card required)
5. Verify email
6. You're in ✅

---

## Step 2: Create New Replit Project (1 minute)

1. Click **"+ Create"** button (top left)
2. Select **"Python"** as language
3. Name it: `songshapes-phase3a`
4. Click **"Create Repl"**
5. Wait for environment to load (~30 seconds)

---

## Step 3: Clone Your SongShapes Code (2 minutes)

In the Replit **Shell** tab (at bottom):

```bash
# Clone your repo
git clone https://github.com/rickwatson5166/songshapes.git .

# (The period at the end puts files in current directory)
```

Wait for clone to complete. You should see all your .py files appear in the left sidebar.

---

## Step 4: Install Dependencies (3 minutes)

In the Shell:

```bash
pip install -r requirements.txt
```

This will install:
- Flask (web framework)
- numpy, scipy, librosa (audio processing)
- soundfile (audio I/O)
- scikit-learn, matplotlib (supporting libs)

**Note**: This takes a couple minutes. Replit will show progress. Just wait.

---

## Step 5: Start the Flask Server (1 minute)

In the Shell:

```bash
python3 app.py
```

You should see output like:
```
 * Running on http://0.0.0.0:5000
```

**Important**: Don't close this terminal window. Leave it running.

---

## Step 6: Get Your Live URL (1 minute)

Once Flask is running:

1. Look at the top of the Replit window
2. Click the **"Webview"** tab (if not already visible)
3. You'll see a URL like: `https://songshapes-phase3a.rickwatson.repl.co`
4. That's your live Phase 3A instance ✅

---

## Step 7: Test Phase 3A Live

### Option A: Web Browser
1. Open your Replit URL in browser
2. You should see the SongShapes UI
3. Try uploading an audio file
4. Test: melody extraction → chord detection → accompaniment generation

### Option B: Use Your Test Script
Open another Shell tab in Replit and run:

```bash
python3 test_phase3a.py
```

(But change `API_URL = "http://localhost:5000"` to your Replit URL first)

---

## Step 8: Share & Iterate

Your Replit URL is live and shareable. You can:

1. **Edit code** in Replit directly (left sidebar)
2. **See changes** instantly (Flask auto-reloads)
3. **Share URL** with others to test
4. **Check logs** in Shell tab to debug
5. **Monitor** what users upload and test

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'librosa'"
- Run `pip install -r requirements.txt` again
- Wait for completion
- Restart Flask with `python3 app.py`

### "Address already in use" error
- Use a different port: `python3 app.py --port 5001`
- Update Replit to use port 5001

### Audio files too large
- Replit free tier has upload limits (~100MB)
- Use smaller test files
- Upgrade to Replit Pro later if needed

### Flask not responding
- Check Shell tab for error messages
- Restart: Stop Flask (Ctrl+C), run `python3 app.py` again
- Check that all dependencies installed: `pip list`

---

## What You Get Now

✅ **Live Phase 3A**
- Melody extraction working
- Chord detection working  
- Accompaniment generation working
- All three endpoints live and testable

✅ **Development Environment**
- Edit code in Replit, changes appear instantly
- Monitor user uploads and test scenarios
- Build out features as needed

✅ **No Payment Required**
- Replit free tier is sufficient for testing
- Upgrade to Pro ($7/month) only if you exceed limits

---

## Next Steps (After Deployment)

1. **Test with real audio** - Upload your own music files
2. **Iterate UI** - Improve the web interface based on testing
3. **Add features** - Stem separation, vocal isolation, etc.
4. **Gather feedback** - Share link with musicians/testers
5. **Monitor performance** - Check Replit logs for issues
6. **Upgrade when needed** - Move to Pro tier if free tier hits limits

---

## Emergency: Need to Stop/Restart?

In Replit Shell:
- **Stop Flask**: Press `Ctrl+C`
- **Restart Flask**: `python3 app.py`
- **Clear cache**: `rm -rf __pycache__ .pytest_cache`
- **Fresh start**: Delete .replit file and let Replit regenerate it

---

## Support

If you hit issues:
1. Check the Shell tab for error messages
2. Post error in Replit chat (? icon bottom right)
3. Check Replit docs: https://docs.replit.com

You've got this! 🚀
