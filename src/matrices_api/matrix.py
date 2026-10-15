"""Suma y resta exactas: se trabaja con fracciones para que 0.1 + 0.2 dé 0.3.

Una operación es una expresión A ± B ± C …: dos matrices (operación simple)
o más (compuesta), con un operador independiente entre cada par.
"""

from decimal import Decimal
from fractions import Fraction

MAX_SIZE = 10
MAX_CHARS = 30
MAX_MATRICES = 8
OPERATORS = ("+", "-")


class MatrixError(ValueError):
    pass


def parse_value(raw: str) -> Fraction:
    """Acepta enteros, decimales (con punto o coma) y fracciones como -3/4."""
    text = str(raw).strip().replace(",", ".").replace("−", "-")
    if not text or len(text) > MAX_CHARS:
        raise MatrixError(f"Valor inválido: '{raw}'")
    try:
        if "/" in text:
            num, den = text.split("/", 1)
            value = Fraction(Decimal(num.strip())) / Fraction(Decimal(den.strip()))
        else:
            value = Fraction(Decimal(text))
    except (ArithmeticError, ValueError):
        raise MatrixError(f"Valor inválido: '{raw}'") from None
    return value


def parse_matrix(rows: list[list[str]], name: str) -> list[list[Fraction]]:
    if not rows or not rows[0]:
        raise MatrixError(f"La matriz {name} está vacía.")
    cols = len(rows[0])
    if len(rows) > MAX_SIZE or cols > MAX_SIZE:
        raise MatrixError(f"La matriz {name} supera {MAX_SIZE}x{MAX_SIZE}.")
    if any(len(r) != cols for r in rows):
        raise MatrixError(f"Todas las filas de {name} deben tener {cols} columnas.")
    try:
        return [[parse_value(v) for v in r] for r in rows]
    except MatrixError as e:
        raise MatrixError(f"Matriz {name}: {e}") from None


def format_value(value: Fraction, as_fraction: bool) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    if as_fraction:
        return f"{value.numerator}/{value.denominator}"
    # Suma/resta de decimales finitos es un decimal finito: es exacto.
    d = Decimal(value.numerator) / Decimal(value.denominator)
    return format(d.normalize(), "f")


def name_of(index: int) -> str:
    """A, B, C… como en la app."""
    return chr(ord("A") + index)


def evaluate(matrices: list[list[list[str]]], operators: list[str]) -> list[list[str]]:
    """Evalúa A op1 B op2 C … de izquierda a derecha, celda a celda."""
    if not 2 <= len(matrices) <= MAX_MATRICES:
        raise MatrixError(f"Usa entre 2 y {MAX_MATRICES} matrices.")
    if len(operators) != len(matrices) - 1:
        raise MatrixError("Debe haber un operador entre cada par de matrices.")
    if any(op not in OPERATORS for op in operators):
        raise MatrixError("Operador inválido: usa '+' o '-'.")
    parsed = [parse_matrix(m, name_of(i)) for i, m in enumerate(matrices)]
    rows, cols = len(parsed[0]), len(parsed[0][0])
    for i, m in enumerate(parsed[1:], start=1):
        if len(m) != rows or len(m[0]) != cols:
            raise MatrixError(
                f"Las matrices deben tener el mismo tamaño "
                f"(A es {rows}x{cols} y {name_of(i)} es {len(m)}x{len(m[0])})."
            )
    signs = [1] + [1 if op == "+" else -1 for op in operators]
    result = []
    for r in range(rows):
        row = []
        for c in range(cols):
            value = sum(s * m[r][c] for s, m in zip(signs, parsed))
            # Fracción solo en las celdas donde alguna matriz tenía una fracción.
            as_fraction = any("/" in str(m[r][c]) for m in matrices)
            row.append(format_value(value, as_fraction))
        result.append(row)
    return result


def calculate(operation: str, a: list[list[str]], b: list[list[str]]) -> list[list[str]]:
    """Operación simple entre dos matrices."""
    if operation not in ("add", "subtract"):
        raise MatrixError("Operación inválida: usa 'add' o 'subtract'.")
    return evaluate([a, b], ["+" if operation == "add" else "-"])


def normalize(rows: list[list[str]]) -> list[list[str]]:
    """Guarda los valores tal como los escribió el usuario, sin espacios."""
    return [[str(v).strip() for v in r] for r in rows]
