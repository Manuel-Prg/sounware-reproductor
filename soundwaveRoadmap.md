# Soundwave — Roadmap de features

## Lo que ya funciona

- Reproducción con controles (play/pause, anterior, siguiente)
- Barra de progreso con tiempo
- Sidebar: Todas las canciones / Álbumes / Artistas / Géneros
- Vista de álbumes con carátulas
- Lista de canciones con metadatos
- Control de volumen
- Búsqueda integrada
- Shuffle y repeat (base)
- Cola de reproducción
- Ecualizador de 10 bandas (backend, sin UI)
- MPRIS2 con señal `Seeked`, `Raise`, y `mpris:artUrl` ✅ (fixes aplicados)

---

## Nivel 1 — Core incompleto (implementar ya)

Estas son las cosas rotas o incompletas que cualquier usuario nota al primer uso.

### Scanner de metadatos

- **Problema:** muchos archivos muestran "Artista desconocido" porque `mutagen` no está leyendo bien los tags `TPE1`, `ALBUMARTIST`, `TPE2`.
- **Fix:** priorizar tags en orden: `TPE2` → `TPE1` → `ALBUMARTIST` → fallback a nombre de carpeta.
- **Archivos:** `library/scanner.py`, `library/db.py`

### Export de carátulas a `/tmp`

- **Problema:** MPRIS no muestra portada en GNOME Shell porque `mpris:artUrl` apunta a `/tmp/soundwave_art/<id>.jpg` pero el scanner nunca las exporta.
- **Fix:** al escanear, extraer imagen embebida con `mutagen` y guardarla en `/tmp/soundwave_art/`.
- **Archivos:** `library/scanner.py`, `player/mpris.py`

### Shuffle real (Fisher-Yates)

- **Problema:** `toggle_shuffle()` activa la bandera pero el queue no se reordena — next() sigue siendo secuencial.
- **Fix:** al activar shuffle, generar un índice aleatorio con Fisher-Yates sobre el queue restante.
- **Archivos:** `player/engine.py`

### ReplayGain

- **Por qué:** sin normalización, pasar de una pista a otra produce saltos de volumen bruscos.
- **Implementación:** elemento `rgvolume` en el pipeline GStreamer; leer tags `REPLAYGAIN_TRACK_GAIN` con mutagen.
- **Archivos:** `player/engine.py`

### Watcher de carpeta (inotify)

- **Por qué:** si el usuario agrega archivos a su carpeta de música, la biblioteca no se actualiza hasta reiniciar.
- **Implementación:** `watchdog` o `inotify_simple` en un hilo separado que dispara rescan parcial.
- **Archivos:** `library/scanner.py`

---

## Nivel 2 — Experiencia (diferenciadores frente a Amberol)

Lo que hace que Soundwave valga la pena sobre las alternativas existentes.

### Ecualizador con UI

- 10 bandas con sliders en un panel desplegable `Adw.BottomSheet` o ventana modal.
- Presets: Flat, Bass boost, Vocal, Rock, Electronic.
- El backend ya existe en `engine.py` (`_build_equalizer_pipeline`), solo falta conectarlo a la UI.
- **Archivos:** `ui/equalizer_panel.py`, `player/engine.py`

### Crossfade / gapless playback

- La queja más frecuente en foros de Linux sobre reproductores.
- GStreamer soporta gapless con `about-to-finish` signal en `playbin`; crossfade requiere dos pipelines con `adder`.
- Empezar con gapless (más simple), luego crossfade configurable (0–10 seg).
- **Archivos:** `player/engine.py`

### Letras sincronizadas (.lrc)

- Buscar archivo `.lrc` con mismo nombre junto al audio.
- Fallback: consultar LRCLIB API (gratuita, sin key).
- Mostrar en un panel lateral o superpuesto a la carátula.
- **Archivos:** `ui/lyrics_view.py`, nuevo módulo `library/lyrics.py`

### Smart playlists

- Playlists generadas automáticamente por reglas: género = "Jazz", año > 2010, plays > 5, etc.
- Almacenar reglas en SQLite, ejecutar como query dinámica.
- **Archivos:** `library/db.py`, `ui/playlist_editor.py`

