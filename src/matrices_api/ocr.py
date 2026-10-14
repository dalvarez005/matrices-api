"""Lee una o dos matrices de una foto con RapidOCR (modelos PP-OCR en ONNX,
corre en el propio servidor, sin GPU ni servicios externos).

El OCR entrega textos con su posición; acá se ordenan en filas y columnas.
El resultado siempre se muestra al usuario para que lo corrija antes de
calcular: celdas que no se pudieron leer llegan como None.
"""

import io
import re
import threading
from dataclasses import dataclass
from statistics import median

from PIL import Image, ImageOps

from .matrix import MAX_SIZE

_NUMBER = re.compile(r"^-?\d+(\.\d+)?(/\d+)?$")
_OPERATORS = {"+": "add", "-": "subtract", "—": "subtract", "–": "subtract"}


class OcrError(Exception):
    pass


@dataclass
class Token:
    text: str
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def cx(self) -> float:
        return self.left + self.width / 2

    @property
    def cy(self) -> float:
        return self.top + self.height / 2


# ---------------------------------------------------------------- RapidOCR

_engine = None
_engine_lock = threading.Lock()


def _get_engine():
    """El modelo se carga una vez (unos segundos) y queda en memoria."""
    global _engine
    with _engine_lock:
        if _engine is None:
            from rapidocr import RapidOCR

            _engine = RapidOCR(
                params={
                    "Global.log_level": "error",
                    # Las matrices vienen derechas: sin clasificador de giro.
                    "Global.use_cls": False,
                    "Det.limit_side_len": 640,
                    "EngineConfig.onnxruntime.intra_op_num_threads": 4,
                }
            )
        return _engine


def available() -> bool:
    try:
        import rapidocr  # noqa: F401
    except ImportError:
        return False
    return True


def _prepare(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
    except Exception:
        raise OcrError("No se pudo abrir la imagen. Usa JPG, PNG o WebP.") from None
    img = img.convert("RGB")
    # Fotos enormes se achican: el modelo no gana precisión y la Orange Pi tarda.
    if max(img.size) > 1280:
        img.thumbnail((1280, 1280), Image.LANCZOS)
    return img


def read_tokens(data: bytes, timeout: int) -> list[Token]:
    import numpy as np

    img = _prepare(data)
    try:
        result = _get_engine()(np.asarray(img))
    except Exception:
        raise OcrError("No se pudo leer la imagen.") from None
    if result.boxes is None:
        return []
    tokens = []
    for box, text in zip(result.boxes, result.txts):
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        tokens.extend(
            split_token(Token(str(text), int(min(xs)), int(min(ys)),
                              int(max(xs) - min(xs)), int(max(ys) - min(ys))))
        )
    return tokens


def split_token(t: Token) -> list[Token]:
    """El OCR a veces junta una fila entera ("3  -2  5"): se separa en
    números, repartiendo el ancho según la cantidad de caracteres."""
    parts = t.text.split()
    if len(parts) <= 1:
        return [t]
    per_char = t.width / max(len(t.text), 1)
    out, pos = [], 0
    for part in parts:
        start = t.text.index(part, pos)
        out.append(Token(part, int(t.left + start * per_char), t.top,
                         max(int(len(part) * per_char), 1), t.height))
        pos = start + len(part)
    return out


# ------------------------------------------------- Tokens → matrices


def _clean(text: str) -> str:
    text = text.replace(",", ".").replace("—", "-").replace("–", "-").replace("−", "-")
    # Corchetes o barras pegados al número: "[3", "4|", "(2".
    return text.strip("[]|()").strip(".")


def _merge_signs(tokens: list[Token], h: float) -> list[Token]:
    """Un '-' suelto pegado a la izquierda de un número es su signo."""
    signs = {}  # índice del número -> índice de su '-'
    for i, t in enumerate(tokens):
        if t.text != "-":
            continue
        candidates = [
            j for j, n in enumerate(tokens)
            if j not in signs and _NUMBER.match(n.text) and not n.text.startswith("-")
            and abs(n.cy - t.cy) < h * 0.6 and 0 <= n.left - t.right < h * 0.8
        ]
        if candidates:
            signs[min(candidates, key=lambda j: tokens[j].left)] = i
    out = []
    for j, t in enumerate(tokens):
        if j in signs:
            s = tokens[signs[j]]
            out.append(Token("-" + t.text, s.left, t.top, t.right - s.left, t.height))
        elif j not in signs.values():
            out.append(t)
    return out


def _intervals(tokens: list[Token]) -> list[tuple[int, int]]:
    """Columnas: proyección de los números sobre el eje x."""
    spans = sorted((t.left, t.right) for t in tokens)
    merged: list[list[int]] = []
    for left, right in spans:
        if merged and left <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], right)
        else:
            merged.append([left, right])
    return [(a, b) for a, b in merged]


