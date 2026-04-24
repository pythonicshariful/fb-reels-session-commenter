"""
Load session from PKL (same format as pklgenerator.py), open Reels, optional
\"Not now\", open comment composer, type text, post. Uses mobile viewport/UA.
"""

import argparse
import pickle
import random
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

import undetected_chromedriver as uc

from pklgenerator import (
    _apply_mobile_emulation,
    _chrome_major_version,
    _mobile_emulation_params,
    _prepare_undetected_chromedriver_cache,
)

# Same logical size as pklgenerator mobile emulation (390×844).
DEFAULT_VIEWPORT_WIDTH = 390
DEFAULT_VIEWPORT_HEIGHT = 1000


_thread_local = threading.local()

def _log(msg: str) -> None:
    logger = getattr(_thread_local, "logger", None)
    if logger:
        logger(msg)
    else:
        print(f"[reel_comment] {msg}", flush=True)


def _script_dir() -> Path:
    return Path(__file__).resolve().parent


def _load_session(pkl_path: Path) -> dict:
    _log(f"Loading PKL: {pkl_path.resolve()}")
    with pkl_path.open("rb") as f:
        return pickle.load(f)


def _print_pkl_summary(data: dict) -> None:
    _log(f"PKL top-level keys: {list(data.keys())}")
    if data.get("url"):
        _log(f"PKL saved page URL: {data['url']}")
    cookies = data.get("cookies") or []
    _log(f"PKL cookies count: {len(cookies)}")
    for i, c in enumerate(cookies):
        _log(
            f"  cookie[{i}] name={c.get('name')!r} domain={c.get('domain')!r} "
            f"path={c.get('path')!r} secure={c.get('secure')}"
        )
        val = c.get("value", "")
        if val is not None:
            sval = str(val)
            preview = sval if len(sval) <= 48 else sval[:45] + "..."
            _log(f"           value length={len(sval)} preview={preview!r}")

    for key, label in (("local_storage", "localStorage"), ("session_storage", "sessionStorage")):
        store = data.get(key) or {}
        _log(f"PKL {label} keys: {len(store)}")
        for k, v in sorted(store.items()):
            s = str(v) if v is not None else ""
            preview = s if len(s) <= 160 else s[:157] + "..."
            _log(f"  {label}[{k!r}] ({len(s)} chars) = {preview!r}")


def _add_cookies(driver, cookies: list) -> None:
    allowed = {"name", "value", "domain", "path", "secure", "httpOnly", "expiry", "sameSite"}
    ok, fail = 0, 0
    for c in cookies:
        try:
            nc = {k: v for k, v in c.items() if k in allowed and v is not None}
            if "expiry" in nc:
                nc["expiry"] = int(nc["expiry"])
            ss = nc.get("sameSite")
            if ss is not None and ss not in ("Strict", "Lax", "None"):
                nc.pop("sameSite", None)
            driver.add_cookie(nc)
            ok += 1
            _log(f"add_cookie OK: {nc.get('name')!r} domain={nc.get('domain')!r}")
        except Exception as ex:
            fail += 1
            _log(f"add_cookie FAIL: {c.get('name')!r} — {type(ex).__name__}: {ex}")
    _log(f"Cookies applied: {ok} ok, {fail} failed (of {len(cookies)} total)")


def _restore_storage(
    driver,
    local_storage: Optional[Dict[str, str]],
    session_storage: Optional[Dict[str, str]],
) -> None:
    src = """
        const entries = arguments[0];
        const storage = arguments[1] === 'session' ? sessionStorage : localStorage;
        for (const [k, v] of Object.entries(entries || {})) {
          try { storage.setItem(k, String(v)); } catch (e) {}
        }
    """
    if local_storage:
        _log(f"Restoring localStorage: {len(local_storage)} keys")
        driver.execute_script(src, local_storage, "local")
    if session_storage:
        _log(f"Restoring sessionStorage: {len(session_storage)} keys")
        driver.execute_script(src, session_storage, "session")