### Last.fm scrobbling

- `pylast` para autenticación OAuth y submit de scrobbles.
- Hacer submit a los 50% de reproducción o 4 minutos (regla oficial Last.fm).
- **Archivos:** nuevo módulo `services/lastfm.py`

### BPM detection

- `aubio` es la opción más ligera para detección offline.
- Correr en hilo de fondo durante el escaneo inicial; guardar en la tabla `songs`.
- Útil para smart playlists y futuro modo DJ.
- **Archivos:** `library/scanner.py`

### MusicBrainz lookup

- Completar tags faltantes (artista, álbum, año, género) consultando MusicBrainz por huella acústica con `acoustid`.
- Solo se ejecuta bajo petición explícita del usuario, nunca automáticamente.
- **Archivos:** nuevo módulo `services/musicbrainz.py`

### Drag and drop

- Arrastrar archivos/carpetas desde el file manager para importarlos.
- GTK4: `Gtk.DropTarget` con tipos `GFile`.
- **Archivos:** `ui/window.py`

### Mini-player

- Ventana compacta (400×80px) que muestra carátula + controles + título.
- Se activa desde el menú o con un atajo de teclado.
- Útil cuando Soundwave está en segundo plano.
- **Archivos:** `ui/mini_player.py`

---

## Nivel 3 — Avanzado (cuando el core sea sólido)

Features que añaden profundidad pero no son bloqueantes.

### Visualizador de audio

- Elemento `spectrum` de GStreamer alimentando un `Gtk.DrawingArea` dibujado con Cairo.
- Alternativa más simple: barras de nivel con el elemento `level`.
- **Archivos:** `ui/visualizer.py`

### Waveform display

- Prerenderizar la forma de onda del archivo al escanear (con `audiowaveform` o Cairo manual).
- Mostrar en la barra de progreso en lugar de una línea plana.
- **Archivos:** `ui/player_bar.py`, `library/scanner.py`

### Podcasts / RSS

- Suscripciones via `feedparser`.
- Guardar episodios descargados en una carpeta configurable.
- Posición guardada por episodio (bookmark).
- **Archivos:** nuevo módulo `services/podcasts.py`

### Sistema de plugins

- Directorio `~/.local/share/soundwave/plugins/` con módulos Python cargados dinámicamente.
- API mínima: `on_song_changed(song)`, `on_state_changed(state)`.
- Permite que terceros agreguen scrobblers, notificadores, integraciones, sin tocar el core.
- **Archivos:** nuevo módulo `core/plugin_manager.py`

### Sync multi-device

- Sincronizar biblioteca (no archivos) vía Syncthing o WebDAV.
- Solo metadatos, plays, playlists — no el audio en sí.
- **Archivos:** nuevo módulo `services/sync.py`

### Flatpak + Flathub

- Manifiesto `io.github.<tuusuario>.soundwave.yml` con módulos GStreamer y Python.
- Publicar en Flathub una vez el core esté estable.
- **Archivos:** `flatpak/io.github.<tuusuario>.soundwave.yml`

---

## Ventajas actuales de Soundwave sobre Amberol

| Feature              | Soundwave          | Amberol |
| -------------------- | ------------------ | ------- |
| Ecualizador          | ✅ (backend listo) | ❌      |
| Vista por géneros    | ✅                 | ❌      |
| Búsqueda integrada   | ✅                 | ❌      |
| Cola de reproducción | ✅                 | ❌      |
| Shuffle / repeat     | ✅                 | ✅      |
| MPRIS2 completo      | ✅                 | ✅      |
| Gapless playback     | ❌ pendiente       | ✅      |
| Carátulas embebidas  | ⚠️ parcial         | ✅      |

---

## Orden de ataque recomendado

1. Scanner de metadatos + export de carátulas (van juntos, 1-2 días)
2. Shuffle real (30 minutos, está casi hecho)
3. Ecualizador UI (el backend ya existe, solo falta el panel)
4. Crossfade / gapless (diferenciador clave)
5. MusicBrainz lookup (resuelve "Artista desconocido" en casos que mutagen no puede)
6. Letras sincronizadas (feature muy pedida en la comunidad)
