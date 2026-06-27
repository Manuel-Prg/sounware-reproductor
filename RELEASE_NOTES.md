# Notas del Parche — Soundwave v1.0.0 🚀

¡Bienvenido a la primera versión de producción oficial de **Soundwave**! Esta versión 1.0.0 establece una base sólida para ofrecer el mejor reproductor de música nativo de Linux diseñado con GTK4 y Libadwaita.

Esta release reúne todas las características principales de reproducción, ecualización, visualización, y estabilidad solicitadas por la comunidad.

---

## 📋 Novedades Destacadas

### 🎚️ Ecualizador Dinámico y Presets

- **Soporte Multibanda**: Ahora puedes elegir entre ecualizador de 10 bandas para un control acústico profesional.
- **Persistencia de Configuración**: Presets genéricos y de auriculares guardados en archivos JSON.
- **Importación AutoEQ**: Soporte directo para importar perfiles de ecualización paramétricos.

### 📊 Espectro de Audio y Visualizador Cairo

- **Múltiples Modos de Visualización**:
  - _Rounded Bars_: Barras clásicas con esquinas suavizadas.
  - _Continuous Wave_: Silueta de onda continua con gradientes dinámicos.
  - _Digital LED Blocks_: Bloques segmentados retro estilo ecualizador de hardware.
  - _Radial / Circular_: Espectro circular que envuelve la carátula y pulsa al ritmo del beat.
- **Cambio de Modo Interactivo**: Cambia el modo del visualizador al instante haciendo un simple clic sobre el fondo.
- **Waveform Progress Bar**: Renderizado dinámico de la forma de onda del audio en la barra de progreso para una navegación intuitiva por la canción.

### 🎧 Motor de Audio Profesional

- **Gapless Playback**: Reproducción continua y libre de silencios entre canciones consecutivas.
- **Crossfade (Transición Cruzada)**: Configura transiciones suaves y graduales entre pistas directamente desde los ajustes.
- **ReplayGain**: Soporte para lectura de metadatos de ganancia para normalizar el volumen automáticamente entre diferentes álbumes.

### 🔄 Integraciones y Rendimiento Sin Bloqueos

- **Last.fm Asíncrono**: Las peticiones de registro de scrobbles y estado "reproduciendo ahora" se han trasladado a hilos en segundo plano (_daemon threads_), garantizando que las llamadas de red nunca congelen la interfaz de usuario al cambiar de canción.
- **MPRIS2 Completo**: Controla Soundwave desde los menús de tu escritorio con soporte completo para carátulas locales, controles multimedia y la señal `Seeked`.
- **Watcher en Segundo Plano**: Monitorización activa de tus carpetas de música mediante un watcher silencioso que actualiza tu biblioteca automáticamente cuando añades nuevos archivos de audio.

### 🧩 Experiencia de Usuario y Estética

- **Selección de Color de Acento**: Nuevo selector de color de acento integrado en los ajustes (Verde, Azul, Púrpura, Rojo, Naranja, Teal, Rosa y Gris).
- **Mini Reproductor (`Ctrl + M`)**: Ventana ultra-compacta con controles esenciales y carátula para ocupar el mínimo espacio en tu escritorio.
- **Normalización de Colaboradores**: Algoritmo inteligente que agrupa colaboraciones (e.g. `Artista feat. Invitado`) bajo el artista principal en lugar de crear artistas duplicados en la base de datos.
- **Sistema de Plugins Modular**: Carga dinámica de plugins en Python para extender las funcionalidades básicas del reproductor.

---

## 🔧 Corrección de Errores y Estabilidad

- **Solución al Cuelgue del Tema**: Corregido un cuelgue crítico/bloqueo de la aplicación al cambiar el tema de Oscuro a Claro. Esto ocurría debido a un bucle infinito de notificaciones en el bloqueo de propiedad de `gtk-icon-theme-name`.
- **Seguridad en Hilos de Base de Datos**: Corregidos errores SQLite `ProgrammingError` relacionados con el acceso concurrente desde los hilos del escáner en segundo plano.
- **Validación de Metadata**: Lógica mejorada en mutagen para parsear tags ID3/Vorbis mal formateados en archivos antiguos, evitando que aparezcan como "Artista desconocido".

---

## ⌨️ Atajos Útiles

- `Espacio` — Reproducir / Pausar
- `Ctrl + Flecha Derecha` — Siguiente canción
- `Ctrl + Flecha Izquierda` — Canción anterior
- `Ctrl + E` — Abrir panel del Ecualizador
- `Ctrl + M` — Alternar Mini Reproductor
- `Ctrl + B` — Mostrar/Ocultar barra lateral
- `Ctrl + F` — Buscar canciones
- `F11` — Pantalla completa

---

## 📦 Distribución y Ejecución

- **AppImage**: Se incluye un script automatizado `build-appimage.sh` para empaquetar de manera sencilla la aplicación para cualquier distribución Linux.
- **Script de Ejecución**: El script `./ejecutar.sh` ahora cuenta con comprobación inteligente de dependencias e instalación automática del entorno virtual Python.
