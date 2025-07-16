# extractor_especies_debug.py — Con impresión de chunks enviados al LLM y logging a archivo
"""
Pipeline para extraer especies con uso precolombino de PDFs,
con logging DEBUG que se escribe tanto en consola como en un archivo.
Requiere: Ollama en localhost:11434 y un modelo que acepte salida estructurada (por ejemplo, deepseek‑r1:8b).
"""
# ╭──────────── IMPORTS ────────────╮
import os
import sys
import re
import json
import logging
import subprocess
import unicodedata
from textwrap import shorten
from typing import List, Dict, Any, Generator

import ollama
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
import pandas as pd
from tqdm.auto import tqdm
# ╰─────────────────────────────────╯

# ╭── instalar openpyxl si falta (para .xlsx) ─╮
try:
    import openpyxl  # noqa: F401
except ModuleNotFoundError:
    print("Instalando openpyxl …")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "openpyxl"])
# ╰────────────────────────────────────────────╯

# ╭───────── CONFIGURACIÓN GENERAL ─────────╮
PDF_DIR    = "data_pdf"
OUTPUT_DIR = "outputs"
OUT_FILE   = os.path.join(OUTPUT_DIR, "especies_precolombinas_debug.xlsx")
LOG_PATH   = os.path.join(OUTPUT_DIR, "extractor_especies_debug.log")

#MODEL_ID   = "deepseek-r1:8b"   # Ajusta al modelo que tengas descargado
MODEL_ID   = "olmo2:7b"
TESS_LANG  = "spa+eng"
CHUNK_SIZE = 4_000

PALI_STOP = {
    "granos", "polínico", "polinico", "trilete",
    "monolete", "exina", "ornamentación", "pólenes",
    "fóveado", "estomatita", "tricolpado"
}

