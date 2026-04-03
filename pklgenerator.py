import os
import pickle
import re
import shutil
import subprocess
import sys
from pathlib import Path

import undetected_chromedriver as uc


def _chrome_major_version():
    """Major Chrome version for matching ChromeDriver (fixes 146 vs 147 mismatch)."""
    if sys.platform == "win32":
        try:
            import winreg

            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    key = winreg.OpenKey(root, r"Software\Google\Chrome\BLBeacon")
                    version, _ = winreg.QueryValueEx(key, "version")
                    winreg.CloseKey(key)
                    return int(version.split(".")[0])
                except OSError:
                    continue
        except ImportError:
            pass
        for exe in (
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ):
            if Path(exe).is_file():
                try:
                    out = subprocess.check_output(
                        [exe, "--version"], text=True, timeout=10
                    )
                    m = re.search(r"(\d+)\.", out)
                    if m:
                        return int(m.group(1))
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    pass
    return None


def _prepare_undetected_chromedriver_cache():
    """
    On Windows, uc's patcher renames a fresh chromedriver.exe onto a fixed path.
    If that file already exists, os.rename fails with WinError 183.
    """
    if sys.platform != "win32":
        return
    base = Path(os.environ.get("APPDATA", "")) / "undetected_chromedriver"
    if not base.is_dir():
        return
    target = base / "undetected_chromedriver.exe"
    if target.is_file():
        try:
            target.unlink()
        except OSError:
            pass
    staging = base / "undetected"
    if staging.is_dir():
        shutil.rmtree(staging, ignore_errors=True)


def _mobile_emulation_params(chrome_major=None):
    """Typical phone size + UA for mobile layout (testing / responsive use)."""
    width, height, dpr = 390, 844, 3
    ver = f"{chrome_major}.0.0.0" if chrome_major else "120.0.0.0"
    ua = (
        f"Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{ver} Mobile Safari/537.36"
    )
    return width, height, dpr, ua


def _apply_mobile_emulation(driver, width, height, dpr, user_agent):
    driver.set_window_size(width, height)
    driver.execute_cdp_cmd(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": width,
            "height": height,
            "deviceScaleFactor": dpr,
            "mobile": True,
        },
    )
    try:
        driver.execute_cdp_cmd(
            "Emulation.setTouchEmulationEnabled",
            {"enabled": True, "maxTouchPoints": 5},
        )
    except Exception:
        pass
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        {
            "userAgent": user_agent,
            "acceptLanguage": "en-US,en;q=0.9",
            "platform": "Android",
        },
    )


def save_facebook_session(output_file="facebook_login_data.pkl"):
    major = _chrome_major_version()
    width, height, dpr, ua = _mobile_emulation_params(major)

    options = uc.ChromeOptions()
    options.add_argument(f"--user-agent={ua}")
    options.add_argument(f"--window-size={width},{height}")

    driver_kwargs = {"options": options}
    if major is not None:
        driver_kwargs["version_main"] = major
    _prepare_undetected_chromedriver_cache()
    driver = uc.Chrome(**driver_kwargs)
    _apply_mobile_emulation(driver, width, height, dpr, ua)

    try:
        print("Opening Facebook mobile login page...")
        driver.get("https://m.facebook.com/login")

        input("Log in manually in the opened browser, then press Enter here...")

        # Get cookies
        cookies = driver.get_cookies()

        # Get localStorage and sessionStorage
        local_storage = driver.execute_script(
            "return Object.assign({}, window.localStorage);"
        )
        session_storage = driver.execute_script(
            "return Object.assign({}, window.sessionStorage);"
        )

        data = {
            "url": driver.current_url,
            "cookies": cookies,
            "local_storage": local_storage,
            "session_storage": session_storage,
        }

        output_path = Path(output_file)
        with output_path.open("wb") as f:
            pickle.dump(data, f)

        print(f"Login data saved to: {output_path.resolve()}")

    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    save_facebook_session()