def _clear_facebook_site_data(driver) -> None:
    """Remove Facebook cookies and storage in this profile (same window, next PKL = next user)."""
    _log("Clearing Facebook cookies + storage (account switch, browser stays open)…")
    for url in ("https://m.facebook.com/", "https://www.facebook.com/"):
        try:
            driver.get(url)
            time.sleep(0.45)
            driver.execute_script(
                "try { localStorage.clear(); sessionStorage.clear(); } catch (e) {}"
            )
            driver.delete_all_cookies()
        except Exception as ex:
            _log(f"  clear on {url!r}: {ex}")
    _log("Facebook state cleared for switch.")


def _restore_facebook_session(driver, data: dict) -> None:
    cookies = data.get("cookies") or []
    local_storage = data.get("local_storage") or {}
    session_storage = data.get("session_storage") or {}

    _log("Navigating to https://m.facebook.com/ for cookie/storage restore")
    driver.get("https://m.facebook.com/")
    _log(f"After GET m.facebook.com: url={driver.current_url!r} title={driver.title!r}")
    _add_cookies(driver, cookies)
    _restore_storage(driver, local_storage, session_storage)
    _log("Refreshing m.facebook.com")
    driver.refresh()
    time.sleep(1)
    _log(f"After refresh: url={driver.current_url!r} title={driver.title!r}")


def _is_logged_in(driver) -> bool:
    """Check if the session is logically logged in based on URL and page content."""
    url = driver.current_url.lower()
    if any(k in url for k in ["login", "checkpoint", "two_step_verification"]):
        _log(f"Login failed/blocked: URL indicates non-logged state ({url})")
        return False

    # Check for "Log In" or "Sign Up" indicators in the DOM
    # Mobile common markers
    markers = [
        "//button[contains(., 'Log In')]",
        "//button[contains(., 'Login')]",
        "//div[contains(text(), 'Welcome to Facebook')]",
        "//a[contains(@href, '/reg/') or contains(@href, '/r.php')]",
    ]
    for xp in markers:
        if driver.find_elements(By.XPATH, xp):
            _log(f"Login failed: Found login marker XPath: {xp}")
            return False

    _log("Login status looks OK (no login markers found).")
    return True


def _create_mobile_driver(
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
):
    major = _chrome_major_version()
    _w0, _h0, dpr, ua = _mobile_emulation_params(major)
    width, height = int(viewport_width), int(viewport_height)
    _log(
        f"Chrome version_main hint: {major!r}; viewport {width}x{height} dpr={dpr} UA={ua!r}"
    )

    options = uc.ChromeOptions()
    options.add_argument(f"--user-agent={ua}")
    options.add_argument(f"--window-size={width},{height}")

    kwargs = {"options": options}
    if major is not None:
        kwargs["version_main"] = major
    _prepare_undetected_chromedriver_cache()
    _log("Starting undetected_chromedriver…")
    driver = uc.Chrome(**kwargs)
    _apply_mobile_emulation(driver, width, height, dpr, ua)
    _log("Driver ready (mobile emulation applied)")
    return driver


def _js_click(driver, element) -> None:
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
        element,
    )
    time.sleep(0.15)
    driver.execute_script(
        """
        const el = arguments[0];
        if (el && typeof el.click === 'function') {
            el.click();
        } else if (el) {
            const ev = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
            el.dispatchEvent(ev);
        }
        """,
        element,
    )
    try:
        tag = element.tag_name
        aria = element.get_attribute("aria-label")
        rid = element.get_attribute("id")
        cls = (element.get_attribute("class") or "")[:120]
        _log(f"JS click done on <{tag}> id={rid!r} aria-label={aria!r} class~{cls!r}")
    except Exception as ex:
        _log(f"JS click (element describe failed): {ex}")


def _snapshot_find_counts(driver, xpaths, label: str) -> None:
    parts = []
    for xp in xpaths:
        n = len(driver.find_elements(By.XPATH, xp))
        parts.append(f"{n}«{xp[:50]}…»" if len(xp) > 50 else f"{n}«{xp}»")
    _log(f"{label} match counts: " + " | ".join(parts))


