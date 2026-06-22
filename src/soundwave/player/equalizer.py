"""
Definición de frecuencias, presets genéricos y funciones de utilidad
para el ecualizador gráfico de Soundwave.
"""
from __future__ import annotations

# ──────────────────────────────────────────────────────────────────
# Frecuencias estándar ISO por número de bandas
# ──────────────────────────────────────────────────────────────────

BANDS_10 = [
    ("31 Hz",    31),   ("63 Hz",    63),   ("125 Hz",  125),
    ("250 Hz",  250),   ("500 Hz",  500),   ("1 kHz",  1000),
    ("2 kHz",  2000),   ("4 kHz",  4000),   ("8 kHz",  8000),
    ("16 kHz", 16000),
]

BANDS_5 = [
    ("63 Hz",    63),   ("250 Hz",  250),   ("1 kHz",  1000),
    ("4 kHz",  4000),   ("16 kHz", 16000),
]

BANDS_3 = [
    ("250 Hz",  250),   ("1 kHz",  1000),   ("4 kHz",  4000),
]

# Map n_bands → frequency table
BANDS_BY_MODE: dict[int, list[tuple[str, float]]] = {
    3:  BANDS_3,
    5:  BANDS_5,
    10: BANDS_10,
}

BAND_MODES = [3, 5, 10]

# Default (legacy) 10-band alias for engine compatibility
BAND_FREQUENCIES = BANDS_10


# ──────────────────────────────────────────────────────────────────
# Generic genre presets (10 bands, mapped up/down for other modes)
# ──────────────────────────────────────────────────────────────────

_PRESETS_10: dict[str, list[float]] = {
    "Plano":   [0.0] * 10,
    "Clásica": [4.0, 2.0, 0.0, -1.0, -1.0,  1.0,  2.0,  3.0,  4.0,  5.0],
    "Club":    [2.0, 2.0, 4.0,  4.0,  4.0,  2.0,  0.0,  0.0,  0.0,  0.0],
    "Dance":   [6.0, 4.0, 0.0, -2.0,  0.0,  2.0,  4.0,  4.0,  4.0,  4.0],
    "Bajo":    [6.0, 4.0,-2.0, -4.0, -2.0,  0.0,  2.0,  4.0,  4.0,  4.0],
    "Jazz":    [3.0, 2.0, 0.0,  2.0,  3.0,  3.0,  2.0,  1.0,  2.0,  3.0],
    "Metal":   [4.0, 2.0,-2.0, -4.0, -2.0,  0.0,  2.0,  4.0,  4.0,  4.0],
    "Pop":     [-2.0, 0.0, 2.0, 4.0,  4.0,  2.0,  0.0, -1.0, -1.0, -1.0],
    "Rock":    [4.0, 2.0,-4.0, -4.0, -2.0,  2.0,  4.0,  4.0,  4.0,  4.0],
    "Voz":     [-2.0,-2.0,-2.0,-1.0,  2.0,  4.0,  4.0,  2.0,  0.0, -2.0],
}


def _interpolate_gains(src_freqs: list[float], src_gains: list[float],
                       dst_freqs: list[float]) -> list[float]:
    """Log-linear interpolation of gains from one frequency grid to another."""
    import math
    result = []
    for f in dst_freqs:
        if f <= src_freqs[0]:
            result.append(src_gains[0])
        elif f >= src_freqs[-1]:
            result.append(src_gains[-1])
        else:
            # Find surrounding points
            for i in range(len(src_freqs) - 1):
                if src_freqs[i] <= f <= src_freqs[i + 1]:
                    # Log interpolation
                    t = (math.log(f) - math.log(src_freqs[i])) / (
                        math.log(src_freqs[i + 1]) - math.log(src_freqs[i]))
                    result.append(src_gains[i] * (1 - t) + src_gains[i + 1] * t)
                    break
    return result


def get_preset_names() -> list[str]:
    return list(_PRESETS_10.keys())


def get_preset(name: str, n_bands: int = 10) -> list[float]:
    """Return preset gains re-sampled to the requested number of bands."""
    gains_10 = list(_PRESETS_10.get(name, [0.0] * 10))
    if n_bands == 10:
        return gains_10

    src_freqs = [f for _, f in BANDS_10]
    dst_freqs = [f for _, f in BANDS_BY_MODE[n_bands]]
    return [round(g, 2) for g in _interpolate_gains(src_freqs, gains_10, dst_freqs)]


def gains_for_engine(ui_bands: list[float], n_bands: int) -> list[float]:
    """
    Convert UI gains (n_bands long) to a 10-element list suitable for
    the engine's equalizer-10bands element.
    """
    if n_bands == 10:
        return list(ui_bands)

    src_freqs = [f for _, f in BANDS_BY_MODE[n_bands]]
    dst_freqs = [f for _, f in BANDS_10]
    return [round(g, 2) for g in _interpolate_gains(src_freqs, ui_bands, dst_freqs)]


# ──────────────────────────────────────────────────────────────────
# Gain clamping
# ──────────────────────────────────────────────────────────────────

GAIN_MIN = -24.0
GAIN_MAX = 12.0
GAIN_STEP = 0.5


def clamp_gain(value: float) -> float:
    return max(GAIN_MIN, min(GAIN_MAX, value))
