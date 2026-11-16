"""Fuentes guardadas en la Pi: se eligen bien de la hoja de Google y no se rompe sin internet."""

import tempfile
from pathlib import Path

from goa import fuentes

CSS = """
/* cyrillic */
@font-face { font-family: 'IBM Plex Sans'; font-weight: 400; src: url(https://x/cyr400.woff2) format('woff2'); }
/* latin-ext */
@font-face { font-family: 'IBM Plex Sans'; font-weight: 400; src: url(https://x/ext400.woff2) format('woff2'); }
/* latin */
@font-face { font-family: 'IBM Plex Sans'; font-weight: 400; src: url(https://x/lat400.woff2) format('woff2'); }
/* latin */
@font-face { font-family: 'IBM Plex Sans'; font-weight: 700; src: url(https://x/lat700.woff2) format('woff2'); }
"""


def main():
    assert fuentes.url_latina(CSS, 400) == "https://x/lat400.woff2"
    assert fuentes.url_latina(CSS, 700) == "https://x/lat700.woff2"
    assert fuentes.url_latina(CSS, 500) is None

    pedidos = []

    def falsa(url):
        pedidos.append(url)
        if "css2" in url:
            fam = url.split("family=")[1].split(":")[0].replace("+", " ")
            return "".join(f"/* latin */\n@font-face {{ font-family: '{fam}'; font-weight: {p}; "
                           f"src: url(https://x/{fam.replace(' ', '')}{p}.woff2) format('woff2'); }}\n"
                           for f, p in fuentes.FUENTES.values() if f == fam).encode()
        return b"wOF2" + url.encode()

    with tempfile.TemporaryDirectory() as d:
        carpeta = Path(d) / "fuentes"
        assert fuentes.asegurar(carpeta, falsa) == len(fuentes.FUENTES)
        assert not fuentes.faltan(carpeta)
        assert sum("css2" in u for u in pedidos) == 3  # una hoja por familia
        assert fuentes.leer("megrim-400.woff2", carpeta).startswith(b"wOF2")
        assert fuentes.leer("../config.toml", carpeta) is None
        assert fuentes.leer("otra.woff2", carpeta) is None
        pedidos.clear()
        assert fuentes.asegurar(carpeta, falsa) == 0 and not pedidos  # ya estaban

    def sin_red(url):
        raise OSError("sin internet")

    with tempfile.TemporaryDirectory() as d:
        carpeta = Path(d) / "fuentes"
        assert fuentes.asegurar(carpeta, sin_red) == 0
        assert len(fuentes.faltan(carpeta)) == len(fuentes.FUENTES)
    print("fuentes: ok")


if __name__ == "__main__":
    main()