def _wait_first_xpath(driver, xpaths, timeout: float, label: str = "xpath"):
    """Return first element matching any XPath (presence only — for JS click)."""

    def _any_present(d):
        for i, xp in enumerate(xpaths):
            els = d.find_elements(By.XPATH, xp)
            if els:
                _log(f"{label}: matched XPath[{i}] count={len(els)} xpath={xp!r}")
                return els[0]
        return False

    try:
        el = WebDriverWait(driver, timeout).until(_any_present)
        return el
    except TimeoutException:
        _log(f"{label}: TIMEOUT after {timeout}s — snapshot:")
        _log(f"  current_url={driver.current_url!r} title={driver.title!r}")
        _snapshot_find_counts(driver, xpaths, label)
        raise


def _click_not_now_js(driver, timeout: float) -> bool:
    xpaths = [
        "//div[@role='button' and @aria-label='Not now']",
        "//*[@role='button' and @aria-label='Not now']",
    ]
    try:
        el = _wait_first_xpath(driver, xpaths, timeout, label="Not now")
        _js_click(driver, el)
        _log("Clicked Not now")
        return True
    except TimeoutException:
        _log("Not now button not found (skipped)")
        return False


def _wait_post_comment_button(driver, timeout: float):
    """Mobile Reels: 'Post a comment'; desktop-style: 'Post comment'. Skip if aria-disabled."""

    xpaths = (
        "//div[@role='button' and @aria-label='Post a comment']",
        "//*[@role='button' and @aria-label='Post a comment']",
        "//div[@role='button' and @aria-label='Post comment']",
        "//*[@role='button' and @aria-label='Post comment']",
    )

    def _find_post(d):
        for xp in xpaths:
            for el in d.find_elements(By.XPATH, xp):
                dis = el.get_attribute("aria-disabled")
                if dis in ("true", "True"):
                    continue
                _log(
                    f"Post: found (aria-disabled={dis!r}) xpath={xp!r}"
                )
                return el
        return False

    try:
        return WebDriverWait(driver, timeout).until(_find_post)
    except TimeoutException:
        _log("Post button: TIMEOUT — snapshot:")
        _log(f"  current_url={driver.current_url!r} title={driver.title!r}")
        _snapshot_find_counts(driver, list(xpaths), "Post")
        for xp in xpaths:
            for el in driver.find_elements(By.XPATH, xp):
                _log(f"  candidate aria-disabled={el.get_attribute('aria-disabled')!r}")
        raise


def _normalize_reel_feed_url(url: str) -> str:
    """Main Reels feed with trailing slash — reloading gives a new suggested reel."""
    u = (url or "").strip()
    if not u:
        return "https://www.facebook.com/reel/"
    if not u.startswith("http"):
        u = "https://" + u.lstrip("/")
    low = u.lower()
    if "facebook.com" in low or "fb.watch" in low or "m.facebook.com" in low:
        if "/reel" in low:
            return "https://www.facebook.com/reel/"
    return "https://www.facebook.com/reel/"


def _scroll_feed_try_next_reel(driver) -> None:
    """Optional: nudge vertical feed (may work on some layouts)."""
    try:
        driver.execute_script(
            """
            window.scrollBy(0, Math.min(800, window.innerHeight * 0.85));
            """
        )
        time.sleep(0.5)
    except Exception as ex:
        _log(f"scroll_feed_try_next_reel: {ex}")
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ARROW_DOWN)
        time.sleep(0.25)
        body.send_keys(Keys.PAGE_DOWN)
    except Exception as ex:
        _log(f"scroll_feed keys: {ex}")


def _go_to_fresh_reel_feed(driver, feed_url: str, settle: float = 2.5) -> None:
    """Reload reel feed so the next clip is not the same as the one just commented on."""
    target = _normalize_reel_feed_url(feed_url)
    _log(f"Loading reel feed for next video: {target!r}")
    driver.get(target)
    time.sleep(settle)
    _log(f"After feed load: url={driver.current_url!r} title={driver.title!r}")


