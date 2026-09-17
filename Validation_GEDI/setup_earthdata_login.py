"""
One-off helper: store your NASA Earthdata login so the GEDI and fire steps
can use it.

Run this once. It asks for your Earthdata username and password, writes them
to a .netrc file, and then checks that the credentials actually work against
the live service.

    C:\\ProgramData\\Anaconda3\\envs\\JinzhuLuto\\python.exe setup_earthdata_login.py

Use that full path to python rather than `conda run`, because `conda run`
buffers input and the password prompt will appear to hang.

## What this touches, and nothing else

  writes   N:\\Current-Users\\ZOHREH-KALAHROUDI\\.netrc   (one line of text)

That is the only file it creates or changes. It does not modify any script,
any data, or any system setting, and it deletes nothing. If a .netrc already
exists it asks before replacing it, and keeps a copy at .netrc.backup.

## Why a file rather than an environment variable

Each command run from the assistant starts a fresh shell, so environment
variables set in one command are gone by the next. A file on disk is read
every time, by any process, which is why this is the route that works here.

## Why the password is typed rather than pasted into chat

getpass() does not echo it, and it is written only to the .netrc. It is never
printed, logged, or sent anywhere except to NASA's login service during the
verification step at the end.
"""

from __future__ import annotations

import getpass
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

TARGET = Path(C.WORK_HOME) / ".netrc"
HOST = "urs.earthdata.nasa.gov"
TEST_URL = ("https://data.ornldaac.earthdata.nasa.gov/protected/gedi/"
            "GEDI_L4B_Gridded_Biomass_V2_1/data/"
            "GEDI04_B_MW019MW223_02_002_02_R01000M_MU.tif")


def verify(user, pw):
    """Ask the service whether these credentials really work."""
    try:
        import requests
    except ImportError:
        print("  (requests not installed - skipping the live check)")
        return None

    class S(requests.Session):
        def rebuild_auth(self, prepared_request, response):
            h = prepared_request.headers
            if "Authorization" in h:
                a = requests.utils.urlparse(response.request.url).hostname
                b = requests.utils.urlparse(prepared_request.url).hostname
                if a != b and b != HOST and a != HOST:
                    del h["Authorization"]

    s = S()
    s.auth = (user, pw)
    s.headers.update(C.UA)
    try:
        r = s.get(TEST_URL, stream=True, timeout=120, allow_redirects=True)
        ctype = (r.headers.get("Content-Type") or "").lower()
        code = r.status_code
        r.close()
    except Exception as exc:
        print("  live check could not run: %s" % type(exc).__name__)
        return None
    if code in (200, 206) and "html" not in ctype:
        return True
    if "html" in ctype or code in (401, 403):
        return False
    print("  unexpected response: HTTP %d, %s" % (code, ctype[:40]))
    return False


def main():
    print(__doc__.split("## What this touches")[0].strip())
    print("\n" + "=" * 66)
    print("This will write ONE file: %s" % TARGET)
    print("=" * 66)

    if TARGET.exists():
        ans = input("\n%s already exists. Replace it? [y/N] " % TARGET.name)
        if ans.strip().lower() not in ("y", "yes"):
            print("Left unchanged.")
            return
        shutil.copyfile(TARGET, TARGET.with_suffix(".netrc.backup"))
        print("  previous file copied to %s"
              % TARGET.with_suffix(".netrc.backup").name)

    print("\nEarthdata login  (register free at "
          "https://urs.earthdata.nasa.gov/users/new)")
    user = input("  username: ").strip()
    if not user:
        sys.exit("No username entered - nothing written.")
    pw = getpass.getpass("  password (not shown as you type): ")
    if not pw:
        sys.exit("No password entered - nothing written.")

    # ASCII and no trailing newline: PowerShell's default UTF-8 BOM makes
    # every netrc parser fail with a confusing "not found".
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text("machine %s login %s password %s\n" % (HOST, user, pw),
                      encoding="ascii")
    try:
        TARGET.chmod(0o600)
    except Exception:
        pass
    print("\nwrote %s" % TARGET)

    found_user, found_pw, src = C.earthdata_credentials()
    if not found_user:
        print("  PROBLEM: the file was written but cannot be read back.")
        print("  Searched:")
        for c in C.netrc_candidates():
            print("     %-56s %s" % (str(c)[:56],
                                     "EXISTS" if c.exists() else "-"))
        sys.exit(1)
    print("  read back OK from %s (user %s...)" % (src, found_user[:2]))

    print("\nchecking the credentials against NASA's service...")
    ok = verify(found_user, found_pw)
    if ok is True:
        print("  PASS - login works and the data licence is accepted.")
        print("\nYou are done. The GEDI and fire steps will now run.")
    elif ok is False:
        print("  FAIL - the server returned a login page instead of data.")
        print("\n  The username and password are probably fine; what is")
        print("  usually missing is the licence agreement. Log in at")
        print("  https://urs.earthdata.nasa.gov and accept the EULAs for")
        print("  LP DAAC and ORNL DAAC under Applications > Authorized Apps,")
        print("  then run this script again to re-check.")
    else:
        print("  could not verify online - the file is written; try")
        print("  Step_02_build_fire_mask.py --check")


if __name__ == "__main__":
    main()
