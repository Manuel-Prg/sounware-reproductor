BAND_FREQUENCIES = [
    ("31 Hz", 31),
    ("62 Hz", 62),
    ("125 Hz", 125),
    ("250 Hz", 250),
    ("500 Hz", 500),
    ("1 kHz", 1000),
    ("2 kHz", 2000),
    ("4 kHz", 4000),
    ("8 kHz", 8000),
    ("16 kHz", 16000),
]

PRESETS: dict[str, list[float]] = {
    "Plano": [0.0] * 10,
    "Clásica": [4.0, 2.0, 0.0, -1.0, -1.0, 1.0, 2.0, 3.0, 4.0, 5.0],
    "Club": [2.0, 2.0, 4.0, 4.0, 4.0, 2.0, 0.0, 0.0, 0.0, 0.0],
    "Dance": [6.0, 4.0, 0.0, -2.0, 0.0, 2.0, 4.0, 4.0, 4.0, 4.0],
    "Bajo": [6.0, 4.0, -2.0, -4.0, -2.0, 0.0, 2.0, 4.0, 4.0, 4.0],
    "Jazz": [3.0, 2.0, 0.0, 2.0, 3.0, 3.0, 2.0, 1.0, 2.0, 3.0],
    "Metal": [4.0, 2.0, -2.0, -4.0, -2.0, 0.0, 2.0, 4.0, 4.0, 4.0],
    "Pop": [-2.0, 0.0, 2.0, 4.0, 4.0, 2.0, 0.0, -1.0, -1.0, -1.0],
    "Rock": [4.0, 2.0, -4.0, -4.0, -2.0, 2.0, 4.0, 4.0, 4.0, 4.0],
    "Voz": [-2.0, -2.0, -2.0, -1.0, 2.0, 4.0, 4.0, 2.0, 0.0, -2.0],
}


def get_preset_names() -> list[str]:
    return list(PRESETS.keys())


def get_preset(name: str) -> list[float]:
    return PRESETS.get(name, [0.0] * 10)


def apply_preset(bands: list[float], preset_name: str) -> list[float]:
    preset = get_preset(preset_name)
    return list(preset) if preset else bands


GAIN_MIN = -24.0
GAIN_MAX = 12.0
GAIN_STEP = 0.5


def clamp_gain(value: float) -> float:
    return max(GAIN_MIN, min(GAIN_MAX, value))
