#!/usr/bin/env bash
# Instala el motor Goa en una Raspberry Pi (Raspberry Pi OS Lite, 64 bits).
# Uso: desde la carpeta goa-engine, ./install.sh
# Puedes volver a correrlo cuando quieras: nunca borra tu configuración.
set -euo pipefail

CARPETA="$(cd "$(dirname "$0")" && pwd)"
USUARIO="$(id -un)"
CONFIG_DIR="$HOME/.config/goa"
CONFIG="$CONFIG_DIR/config.toml"

echo "==> Instalando dependencias"
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-mido python3-rtmidi git >/dev/null || {
  echo "    Sin paquetes del sistema; uso pip."
  sudo apt-get install -y -qq python3-pip git >/dev/null
  pip3 install --user --break-system-packages mido python-rtmidi
}
sudo usermod -aG audio "$USUARIO"

echo "==> Configuración"
mkdir -p "$CONFIG_DIR"
if [ -f "$CONFIG" ]; then
  echo "    Ya existe $CONFIG, la dejo como está."
else
  cp "$CARPETA/config.ejemplo.toml" "$CONFIG"
  echo "    Creada $CONFIG"
fi

echo "==> Servicio que arranca solo al encender"
sudo tee /etc/systemd/system/goa.service >/dev/null <<EOF
[Unit]
Description=Motor generativo Goa
After=sound.target

[Service]
User=$USUARIO
WorkingDirectory=$CARPETA
ExecStart=/usr/bin/python3 -m goa.main --config $CONFIG
Restart=always
RestartSec=2
Nice=-10
CPUSchedulingPolicy=rr
CPUSchedulingPriority=50

[Install]
WantedBy=multi-user.target
EOF

echo "==> Comandos goa-*"
crear() { sudo tee "/usr/local/bin/$1" >/dev/null; sudo chmod +x "/usr/local/bin/$1"; }

crear goa-ports <<EOF
#!/usr/bin/env bash
cd "$CARPETA" && exec python3 -m goa.puertos "\$@"
EOF

crear goa-log <<'EOF'
#!/usr/bin/env bash
exec journalctl -u goa -f -n 50
EOF

crear goa-restart <<'EOF'
#!/usr/bin/env bash
sudo systemctl restart goa && echo "Motor reiniciado."
EOF

crear goa-debug <<EOF
#!/usr/bin/env bash
# Corre el motor a mano mostrando cada nota (detiene el servicio mientras tanto).
sudo systemctl stop goa
cd "$CARPETA" && python3 -m goa.main --config "$CONFIG" --debug
sudo systemctl start goa
EOF

crear goa-update <<EOF
#!/usr/bin/env bash
set -e
cd "$CARPETA"
if [ ! -d .git ]; then
  echo "Esta instalación no viene de GitHub."
  echo "Para actualizar: reemplaza la carpeta $CARPETA por la nueva versión y corre goa-restart."
  exit 1
fi
version() { python3 -c "import goa; print(goa.__version__)"; }
if [ "\${1:-}" = "--anterior" ]; then
  git rev-parse -q --verify HEAD^ >/dev/null || { echo "No hay versión anterior."; exit 1; }
  git checkout -q HEAD^
  echo "Volviste a la versión \$(version). Para volver a la última: goa-update"
else
  git checkout -q main && git pull -q
  echo "Actualizado a la versión \$(version)."
fi
sudo systemctl restart goa
echo "Motor reiniciado."
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now goa
sudo systemctl restart goa

echo
echo "Listo. App en el celular (misma red Wi-Fi): http://goa.local:8080"
echo
echo "Comandos:"
echo "  goa-ports                    lista los puertos MIDI"
echo "  goa-ports --probar FM-1 2    toca unas notas en la FM-1, canal 2"
echo "  goa-ports --escuchar Circuit muestra lo que manda la Circuit"
echo "  goa-log                      ver qué está haciendo el motor"
echo "  goa-debug                    correr a mano mostrando cada nota"
echo "  goa-restart                  reiniciar tras editar $CONFIG"
echo "  goa-update                   bajar la última versión"
echo
echo "Si es la primera instalación, reinicia la Pi una vez: sudo reboot"