def _rows(tokens: list[Token], h: float) -> list[list[Token]]:
    rows: list[list[Token]] = []
    for t in sorted(tokens, key=lambda t: t.cy):
        if rows and abs(t.cy - median(x.cy for x in rows[-1])) < h * 0.6:
            rows[-1].append(t)
        else:
            rows.append([t])
    return rows


def _grid(tokens: list[Token], h: float) -> list[list[str | None]]:
    cols = _intervals(tokens)[:MAX_SIZE]
    rows = _rows(tokens, h)[:MAX_SIZE]
    grid: list[list[str | None]] = [[None] * len(cols) for _ in rows]
    for r, row in enumerate(rows):
        for t in sorted(row, key=lambda t: t.left):
            c = next((i for i, (a, b) in enumerate(cols) if a <= t.cx <= b), None)
            if c is not None:
                grid[r][c] = t.text if grid[r][c] is None else grid[r][c] + t.text
    return grid


def _split_x(numbers: list[Token], operators: list[Token]) -> tuple[float | None, str | None]:
    """Dónde termina A y empieza B, y la operación si se vio el signo."""
    top = min(t.top for t in numbers)
    bottom = max(t.top + t.height for t in numbers)
    for op in operators:
        if top <= op.cy <= bottom:
            left = sum(1 for t in numbers if t.cx < op.cx)
            right = sum(1 for t in numbers if t.cx > op.cx)
            if left and right:
                return op.cx, _OPERATORS[op.text]
    # Sin signo visible: el hueco entre columnas mucho más grande que el resto.
    cols = _intervals(numbers)
    gaps = [cols[i + 1][0] - cols[i][1] for i in range(len(cols) - 1)]
    if len(gaps) >= 2:
        widest = max(range(len(gaps)), key=gaps.__getitem__)
        others = gaps[:widest] + gaps[widest + 1 :]
        if gaps[widest] > 2.5 * max(median(others), 1):
            return (cols[widest][1] + cols[widest + 1][0]) / 2, None
    return None, None


def tokens_to_matrices(tokens: list[Token]) -> dict:
    tokens = [Token(_clean(t.text), t.left, t.top, t.width, t.height) for t in tokens]
    tokens = [t for t in tokens if t.text]
    if not tokens:
        return {"matrices": [], "operation": None}
    h = median(t.height for t in tokens if _NUMBER.match(t.text) or t.text in _OPERATORS) or 1
    tokens = _merge_signs(tokens, h)
    numbers = [t for t in tokens if _NUMBER.match(t.text)]
    # Corchetes y barras leídos como "1": mucho más altos que un número.
    numbers = [t for t in numbers if t.height < h * 1.7]
    if not numbers:
        return {"matrices": [], "operation": None}
    h = median(t.height for t in numbers)
    operators = [t for t in tokens if t.text in _OPERATORS]

    split, operation = _split_x(numbers, operators)
    groups = (
        [numbers]
        if split is None
        else [[t for t in numbers if t.cx < split], [t for t in numbers if t.cx > split]]
    )
    matrices = []
    for group in groups:
        grid = _grid(group, h)
        # Filas casi vacías suelen ser ruido (un título, una marca).
        cols = len(grid[0]) if grid else 0
        grid = [r for r in grid if sum(v is not None for v in r) * 2 >= cols]
        if grid and cols:
            matrices.append({"rows": len(grid), "cols": cols, "values": grid})
    return {"matrices": matrices, "operation": operation if len(matrices) == 2 else None}