def _comment_on_current_reel(
    driver,
    comment: str,
    step_timeout: float,
    not_now_timeout: float,
    index: int,
    total: int,
) -> None:
    _log(f"--- Reel {index + 1} / {total} ---")
    _click_not_now_js(driver, not_now_timeout)

    comment_xpaths = [
        "(//div[@role='button' and @aria-label='Comment'])[1]",
        "(//*[@role='button' and @aria-label='Comment'])[1]",
        "(//*[@aria-label='Comment' and (@role='button' or @role='link')])[1]",
        "(//div[@role='button' and contains(@aria-label, 'Comment')])[1]",
    ]
    comment_btn = _wait_first_xpath(
        driver, comment_xpaths, step_timeout, label="Comment button"
    )
    _log("Clicking Comment…")
    _js_click(driver, comment_btn)

    textarea_xpaths = [
        "//textarea[contains(@class,'native-input') and contains(@placeholder,'Comment')]",
        "//textarea[@role='combobox' and contains(@placeholder,'Comment')]",
        "//textarea[contains(@class,'internal-input') and contains(@class,'input-box')]",
        "//textarea[contains(@placeholder,'Comment as')]",
    ]
    _log("Waiting for comment textarea…")
    ta = _wait_first_xpath(
        driver, textarea_xpaths, step_timeout, label="Comment textarea"
    )
    _js_click(driver, ta)
    try:
        ta.clear()
    except Exception:
        pass
    ta.send_keys(comment)
    _log(f"Typed comment ({len(comment)} chars); waiting for Post…")
    time.sleep(0.5)

    post = _wait_post_comment_button(driver, step_timeout)
    _log("Clicking Post a comment…")
    _js_click(driver, post)
    _log(f"Posted on reel {index + 1}/{total}.")
    time.sleep(2)


def _pause_browser_for_debug(driver) -> None:
    _log(
        "Error path: browser left OPEN — use DevTools (F12) → Elements to inspect "
        "selectors on the current page."
    )
    _log(f"Current page: {driver.current_url!r}")
    try:
        input("Press Enter in this terminal when you are done inspecting (closes browser)… ")
    except EOFError:
        _log("Non-interactive stdin; closing browser now.")


def _discover_pkl_paths(pkl_dir: Path) -> List[Path]:
    paths = sorted(pkl_dir.glob("*.pkl"), key=lambda p: p.name.lower())
    return paths


def run(
    pkl_paths: List[Path],
    reel_url: str,
    comment: str,
    reel_count: int = 1,
    min_delay: float = 2.0,
    max_delay: float = 5.0,
    not_now_timeout: float = 6.0,
    step_timeout: float = 25.0,
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
    logger=None,
) -> None:
    if logger:
        _thread_local.logger = logger
    if reel_count < 1:
        raise ValueError("reel_count must be at least 1")
    paths = [p.resolve() for p in pkl_paths]
    if not paths:
        raise ValueError("At least one PKL path is required")
    for p in paths:
        if not p.is_file():
            raise FileNotFoundError(p)

    feed_url = _normalize_reel_feed_url(reel_url)
    _log(f"Target reel URL (raw): {reel_url!r}")
    _log(f"Normalized reel feed: {feed_url!r}")
    _log(f"PKL files ({len(paths)}): {[x.name for x in paths]}")
    _log(f"Reels per account: {reel_count}")
    _log(f"Comment text ({len(comment)} chars): {comment!r}")

    driver = None
    ok = False
    try:
        driver = _create_mobile_driver(viewport_width, viewport_height)

        for acc_i, pkl_path in enumerate(paths):
            _log(f"======== Account {acc_i + 1} / {len(paths)}: {pkl_path.name} ========")
            if acc_i > 0:
                _clear_facebook_site_data(driver)

            data = _load_session(pkl_path)
            _print_pkl_summary(data)
            _restore_facebook_session(driver, data)

            if not _is_logged_in(driver):
                _log(f"SKIP Account: {pkl_path.name} is not logged in or is locked.")
                continue

            _log(f"Opening reel URL: {feed_url!r}")
            driver.get(feed_url)
            time.sleep(2)
            _log(f"After reel load: url={driver.current_url!r} title={driver.title!r}")

            # Increase height by 10% after load to ensure comment section visibility
            try:
                _log("Boosting window height by 10% for improved visibility…")
                window_size = driver.get_window_size()
                driver.set_window_size(window_size['width'], int(window_size['height'] * 1.1))
                time.sleep(0.5)
            except Exception as e:
                _log(f"Dynamic resize failed: {e}")

            try:
                for i in range(reel_count):
                    _comment_on_current_reel(
                        driver,
                        comment,
                        step_timeout,
                        not_now_timeout,
                        index=i,
                        total=reel_count,
                    )
                    if i + 1 < reel_count:
                        _log("Moving to next reel (scroll nudge + reload feed)…")
                        _scroll_feed_try_next_reel(driver)
                        _go_to_fresh_reel_feed(driver, feed_url)

                        # Random delay between reels
                        delay = random.uniform(min_delay, max_delay)
                        _log(f"Random delay: waiting {delay:.2f}s...")
                        time.sleep(delay)
            except Exception as e:
                _log(f"Error processing reels for account {pkl_path.name}: {e}")
                _log("Will attempt to move to next account...")
                continue

        ok = True
    except Exception:
        if driver is not None:
            try:
                _log(f"Exception — url={driver.current_url!r} title={driver.title!r}")
            except Exception:
                _log("Exception — could not read driver URL/title")
        raise
    finally:
        if driver is not None:
            if ok:
                driver.quit()
                _log("Browser closed.")
            else:
                try:
                    _pause_browser_for_debug(driver)
                finally:
                    driver.quit()
                    _log("Browser closed after debug pause.")


