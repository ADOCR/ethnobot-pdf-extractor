# ethnobot-pdf-extractor
# Extractor de Datos Etnobotánicos desde PDFs

*Un pipeline de Python diseñado para extraer y estructurar información sobre especies de plantas y sus usos precolombinos a partir de documentos PDF académicos, utilizando Modelos de Lenguaje Grandes (LLMs) locales a través de Ollama.*

## 📖 Descripción

Este proyecto aborda el desafío de extraer datos estructurados de fuentes no estructuradas como artículos académicos y tesis. El script procesa una carpeta de archivos PDF, realiza reconocimiento óptico de caracteres (OCR) si es necesario, limpia el texto, lo divide en fragmentos manejables y utiliza un LLM local para identificar entidades clave:

- `especie_cientifica`
- `nombre_comun`
- `uso_precolombino`

Los resultados son normalizados, filtrados para asegurar su calidad y finalmente guardados en un archivo Excel para su posterior análisis.

## 🌟 Características

- **Procesamiento de PDFs**: Compatible con documentos de texto digital y escaneados.
- **Limpieza de Texto**: Normaliza y limpia el texto extraído para mejorar la calidad de entrada al modelo.
- **Extracción Inteligente**: Utiliza un LLM local para el reconocimiento y la extracción de entidades.
- **Manejo de Formatos**: Robusto frente a diversas estructuras de salida JSON generadas por los LLMs.
- **Salida Estructurada**: Exporta los datos limpios y deduplicados a un archivo `.xlsx`.

## 🛠️ Requisitos

- Python 3.8+
- Ollama instalado y en ejecución.
- Tesseract OCR instalado y accesible en el PATH del sistema.
- Hardware recomendado: GPU con al menos 4GB de VRAM.

## ⚙️ Instalación

Sigue estos pasos para configurar tu entorno de trabajo:

### 1. Clona el repositorio:

```bash
git clone (https://github.com/ADOCR/ethnobot-pdf-extractor/)
cd tu-repositorio
```

### 2. Crea y activa un entorno virtual (recomendado):

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Instala las dependencias:

```bash
pip install -r requirements.txt
```

### 4. Instala el Modelo de Lenguaje:

Este proyecto se evaluó con múltiples modelos, siendo `deepseek-r1:8b` el recomendado por su balance entre rendimiento y precisión.

```bash
ollama pull deepseek-r1:8b
```

## 🔧 Configuración

### 1. Crea la carpeta de datos:

```bash
mkdir data_pdf
```

### 2. Añade tus documentos:

Coloca todos los archivos PDF a procesar dentro de `data_pdf`.

### 3. Ajusta el script (opcional):

Edita `extractor_especies.py` y modifica la sección de `CONFIGURACIÓN GENERAL` según tus necesidades, especialmente el `MODEL_ID` si decides usar otro modelo.

## 🚀 Uso

Ejecuta el script desde tu terminal:

```bash
python extractor_especies.py
```

Al finalizar, encontrarás los resultados (log y Excel) en la carpeta `outputs`.

## 📊 Análisis Comparativo de Modelos

Durante el desarrollo, se evaluaron sistemáticamente siete familias de modelos (\~7-8B parámetros). Ranking final:

| Clasificación | Modelo          | Evaluación Cualitativa: Veredicto                            |
| ------------- | --------------- | ------------------------------------------------------------ |
| 1º 🥇         | deepseek-r1:8b  | El Campeón Pragmático. Mejor balance sensibilidad-precisión. |
| 2º 🥈         | phi3\:mini      | Potencial alto, pero con errores factuales e inconsistencia. |
| 3º 🥉         | gemma:7b        | Preciso, fiable, pero demasiado conservador.                 |
| 4º            | qwen2:7b        | Potente, pero errores conceptuales críticos.                 |
| 5º            | llama3:8b       | Excelente formato, errores de conocimiento graves.           |
| DQ            | openthinker:7b  | Descalificado por comportamiento errático.                   |
| DQ            | granite-code:8b | Descalificado por alucinaciones factuales masivas.           |

## 📦 requirements.txt

```text
ollama
pdfplumber
pdf2image
pytesseract
pandas
openpyxl
tqdm
langdetect
```

---

.

