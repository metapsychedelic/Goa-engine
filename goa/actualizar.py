"""Actualizar el motor desde la app: lo mismo que goa-update, con red de seguridad.

- `estado()` busca en GitHub si hay una versión nueva y qué trae (sin cambiar nada).
- `actualizar()` baja la última versión de main, comprueba que el código nuevo arranca y
  carga tu configuración, y si no, vuelve sola a la versión en que estabas.
- `anterior()` vuelve a la versión previa (como goa-update --anterior).
- `reiniciar()` termina el proceso con calma (apaga las notas y guarda); el servicio
  (Restart=always) lo vuelve a levantar con la versión nueva.

Git corre con prioridad baja: el servicio del motor tiene prioridad de tiempo real y los
procesos hijos la heredarían; así una descarga lenta no le quita tiempo al reloj MIDI.
"""

import logging
import os
import re
import signal
import subprocess
import sys
import threading
from pathlib import Path

log = logging.getLogger("goa")
CARPETA = Path(__file__).resolve().parent.parent
RAMA = "main"


class ErrorActualizacion(Exception):
    pass


def _baja_prioridad():
    try:
        os.sched_setscheduler(0, os.SCHED_OTHER, os.sched_param(0))
    except (AttributeError, OSError):
        pass
    try:
        os.nice(10)
    except OSError:
        pass


