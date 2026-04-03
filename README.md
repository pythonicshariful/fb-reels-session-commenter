# Autocommenter

Small Python helpers to **save a Facebook mobile-browser session** to a pickle file and **reuse that session** to post comments on the **Reels** feed with **undetected Chrome**. Intended for personal automation only; you are responsible for complying with Meta’s terms and policies.

## Requirements

- **Python 3.9+** (tested with 3.9 on Windows)
- **Google Chrome** installed (version should match what `undetected-chromedriver` pulls in)
- Python packages (from repo root):

```bash
pip install -r requirements.txt
```

## Project layout

| Path | Purpose |
|------|---------|
| `pklgenerator.py` | Opens Facebook mobile login, you sign in manually, then saves cookies + storage to a `.pkl` file |
| `reel_comment.py` | Loads one or more `.pkl` files, opens Reels, posts comments (mobile viewport / UA) |
| `pklfiles/` | Recommended folder for `.pkl` session files (e.g. `facebook_login_data1.pkl`, `facebook_login_data2.pkl`) |

## 1. Save a session (`pklgenerator.py`)

1. Run:

   ```bash
   python pklgenerator.py
   ```

2. Log in **manually** in the browser that opens (`m.facebook.com`).

3. When finished, press **Enter** in the terminal.

4. By default, data is written to **`facebook_login_data.pkl`** in the current working directory.

To save into `pklfiles/` with a custom name:

```python
# Or change the script’s default, or call from a tiny wrapper:
python -c "from pklgenerator import save_facebook_session; save_facebook_session('pklfiles/account1.pkl')"
```

On Windows, if ChromeDriver cache errors appear (`FileExistsError` / WinError 183), `pklgenerator.py` already clears the usual undetected-chromedriver cache path before launch.

## 2. Comment on Reels (`reel_comment.py`)

### Interactive (prompts for reel count and comment)

```bash
python reel_comment.py
```

### Non-interactive

```bash
python reel_comment.py --reels 3 --comment "Hello!"
```

### Multiple accounts (one browser, no restart)

- Put several **`*.pkl`** files under **`pklfiles/`** (sorted by filename).
- Run **without** `--pkl`: every `.pkl` in that folder is processed in order.  
  After each account finishes **`--reels`** comments, cookies/storage are cleared **in the same window** and the next PKL is applied.

```bash
python reel_comment.py --reels 2 --comment "Nice reel"
```

- Scan another directory:

  ```bash
  python reel_comment.py --pkl-dir D:\ks\autocommenter\pklfiles --reels 1 --comment "Hi"
  ```

- Pick specific files (order = order of flags):

  ```bash
  python reel_comment.py --pkl pklfiles\a.pkl --pkl pklfiles\b.pkl --reels 1 --comment "Hey"
  ```

### Useful flags

| Flag | Description |
|------|-------------|
| `--pkl` | One PKL path; repeat for multiple files (if omitted, all `*.pkl` in `--pkl-dir` are used) |
| `--pkl-dir` | Folder scanned when `--pkl` is omitted (default: `pklfiles/` next to `reel_comment.py`) |
| `--reels` | How many **different** reels to comment on **per account** |
| `--comment` | Comment text (if omitted, you are prompted) |
| `--url` | Reel feed URL (default `https://www.facebook.com/reel/`; reloaded between reels to reduce sticking on one video) |
| `--width` / `--height` | Mobile viewport for device metrics (defaults match `pklgenerator`: **390×844**) |

### Errors and debugging

- If a step fails, the script **leaves the browser open** and asks you to press **Enter** after inspecting the page (e.g. DevTools → Elements), then closes the browser.

## Flow summary

1. Generate PKL(s) with **`pklgenerator.py`** (one run per account if you use multiple PKLs).
2. Place them in **`pklfiles/`** (or pass explicit `--pkl` paths).
3. Run **`reel_comment.py`** with **`--reels`** and **`--comment`** (or answer prompts).

## Disclaimer

Automation on Meta services can violate the **Facebook Terms** or trigger rate limits or security checks. Use only accounts you control, avoid spam, and prefer **official APIs** for anything commercial or at scale. This repository is provided as-is with no warranty.
