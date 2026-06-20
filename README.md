# Soundwave 🎵

Un reproductor de música moderno, elegante y de alto rendimiento para Linux, diseñado con **GTK 4** y **Libadw**.

Ofrece una interfaz responsiva tipo dashboard, letras sincronizadas, un ecualizador integrado y un visualizador de espectro de audio dinámico con múltiples modos de visualización.

---

## ✨ Características Principales

*   **Discografía Premium en Grid**: Organización visual moderna de álbumes y artistas con ordenamiento secuencial (por disco y número de pista) y normalización inteligente de colaboraciones (e.g. `Artista feat. Colaborador` agrupado bajo `Artista`).
*   **Visualizador de Espectro Dinámico**:
    *   Soporte para 4 modos de visualización avanzados en tiempo real usando **Cairo**:
        *   **Rounded Bars**: Barras clásicas con bordes redondeados.
        *   **Continuous Wave**: Onda suave con gradiente y silueta superior.
        *   **Digital LED Blocks**: Bloques segmentados estilo retro LED.
        *   **Radial / Circular**: Espectro circular que rodea el arte del disco y pulsa al ritmo de la música.
    *   *Fallback* robusto para entornos donde no esté disponible `python3-gi-cairo`, mostrando un espectro puro de GTK4 con modos bottom-up, top-down y center-out.
    *   Cambio de modo interactivo con un simple clic sobre el fondo del visualizador.
*   **Letras Sincronizadas**: Panel de visualización de letras alineado simétricamente en el centro con auto-scroll activo.
*   **Ecualizador Multibanda**: Ajuste fino de frecuencias de audio directamente integrado.
*   **Sistema de Plugins**: Capacidad de expandir las funcionalidades del reproductor de manera modular.
*   **Diseño Centrado y Proporcionado**: Interfaz en vidrio pulido (*glassmorphism*) con barra de controles de reproducción perfectamente simétrica usando `Gtk.CenterBox`.

---

## 🛠 Requisitos de Instalación

Asegúrate de contar con las siguientes dependencias del sistema instaladas en tu distribución Linux (instrucciones para Ubuntu/Debian):

```bash
# Dependencias del sistema necesarias para GTK4, PyGObject, GStreamer y soporte de Cairo
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 \
                 gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
                 gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
                 gstreamer1.0-libav
```

---

## 🚀 Cómo Empezar

El proyecto incluye un script listo para configurar el entorno virtual de Python y arrancar la aplicación de forma automática:

1.  Dale permisos de ejecución al script lanzador:
    ```bash
    chmod +x ejecutar.sh
    ```
2.  Inicia la aplicación:
    ```bash
    ./ejecutar.sh
    ```

El script configurará automáticamente el `PYTHONPATH` necesario y utilizará el entorno virtual `.venv` para ejecutar el módulo `soundwave`.

---

## ⌨️ Atajos de Teclado

| Acción | Atajo |
| :--- | :--- |
| **Reproducir / Pausar** | `Espacio` |
| **Siguiente canción** | `Ctrl + Flecha Derecha` |
| **Canción anterior** | `Ctrl + Flecha Izquierda` |
| **Enfocar barra de búsqueda** | `Ctrl + F` |
| **Limpiar búsqueda** | `Escape` |
| **Mostrar ecualizador** | `Ctrl + E` |
| **Colapsar/Expandir barra lateral** | `Ctrl + B` |
| **Mini Reproductor** | `Ctrl + M` |
| **Pantalla completa** | `F11` |

---

## 🧪 Pruebas Unitarias

El proyecto cuenta con una batería de pruebas automatizadas para validar el comportamiento del reproductor y sus módulos core:

```bash
.venv/bin/python -m unittest discover tests
```
