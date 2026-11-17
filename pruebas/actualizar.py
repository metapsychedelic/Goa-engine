"""Pruebas del botón de actualización (goa/actualizar.py) contra un «GitHub» falso:
un repositorio en una carpeta temporal y una «Pi» que lo clona.

  python3 -m pruebas.actualizar
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from goa import actualizar as A

RAIZ = Path(__file__).resolve().parent.parent


def ok(cond, texto):
    print(("OK    " if cond else "FALLA ") + texto)
    return cond


def git(carpeta, *args):
    subprocess.run(["git", "-c", "user.name=prueba", "-c", "user.email=p@p", *args], cwd=carpeta, check=True,
                   capture_output=True, text=True)


def version(carpeta, v):
    (carpeta / "goa" / "__init__.py").write_text(f'__version__ = "{v}"\n')


def commit(carpeta, mensaje):
    git(carpeta, "add", "-A")
    git(carpeta, "commit", "-q", "-m", mensaje)
    git(carpeta, "push", "-q", "origin", "main")


def main():
    bien = True
    tmp = Path(tempfile.mkdtemp())
    try:
        github, dev, pi = tmp / "github.git", tmp / "dev", tmp / "pi"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(github)], check=True)
        # El desarrollador sube la 9.0.0 (el código de verdad, con otro número).
        shutil.copytree(RAIZ, dev, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.mp3", "*.wav"))
        git(dev, "init", "-q", "-b", "main")
        git(dev, "remote", "add", "origin", str(github))
        version(dev, "9.0.0")
        commit(dev, "Primera versión")
        subprocess.run(["git", "clone", "-q", str(github), str(pi)], check=True)
        config = pi / "config.ejemplo.toml"

        e = A.estado(pi)
        bien &= ok(e["git"] and e["version"] == "9.0.0" and not e["hay_nueva"], "recién instalada: 9.0.0, nada nuevo")

        version(dev, "9.1.0")
        commit(dev, "Bajo con fusas nuevas")
        e = A.estado(pi)
        bien &= ok(e["hay_nueva"] and e["version_nueva"] == "9.1.0" and e["cambios"] == ["Bajo con fusas nuevas"],
                   "ve la 9.1.0 en GitHub y qué trae")
        bien &= ok(A.estado(pi, buscar=False)["version"] == "9.0.0", "buscar no cambia nada")

        r = A.actualizar(config, pi)
        bien &= ok(r["version"] == "9.1.0" and r["antes"] == "9.0.0" and r["cambio"] and not r["instalar"], "actualiza a la 9.1.0")
        bien &= ok(not A.estado(pi)["hay_nueva"], "después ya está al día")
        r = A.actualizar(config, pi)
        bien &= ok(not r["cambio"], "actualizar estando al día no cambia nada (y no reinicia)")

        # Una versión rota: no arranca. Debe volver sola a la 9.1.0.
        version(dev, "9.2.0")
        motor = dev / "goa" / "motor.py"
        bueno = motor.read_text()
        motor.write_text(bueno + "\ndef roto(:\n")
        commit(dev, "Versión rota")
        try:
            A.actualizar(config, pi)
            bien &= ok(False, "una versión que no arranca se rechaza")
        except A.ErrorActualizacion as ex:
            bien &= ok("Sigues en la 9.1.0" in str(ex), f"una versión que no arranca se rechaza: «{ex}»")
        bien &= ok(A.estado(pi, buscar=False)["version"] == "9.1.0" and "roto" not in (pi / "goa" / "motor.py").read_text(),
                   "y la Pi queda en la 9.1.0, con el código bueno")

        # Volver a la anterior y de nuevo a la última (ya arreglada).
        r = A.anterior(config, pi)
        e = A.estado(pi)
        bien &= ok(r["version"] == "9.0.0" and e["en_anterior"] and e["hay_nueva"], "vuelve a la anterior (9.0.0) y ofrece la última")
        motor.write_text(bueno)
        version(dev, "9.3.0")
        (dev / "install.sh").write_text((dev / "install.sh").read_text() + "\n# dependencia nueva\n")
        commit(dev, "Arreglo y dependencia nueva")
        r = A.actualizar(config, pi)
        bien &= ok(r["version"] == "9.3.0" and r["instalar"], "desde la anterior, actualiza a la 9.3.0 y avisa que cambió install.sh")
        bien &= ok(not A.estado(pi, buscar=False)["en_anterior"], "y vuelve a quedar en main")

        # Cambios hechos a mano en la Pi que chocan con los nuevos: no rompe nada, avisa.
        version(dev, "9.4.0")
        commit(dev, "Otra")
        (pi / "goa" / "__init__.py").write_text('__version__ = "mía"\n')
        try:
            A.actualizar(config, pi)
            bien &= ok(False, "con cambios a mano avisa")
        except A.ErrorActualizacion as ex:
            bien &= ok("a mano" in str(ex), f"con cambios a mano avisa: «{ex}»")
        bien &= ok((pi / "goa" / "__init__.py").read_text() == '__version__ = "mía"\n', "y no toca esos cambios")
        git(pi, "checkout", "-q", "--", "goa/__init__.py")

        # Sin internet (GitHub no existe): mensaje claro, nada cambia.
        git(pi, "remote", "set-url", "origin", "https://127.0.0.1:9/no-existe.git")
        try:
            A.estado(pi)
            bien &= ok(False, "sin internet avisa")
        except A.ErrorActualizacion as ex:
            bien &= ok("internet" in str(ex) or "GitHub" in str(ex), f"sin internet avisa: «{ex}»")

        sin_git = tmp / "copia"
        sin_git.mkdir()
        bien &= ok(A.estado(sin_git) == {"git": False}, "una instalación copiada a mano (sin git) lo dice")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nTodo bien." if bien else "\nHay fallas.")
    return 0 if bien else 1


if __name__ == "__main__":
    sys.exit(main())