def _git(carpeta, *args, timeout=30):
    carpeta = carpeta or CARPETA
    try:
        r = subprocess.run(["git", *args], cwd=carpeta, capture_output=True, text=True, timeout=timeout,
                           preexec_fn=_baja_prioridad, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    except FileNotFoundError:
        raise ErrorActualizacion("Git no está instalado en la Pi") from None
    except subprocess.TimeoutExpired:
        raise ErrorActualizacion("GitHub no respondió: revisa que la Pi tenga internet") from None
    if r.returncode != 0:
        raise ErrorActualizacion(_explicar(r.stderr or r.stdout))
    return r.stdout.strip()


def _explicar(salida):
    texto = salida.strip()
    if re.search(r"could not resolve|unable to access|network|timed out|connection", texto, re.I):
        return "No hay conexión con GitHub: revisa que la Pi tenga internet"
    if re.search(r"local changes|would be overwritten|not possible to fast-forward|diverg", texto, re.I):
        return "Hay archivos del motor cambiados a mano en la Pi: no actualizo para no pisarlos"
    return texto.splitlines()[-1] if texto else "Git falló"


def _existe(carpeta, ref):
    try:
        return bool(_git(carpeta, "rev-parse", "-q", "--verify", ref))
    except ErrorActualizacion:
        return False


def _version_en(carpeta, commit):
    texto = _git(carpeta, "show", f"{commit}:goa/__init__.py")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', texto)
    return m.group(1) if m else "?"


def es_git(carpeta=None):
    return (Path(carpeta or CARPETA) / ".git").exists()


def estado(carpeta=None, buscar=True):
    """Versión instalada y, con `buscar`, si en GitHub hay una más nueva y qué cambios trae."""
    if not es_git(carpeta):
        return {"git": False}
    actual = _git(carpeta, "rev-parse", "HEAD")
    rama = _git(carpeta, "rev-parse", "--abbrev-ref", "HEAD")
    res = {"git": True, "version": _version_en(carpeta, actual), "commit": actual[:7],
           "en_anterior": rama != RAMA,   # después de «volver a la anterior» git queda fuera de main
           "hay_anterior": _existe(carpeta, "HEAD^")}
    if buscar:
        _git(carpeta, "fetch", "-q", "origin", RAMA, timeout=40)
        remoto = _git(carpeta, "rev-parse", f"origin/{RAMA}")
        cambios = _git(carpeta, "log", "--format=%s", f"{actual}..{remoto}") if remoto != actual else ""
        res.update(hay_nueva=bool(cambios) or (res["en_anterior"] and remoto != actual),
                   version_nueva=_version_en(carpeta, remoto),
                   cambios=[c for c in cambios.splitlines() if c][:10])
    return res


def _probar(carpeta, ruta_config):
    """El código que quedó en la carpeta arranca y entiende la configuración: lo comprueba
    un proceso aparte, con el Python de siempre (el motor que corre tiene el código viejo)."""
    codigo = ("import pathlib, py_compile\n"
              "for f in pathlib.Path('goa').glob('*.py'): py_compile.compile(str(f), doraise=True)\n"
              "import goa.web, goa.motor\n"
              "from goa.config import cargar, normalizar\n"
              "from goa.motor import Motor\n"
              "c = normalizar(cargar(%r))\n"
              "m = Motor(c, lambda *a: None); m.start(); m.nota_on(1, 45)\n"
              "for _ in range(4 * 96): m.reloj()\n") % str(ruta_config)
    try:
        r = subprocess.run([sys.executable, "-c", codigo], cwd=carpeta or CARPETA, capture_output=True, text=True,
                           timeout=120, preexec_fn=_baja_prioridad)
    except subprocess.TimeoutExpired:
        return "la versión nueva no terminó de arrancar"
    if r.returncode != 0:
        return (r.stderr.strip().splitlines() or ["error desconocido"])[-1][:200]
    return None


def _cambia_instalacion(carpeta, antes, despues):
    return "install.sh" in _git(carpeta, "diff", "--name-only", antes, despues).split()


def actualizar(ruta_config, carpeta=None):
    """Baja la última versión. Si la nueva no arranca con tu configuración, vuelve a la
    de antes y lanza ErrorActualizacion. Devuelve qué cambió."""
    if not es_git(carpeta):
        raise ErrorActualizacion("Esta instalación no viene de GitHub: actualízala a mano")
    antes = _git(carpeta, "rev-parse", "HEAD")
    version_antes = _version_en(carpeta, antes)
    _git(carpeta, "checkout", "-q", RAMA)
    try:
        _git(carpeta, "pull", "-q", "--ff-only", "origin", RAMA, timeout=90)
    except ErrorActualizacion:
        _git(carpeta, "checkout", "-q", antes)
        raise
    despues = _git(carpeta, "rev-parse", "HEAD")
    error = _probar(carpeta, ruta_config) if despues != antes else None
    if error:
        _git(carpeta, "reset", "-q", "--hard", antes)
        log.warning("La versión nueva no arrancó (%s); quedé en %s", error, version_antes)
        raise ErrorActualizacion(f"La versión nueva no arrancó con tu configuración ({error}). Sigues en la {version_antes}.")
    return {"antes": version_antes, "version": _version_en(carpeta, despues), "cambio": despues != antes,
            "instalar": despues != antes and _cambia_instalacion(carpeta, antes, despues)}


def anterior(ruta_config, carpeta=None):
    """Vuelve a la versión previa a la actual (como goa-update --anterior)."""
    if not es_git(carpeta):
        raise ErrorActualizacion("Esta instalación no viene de GitHub")
    antes = _git(carpeta, "rev-parse", "HEAD")
    if not _existe(carpeta, "HEAD^"):
        raise ErrorActualizacion("No hay una versión anterior")
    _git(carpeta, "checkout", "-q", "HEAD^")
    error = _probar(carpeta, ruta_config)
    if error:
        _git(carpeta, "checkout", "-q", antes)
        raise ErrorActualizacion(f"La versión anterior no arrancó con tu configuración ({error})")
    return {"version": _version_en(carpeta, "HEAD")}


def con_servicio():
    """True si el motor corre como servicio de systemd (que lo vuelve a levantar solo)."""
    return bool(os.environ.get("INVOCATION_ID"))


def reiniciar(espera=1.5):
    """Termina el motor como con Ctrl+C (apaga las notas y cierra los puertos) tras
    `espera` segundos, para que la app alcance a recibir la respuesta."""
    threading.Timer(espera, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
