#!/bin/bash
# Obtener el directorio absoluto donde reside este script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 1. Validar dependencias del sistema
if ! python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1'); gi.require_version('Gst', '1.0'); import dbus" &>/dev/null; then
    echo " Error: Faltan dependencias del sistema o bindings de Python (GTK4, Libadwaita, GStreamer, PyGObject o DBus)."
    echo "Por favor, instala las dependencias necesarias para tu distribución:"
    echo ""
    echo "En Fedora Linux:"
    echo "  sudo dnf install python3-gobject python3-cairo python3-dbus gtk4 libadwaita \\"
    echo "                   gstreamer1-plugins-base gstreamer1-plugins-good \\"
    echo "                   gstreamer1-plugins-bad-free gstreamer1-plugins-ugly-free"
    echo ""
    echo "En Ubuntu/Debian:"
    echo "  sudo apt install python3-gi python3-gi-cairo python3-dbus gir1.2-gtk-4.0 gir1.2-adw-1 \\"
    echo "                   gstreamer1.0-plugins-base gstreamer1.0-plugins-good \\"
    echo "                   gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \\"
    echo "                   gstreamer1.0-libav"
    echo ""
    exit 1
fi

# 2. Configurar entorno virtual si no existe
if [ ! -d "$DIR/.venv" ]; then
    echo " Configurando el entorno virtual (.venv)..."
    python3 -m venv --system-site-packages "$DIR/.venv"
    if [ $? -ne 0 ]; then
        echo " Error al crear el entorno virtual."
        exit 1
    fi
    echo " Instalando dependencias de Python (mutagen, requests)..."
    "$DIR/.venv/bin/pip" install --upgrade pip
    "$DIR/.venv/bin/pip" install mutagen requests
fi

# 3. Detectar KDE Plasma, Hyprland, Sway o Qtile en Wayland para forzar GDK_BACKEND=x11 (evita doble decoración y clics congelados)
if [[ "$XDG_CURRENT_DESKTOP" =~ (KDE|plasma|Plasma|Hyprland|hyprland|sway|Sway|qtile|Qtile) ]] && [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    echo " Detectado $XDG_CURRENT_DESKTOP en Wayland. Forzando GDK_BACKEND=x11 para evitar problemas de clics en ventanas modales."
    export GDK_BACKEND=x11
fi

# 4. Ejecutar usando el intérprete de python del entorno virtual y configurando PYTHONPATH
PYTHONPATH="$DIR/src" "$DIR/.venv/bin/python" -m soundwave "$@"
