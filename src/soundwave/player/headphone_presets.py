"""
Gestión de presets de audífonos importados desde AutoEQ u otras fuentes.
Se almacenan en ~/.config/soundwave/headphone_presets.json
"""
import json
import math
import os
import re
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "soundwave"
HEADPHONE_PRESETS_FILE = CONFIG_DIR / "headphone_presets.json"


def load_headphone_presets() -> dict[str, list[float]]:
    if HEADPHONE_PRESETS_FILE.exists():
        try:
            return json.loads(HEADPHONE_PRESETS_FILE.read_text())
        except Exception:
            pass
    return {}


def save_headphone_preset(name: str, bands: list[float]) -> None:
    presets = load_headphone_presets()
    presets[name] = [round(g, 2) for g in bands]
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    HEADPHONE_PRESETS_FILE.write_text(json.dumps(presets, indent=2))


def delete_headphone_preset(name: str) -> None:
    presets = load_headphone_presets()
    if name in presets:
        del presets[name]
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HEADPHONE_PRESETS_FILE.write_text(json.dumps(presets, indent=2))


def get_headphone_preset_names() -> list[str]:
    return list(load_headphone_presets().keys())


def get_headphone_preset(name: str) -> Optional[list[float]]:
    return load_headphone_presets().get(name)


# ──────────────────────────────────────────────────────────────────
# AutoEQ Parametric EQ parser
# ──────────────────────────────────────────────────────────────────

def _eval_pk(f: float, Fc: float, G: float, Q: float) -> float:
    """Gain at frequency f for a peaking bell filter."""
    if Fc <= 0 or Q <= 0:
        return 0.0
    ratio = f / Fc - Fc / f
    return G / (1.0 + (Q * ratio) ** 2)


def _eval_lsc(f: float, Fc: float, G: float, Q: float) -> float:
    """Gain at frequency f for a low-shelf filter."""
    if Fc <= 0:
        return 0.0
    slope = max(0.5, Q)
    return G / (1.0 + (f / Fc) ** (2.0 * slope))


def _eval_hsc(f: float, Fc: float, G: float, Q: float) -> float:
    """Gain at frequency f for a high-shelf filter."""
    if Fc <= 0:
        return 0.0
    slope = max(0.5, Q)
    return G / (1.0 + (Fc / f) ** (2.0 * slope))


def parse_autoeq_parametric(text: str, target_freqs: list[float]) -> tuple[list[float], float]:
    """
    Parse an AutoEQ ParametricEq.txt file and return gains at the given target
    frequencies plus the preamp gain (in dB).

    Returns: (gains_list, preamp_db)
    """
    filters = []
    preamp_db = 0.0

    for line in text.splitlines():
        line = line.strip()
        # Preamp
        m = re.match(r"Preamp\s*:\s*([-\d.]+)\s*dB", line, re.IGNORECASE)
        if m:
            preamp_db = float(m.group(1))
            continue
        # Filter  ON <type> Fc <hz> Hz Gain <db> dB Q <q>
        m = re.match(
            r"Filter\s+\d+\s*:\s*ON\s+(\w+)\s+Fc\s+([\d.]+)\s*Hz\s+Gain\s+([-\d.]+)\s*dB\s+Q\s+([\d.]+)",
            line, re.IGNORECASE
        )
        if m:
            ftype = m.group(1).upper()
            fc = float(m.group(2))
            gain = float(m.group(3))
            q = float(m.group(4))
            filters.append((ftype, fc, gain, q))

    gains = []
    for f in target_freqs:
        total = 0.0
        for ftype, fc, gain, q in filters:
            if ftype == "PK":
                total += _eval_pk(f, fc, gain, q)
            elif ftype == "LSC":
                total += _eval_lsc(f, fc, gain, q)
            elif ftype == "HSC":
                total += _eval_hsc(f, fc, gain, q)
        gains.append(round(total, 2))
    return gains, preamp_db


def import_autoeq_file(filepath: str, preset_name: str, target_freqs: list[float]) -> list[float]:
    """
    Read an AutoEQ ParametricEq.txt file, convert to graphic EQ gains at
    target_freqs, save as a headphone preset and return the gains.
    """
    text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    gains, preamp = parse_autoeq_parametric(text, target_freqs)
    # Apply preamp offset so overall loudness stays neutral
    gains = [round(g + preamp, 2) for g in gains]
    save_headphone_preset(preset_name, gains)
    return gains