BINOMIO    = re.compile(r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+ [a-záéíóúñ]{2,}", re.U)
CLAVES_USO = re.compile(
    r"\b(aliment|comest|madera|medicin|ritual|tinte|textil|aroma|colorant)", re.I
)

SYSTEM_PROMPT = """
Eres un asistente experto en etnobotánica e historia precolombina de América tropical.
IGNORA términos morfológicos de palinología (trilete, monolete, exina, etc.).
Registra especies solo cuando:
  • se menciona explícitamente un uso precolombino (alimentación, madera, medicina…)
  • aparece el nombre científico o común claro.
Regla Adicional: Si el uso no está en la misma frase que la especie, pero lo infieres del contexto cercano, debes añadir una clave "justificacion_del_uso" y citar textualmente la frase del documento que respalda tu inferencia. Si el uso es explícito y directo, no añadas esta clave.

Responde EXCLUSIVAMENTE con un arreglo JSON válido...
Ejemplo de uso explícito:
[
  {
    "especie_cientifica": "Zea mays",
    "nombre_comun": "Maíz",
    "uso_precolombino": "Alimentación y ceremonias"
  }
]
Ejemplo de uso inferido:
[
  {
    "especie_cientifica": "Bactris gasipaes",
    "nombre_comun": "Pejibaye",
    "uso_precolombino": "Construcción",
    "justificacion_del_uso": "Las palmas de la región se usaban para la construcción de techos."
  }
]
""".strip()
# ╰──────────────────────────────────────────╯

# ╭──────── Logger en modo DEBUG ───────────╮
# Se registran nuestros propios mensajes a nivel DEBUG, pero se suprime
# el exceso de verbosidad de librerías como pdfminer/pdfplumber.

os.makedirs(OUTPUT_DIR, exist_ok=True)  # Asegura que la carpeta exista para el log

# 1) Root logger: INFO (evita inundarnos con DEBUG externos)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)

# 2) Nuestro logger de módulo: DEBUG (no propaga al root)
log = logging.getLogger("extractor")
log.setLevel(logging.DEBUG)
for h in logging.getLogger().handlers:
    log.addHandler(h)
log.propagate = False

# 3) Silencia librerías ruidosas
for noisy in ("pdfminer", "pdfplumber", "PIL", "pdf2image"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
# ╰─────────────────────────────────────────╯

# ╭─────────── UTILIDADES DE LIMPIEZA ───────────╮
def clean_text(raw: str) -> str:
    txt = unicodedata.normalize("NFKD", raw)
    txt = re.sub(r"\s+", " ", txt)
    txt = re.sub(r"\b(página|page)\s*\d+\b", " ", txt, flags=re.I)
    txt = re.sub(r"tabla\s*\d+(\.\d+)?\b", " ", txt, flags=re.I)
    txt = re.sub(r"\b\d+\s*(x|–|—)\s*\d+\b", " ", txt)
    txt = re.sub(r"[_•·●■◆►▪\-]{2,}", " ", txt)
    txt = " ".join(w for w in txt.split() if w.lower() not in PALI_STOP)
    return re.sub(r" {2,}", " ", txt).strip()
# ╰───────────────────────────────────────────────╯

# ╭─────────── FUNCIONES PRINCIPALES ─────────────╮

def setup_dirs():
    os.makedirs(PDF_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def extract_text(pdf_path: str) -> str:
    log.info(f"Procesando {os.path.basename(pdf_path)}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            txt = "\n".join(p.extract_text() or "" for p in pdf.pages)
        if len(txt.strip()) > 100:
            log.debug("   → texto digital OK")
            return txt
        log.debug("   → texto escaso; OCR…")
    except Exception as e:
        log.warning(f"   → fallo digital ({e}); OCR…")

    try:
        imgs = convert_from_path(pdf_path, dpi=300)
        txt = "\n".join(pytesseract.image_to_string(i, lang=TESS_LANG) for i in imgs)
        log.debug("   → OCR completado")
        return txt
    except Exception as e:
        log.error(f"   → OCR falló: {e}")
        return ""


def chunk_text(txt: str, size: int) -> Generator[str, None, None]:
    for i in range(0, len(txt), size):
        ch = txt[i:i + size]
        if BINOMIO.search(ch) and CLAVES_USO.search(ch):
            yield ch


def llm_extract(chunk: str) -> List[Dict[str, Any]]:
    """Envía el chunk al LLM. Se pide salida JSON pura via `format='json'`."""
    try:
        resp = ollama.chat(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": chunk}
            ],
            format="json",                       # ¡salida estructurada!
            options={"temperature": 0.0, "top_p": 0.1}
        )
        raw = resp["message"]["content"]
        log.debug("Contenido recibido (4000 chars):\n%s", raw[:4000])
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning(f"   → JSON inválido: {e}")
        return []
    except ollama.ResponseError as e:
        log.error(f"   → Error de Ollama: {e.error}")
        return []
    except Exception as e:
        log.error(f"   → Error inesperado: {e}")
        return []

    # Normaliza a lista de dicts
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        log.warning("   → El JSON no es lista ni objeto válido; se descarta.")
        return []

    return [d for d in data if isinstance(d, dict)]


def normaliza_registros(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filtra y normaliza registros. Ahora es capaz de manejar tanto objetos
    simples como objetos que contienen listas de especies.
    """
    registros_finales = []
    for item in lst:
        if not isinstance(item, dict):
            continue

        especies = item.get("especie_cientifica")
        comunes = item.get("nombre_comun")
        usos = item.get("uso_precolombino")

        # Caso 1: El valor es una lista (como en la salida de OLMo)
        if isinstance(especies, list):
            for i, especie_nombre in enumerate(especies):
                nombre_limpio = especie_nombre.strip()
                if not nombre_limpio:
                    continue

                try:
                    nombre_comun_actual = comunes[i] if comunes and i < len(comunes) else ""
                except (TypeError, IndexError):
                    nombre_comun_actual = ""

                # Como el uso puede no venir en la lista, lo manejamos con cuidado
                try:
                    uso_actual = usos[i] if isinstance(usos, list) and i < len(usos) else ""
                except (TypeError, IndexError):
                    uso_actual = ""

                # Solo añadimos si tenemos especie y uso
                if nombre_limpio and uso_actual:
                     registros_finales.append({
                        "especie_cientifica": nombre_limpio,
                        "nombre_comun": nombre_comun_actual.strip(),
                        "uso_precolombino": uso_actual.strip()
                    })

        # Caso 2: El valor es un texto simple (el comportamiento normal)
        elif isinstance(especies, str):
            nombre_limpio = especies.strip()
            # Aseguramos que 'usos' no sea una lista aquí
            uso_limpio = (usos if isinstance(usos, str) else "") or ""

            if nombre_limpio and uso_limpio.strip() and nombre_limpio.lower() not in {"", "no especificado"}:
                registros_finales.append({
                    "especie_cientifica": nombre_limpio,
                    "nombre_comun": (item.get("nombre_comun") or "").strip(),
                    "uso_precolombino": uso_limpio.strip()
                })

    return registros_finales
# ╰───────────────────────────────────────────────╯

# ╭──────────────────── MAIN ─────────────────────╮

def main():
    setup_dirs()
    pdfs = [f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")]
    if not pdfs:
        log.error(f"No hay PDFs en '{PDF_DIR}'.")
        return

    registros: List[Dict[str, Any]] = []

    for pdf in tqdm(pdfs, desc="PDFs"):
        full = clean_text(extract_text(os.path.join(PDF_DIR, pdf)))
        if not full:
            continue

        for idx, ch in enumerate(chunk_text(full, CHUNK_SIZE), 1):
            log.debug("   → CHUNK %d [%d chars]: %s", idx, len(ch),
                      shorten(ch, width=120, placeholder="…"))
            datos = normaliza_registros(llm_extract(ch))
            for d in datos:
                d["archivo_origen"] = pdf
            registros.extend(datos)

        log.info(
            f"   → {len([r for r in registros if r['archivo_origen'] == pdf])} registros válidos en {pdf}")

    if not registros:
        log.warning("Sin especies encontradas.")
        return

    df = pd.DataFrame(registros).drop_duplicates(
        subset=["especie_cientifica", "nombre_comun", "uso_precolombino", "archivo_origen"]
    )
    print(df.to_string())
    df.to_excel(OUT_FILE, index=False)
    log.info(f"✅ Guardado {len(df)} filas en '{OUT_FILE}'")


if __name__ == "__main__":
    main()
# ╰───────────────────────────────────────────────╯
