"""Give each GitHub build a higher version number, so Android installs it over the previous one.

Usage:  python android-build/patch_gradle.py android/app/build.gradle <build-number>
"""
import re
import sys
from pathlib import Path

path, build = Path(sys.argv[1]), int(sys.argv[2])
src = path.read_text()
out, n1 = re.subn(r"(versionCode\s*=?\s*)\d+", rf"\g<1>{build}", src, count=1)
out, n2 = re.subn(r'(versionName\s*=?\s*)"[^"]*"', rf'\g<1>"1.{build}"', out, count=1)
if not (n1 and n2):
    sys.exit(f"could not find versionCode/versionName in {path}")
path.write_text(out)
print(f"versionCode {build}, versionName 1.{build}")
