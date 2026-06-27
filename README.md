# Soundwave 🎵

Un reproductor de música moderno, elegante y de alto rendimiento para Linux, diseñado con **GTK 4** y **Libadwaita**.

Soundwave ofrece una interfaz responsiva tipo dashboard en vidrio pulido (_glassmorphism_), letras sincronizadas en tiempo real, un motor de ecualización avanzado, un visualizador de espectro dinámico basado en Cairo y un robusto sistema de reproducción sin pausas (_gapless_) con soporte para transiciones cruzadas (_crossfade_).

---

## ✨ Características Destacadas

### 🎨 Diseño y Experiencia de Usuario Premium

- **Glassmorphism Interactivo**: Interfaz moderna y semi-translúcida que responde fluidamente a las interacciones del usuario.
- **Barra de Controles Perfectamente Simétrica**: Diseñada con `Gtk.CenterBox` para lograr la distribución óptima de los controles.
- **Mini Reproductor Compacto (`Ctrl + M`)**: Ventana ultra-compacta con controles esenciales y carátula para ocupar el mínimo espacio en tu escritorio.

### 📊 Visualizador de Espectro de Audio y Forma de Onda

- **4 Modos del Espectro con Cairo**:
  - _Rounded Bars_: Barras de espectro clásicas con bordes redondeados.
  - _Continuous Wave_: Onda suave con silueta superior y gradientes de color.
  - _Digital LED Blocks_: Bloques segmentados estilo ecualizador LED retro.
  - _Radial / Circular_: Espectro circular que envuelve el arte del disco y pulsa al ritmo de la música.
- **Waveform Progress Bar**: Prerenderiza la forma de onda de cada pista en la barra de progreso para buscar y visualizar la intensidad del sonido.
- **Fallback Inteligente**: Modo alternativo basado en widgets GTK nativos si no está disponible la biblioteca de dibujo Cairo.

### 🎚️ Ecualizador y Perfiles AutoEQ

- **Bandas Dinámicas**: Soporte para ecualizador.
- **Gestión de Presets Estables**: Almacenamiento local de ajustes preestablecidos y de auriculares (presets de audífonos).
- **Importación AutoEQ**: Capacidad de importar perfiles AutoEQ para calibrar tus audífonos favoritos.

### 🎧 Audio Engine de Nivel Superior (GStreamer)

- **Gapless Playback**: Reproducción continua y fluida de pistas consecutivas sin silencios intermedios.
- **Crossfade Configurable**: Transición gradual entre canciones para un flujo musical ininterrumpido.
- **ReplayGain**: Normalización automática del volumen para prevenir picos molestos de ganancia.

### 📂 Organización e Integraciones

- **Cola de Reproducción Avanzada**:
  - Permite añadir canciones para reproducir a continuación o al final.
  - Soporte de reordenación interactiva mediante drag-and-drop con handles dedicados.
- **Organización Inteligente**: Normalización inteligente de artistas colaboradores (e.g. agrupando colaboraciones sin duplicar artistas) y ordenamiento por disco/pista.
- **Letras Sincronizadas (.lrc)**: Auto-scroll activo con letras locales o descargadas de forma automática desde la API de LRCLIB.
- **Sincronización WebDAV**: Respaldo y sincronización de metadatos, playlists y estadísticas entre múltiples dispositivos.
- **Escáner Automático con Watcher**: Vigilancia activa de la biblioteca en segundo plano usando `inotify` (`watchdog`), actualizando las listas al instante cuando añades música.
- **Last.fm Scrobbler Asíncrono**: Registro de reproducciones y estado "now playing" totalmente asíncrono y en segundo plano para evitar bloqueos en la interfaz.
- **Soporte Completo MPRIS2**: Controla el reproductor desde tu entorno de escritorio (GNOME Shell, KDE Plasma, etc.) con soporte para carátulas locales, controles multimedia y señal `Seeked`.

---

## 🛠 Requisitos de Instalación

Asegúrate de contar con las siguientes dependencias del sistema instaladas en tu distribución Linux:

### Ubuntu / Debian / Linux Mint:

```bash
# Dependencias necesarias para GTK4, PyGObject, GStreamer, Cairo y DBus
sudo apt install python3-gi python3-gi-cairo python3-dbus gir1.2-gtk-4.0 gir1.2-adw-1 \
                 gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
                 gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
                 gstreamer1.0-libav
```

### Fedora Linux:

```bash
# Dependencias necesarias para GTK4, PyGObject, GStreamer, Cairo y DBus
sudo dnf install python3-gobject python3-cairo python3-dbus gtk4 libadwaita \
                 gstreamer1-plugins-base gstreamer1-plugins-good \
                 gstreamer1-plugins-bad-free gstreamer1-plugins-ugly-free
```

> [!NOTE]
> Para reproducir formatos con patentes propietarias (como MP3 o AAC) en Fedora, habilita los repositorios [RPM Fusion](https://rpmfusion.org/) e instala:
>
> ```bash
> sudo dnf install gstreamer1-plugins-bad-freeworld gstreamer1-plugins-ugly gstreamer1-libav
> ```

---

## 🚀 Cómo Empezar

El proyecto incluye un script de automatización (`ejecutar.sh`) que configura el entorno virtual, instala las dependencias de Python y lanza el reproductor.

1. Otorgue permisos de ejecución al script:
   ```bash
   chmod +x ejecutar.sh
   ```
2. Ejecute el script para iniciar la aplicación:
   ```bash
   ./ejecutar.sh
   ```

El lanzador se encargará de comprobar que tu entorno cuente con las dependencias del sistema y de sincronizar las librerías necesarias de Python.

---

## ⌨️ Atajos de Teclado

Diseñado para ser manejado rápidamente mediante el teclado:

| Acción                              | Atajo                     |
| :---------------------------------- | :------------------------ |
| **Reproducir / Pausar**             | `Espacio`                 |
| **Siguiente canción**               | `Ctrl + Flecha Derecha`   |
| **Canción anterior**                | `Ctrl + Flecha Izquierda` |
| **Enfocar barra de búsqueda**       | `Ctrl + F`                |
| **Limpiar búsqueda**                | `Escape`                  |
| **Mostrar ecualizador**             | `Ctrl + E`                |
| **Colapsar/Expandir barra lateral** | `Ctrl + B`                |
| **Mini Reproductor**                | `Ctrl + M`                |
| **Pantalla completa**               | `F11`                     |

---

## 🧪 Pruebas Unitarias

Para ejecutar el set de pruebas automatizadas y asegurar que todo funcione correctamente:

```bash
.venv/bin/python -m unittest discover -s tests
```

---

## 📦 Empaquetado

Para construir un ejecutable portable independiente del sistema, se incluye soporte para construir paquetes **AppImage**:

```bash
./build-appimage.sh
```

---

## 📄 Licencia

Este proyecto está bajo la Licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.
