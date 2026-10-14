"""Suma y resta exactas: se trabaja con fracciones para que 0.1 + 0.2 dé 0.3."""

from decimal import Decimal
from fractions import Fraction

MAX_SIZE = 10
MAX_CHARS = 30


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


def calculate(operation: str, a: list[list[str]], b: list[list[str]]) -> list[list[str]]:
    if operation not in ("add", "subtract"):
        raise MatrixError("Operación inválida: usa 'add' o 'subtract'.")
    ma, mb = parse_matrix(a, "A"), parse_matrix(b, "B")
    if len(ma) != len(mb) or len(ma[0]) != len(mb[0]):
        raise MatrixError(
            f"Las matrices deben tener el mismo tamaño "
            f"(A es {len(ma)}x{len(ma[0])} y B es {len(mb)}x{len(mb[0])})."
        )
    sign = 1 if operation == "add" else -1
    # Fracción solo en las celdas donde A o B tenía una fracción.
    return [
        [
            format_value(x + sign * y, "/" in str(sa) or "/" in str(sb))
            for x, y, sa, sb in zip(ra, rb, a_row, b_row)
        ]
        for ra, rb, a_row, b_row in zip(ma, mb, a, b)
    ]


def normalize(rows: list[list[str]]) -> list[list[str]]:
    """Guarda los valores tal como los escribió el usuario, sin espacios."""
    return [[str(v).strip() for v in r] for r in rows]
