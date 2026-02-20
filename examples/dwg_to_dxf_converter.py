"""
Requires the external ODA File Converter binary.
On macOS the default install path is:
    /Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter
If you install it elsewhere, update `ODA_EXECUTABLE` below.
"""

from pathlib import Path
import sys

import ezdxf
from ezdxf.addons import odafc

ODA_EXECUTABLE = Path(
    "/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"
)

def ensure_oda_available() -> None:
    if ODA_EXECUTABLE.is_file():
        ezdxf.options.set("odafc-addon", "unix_exec_path", str(ODA_EXECUTABLE))
        return

    raise FileNotFoundError(
        f"ODA File Converter not found at {ODA_EXECUTABLE}.\n"
        "Install it from https://www.opendesign.com/guestfiles/oda_file_converter\n"
        "or adjust ODA_EXECUTABLE to the correct path."
    )


def convert(dwg_path: Path, dxf_path: Path) -> None:
    ensure_oda_available()

    doc = odafc.readfile(str(dwg_path))
    print(f"Loaded '{dwg_path.name}' as DXF version: {doc.dxfversion}")

    doc.saveas(str(dxf_path))
    print(f"Saved DXF to: {dxf_path}")


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        dwg_path = Path(sys.argv[1])
    else:
        user_input = input("Enter DWG file name (or path): ").strip()
        dwg_path = Path(user_input)

    if not dwg_path.exists():
        sys.exit(f"DWG file not found: {dwg_path}")       
    dxf_path = dwg_path.with_suffix(".dxf")

    convert(dwg_path, dxf_path)

