#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Soundwave"
APP_ID="io.github.manuelprz.soundwave"
BUILD_DIR="$(pwd)/build-appimage"
APPDIR="${BUILD_DIR}/AppDir"

rm -rf "${BUILD_DIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/lib" "${APPDIR}/usr/share/applications" "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# 1. Descargar linuxdeploy
wget -q -O "${BUILD_DIR}/linuxdeploy" \
  "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage"
chmod +x "${BUILD_DIR}/linuxdeploy"

# 2. Copiar tu código fuente y venv
cp -r src/soundwave "${APPDIR}/usr/bin/soundwave"
python3 -m venv "${APPDIR}/usr/python"
"${APPDIR}/usr/python/bin/pip" install mutagen pydbus dbus-python PyGObject requests --no-cache-dir

# 3. Desktop file e ícono (requeridos por linuxdeploy)
cat > "${APPDIR}/usr/share/applications/${APP_ID}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
Exec=soundwave
Icon=${APP_ID}
Categories=Audio;Music;Player;
EOF

cp data/icons/icono-light-256.png \
  "${APPDIR}/usr/share/icons/hicolor/256x256/apps/${APP_ID}.png"

# 4. AppRun: arranca el venv y carga las libs empaquetadas
cat > "${APPDIR}/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH:-}"
export GI_TYPELIB_PATH="${HERE}/usr/lib/girepository-1.0"
export PYTHONPATH="${HERE}/usr/bin:${PYTHONPATH:-}"

# Forzar GDK_BACKEND=x11 en entornos Wayland no-GNOME para evitar congelamientos en modales y doble decoración
if [[ "${XDG_CURRENT_DESKTOP:-}" =~ (KDE|plasma|Plasma|Hyprland|hyprland|sway|Sway|qtile|Qtile) ]] && [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    export GDK_BACKEND=x11
fi

exec "${HERE}/usr/python/bin/python3" -m soundwave "$@"
EOF
chmod +x "${APPDIR}/AppRun"

export GST_PLUGIN_PATH="${APPDIR}/usr/lib/gstreamer-1.0"
export GST_PLUGIN_SYSTEM_PATH_1_0="${APPDIR}/usr/lib/gstreamer-1.0"

# 5. linuxdeploy detecta y empaqueta las dependencias automáticamente
export NO_STRIP=1  # evita romper símbolos de GStreamer plugins
"${BUILD_DIR}/linuxdeploy" \
  --appdir "${APPDIR}" \
  --desktop-file "${APPDIR}/usr/share/applications/${APP_ID}.desktop" \
  --icon-file "${APPDIR}/usr/share/icons/hicolor/256x256/apps/${APP_ID}.png" \
  --output appimage

echo "AppImage generado en ${BUILD_DIR}/"