def main():
    ap = argparse.ArgumentParser(
        description="Facebook Reels: restore PKL session(s) and post comments. "
        "With no --pkl, all *.pkl in --pkl-dir run in one browser (switch account between files)."
    )
    ap.add_argument(
        "--pkl",
        type=Path,
        action="append",
        default=None,
        help="PKL file from pklgenerator.py (repeat for several; omit to use every *.pkl in --pkl-dir)",
    )
    ap.add_argument(
        "--pkl-dir",
        type=Path,
        default=_script_dir() / "pklfiles",
        help="Folder scanned for *.pkl when --pkl is not passed (sorted by filename)",
    )
    ap.add_argument(
        "--url",
        default="https://www.facebook.com/reel/",
        help="Reel feed URL (default reloads this between comments for a new clip)",
    )
    ap.add_argument(
        "--comment",
        default=None,
        help="Comment text (omit to be prompted)",
    )
    ap.add_argument(
        "--reels",
        type=int,
        default=None,
        help="How many reels to comment on (omit to be prompted)",
    )
    ap.add_argument(
        "--width",
        type=int,
        default=DEFAULT_VIEWPORT_WIDTH,
        help="Mobile viewport width (device metrics)",
    )
    ap.add_argument(
        "--height",
        type=int,
        default=DEFAULT_VIEWPORT_HEIGHT,
        help="Mobile viewport height (default 1000)",
    )
    ap.add_argument(
        "--min-delay",
        type=float,
        default=2.0,
        help="Minimum random delay between reels (seconds)",
    )
    ap.add_argument(
        "--max-delay",
        type=float,
        default=5.0,
        help="Maximum random delay between reels (seconds)",
    )
    args = ap.parse_args()

    if args.pkl:
        pkl_paths = [Path(p).resolve() for p in args.pkl]
        for p in pkl_paths:
            if not p.is_file():
                raise SystemExit(f"PKL not found: {p}")
    else:
        pkl_dir = args.pkl_dir.resolve()
        if not pkl_dir.is_dir():
            raise SystemExit(f"PKL directory not found: {pkl_dir}")
        pkl_paths = _discover_pkl_paths(pkl_dir)
        if not pkl_paths:
            raise SystemExit(f"No .pkl files in {pkl_dir}")

    reel_count = args.reels
    if reel_count is None:
        while True:
            raw = input("How many reels do you want to comment on? ").strip()
            try:
                reel_count = int(raw)
                if reel_count >= 1:
                    break
                print("Please enter a positive integer (1 or more).")
            except ValueError:
                print("Invalid number.")

    comment_text = args.comment
    if comment_text is None:
        comment_text = input("What comment do you want to post? ").strip()
    if not comment_text:
        raise SystemExit("Comment text cannot be empty.")

    run(
        pkl_paths,
        args.url,
        comment_text,
        reel_count=reel_count,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        viewport_width=args.width,
        viewport_height=args.height,
    )


if __name__ == "__main__":
    main()
