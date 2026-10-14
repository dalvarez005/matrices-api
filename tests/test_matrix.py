import pytest

from matrices_api.matrix import MatrixError, calculate


def test_suma_y_resta_enteros():
    a = [["1", "2"], ["3", "4"]]
    b = [["5", "6"], ["7", "8"]]
    assert calculate("add", a, b) == [["6", "8"], ["10", "12"]]
    assert calculate("subtract", a, b) == [["-4", "-4"], ["-4", "-4"]]


def test_decimales_exactos_y_coma():
    assert calculate("add", [["0.1"]], [["0,2"]]) == [["0.3"]]
    assert calculate("subtract", [["1.5"]], [["0.25"]]) == [["1.25"]]


def test_fracciones():
    assert calculate("add", [["1/2", "1/3"]], [["1/2", "1/6"]]) == [["1", "1/2"]]
    assert calculate("subtract", [["1/3"]], [["0.5"]]) == [["-1/6"]]
    # Cada celda decide: la fracción no contagia a las demás.
    assert calculate("add", [["1/2", "0.1"]], [["1", "0.2"]]) == [["3/2", "0.3"]]


@pytest.mark.parametrize(
    "a,b,msg",
    [
        ([["1", "2"]], [["1"]], "mismo tamaño"),
        ([["1", "x"]], [["1", "2"]], "Valor inválido"),
        ([["1", "2"], ["3"]], [["1", "2"], ["3", "4"]], "columnas"),
        ([["1/0"]], [["1"]], "Valor inválido"),
        ([[]], [[]], "vacía"),
    ],
)
def test_errores(a, b, msg):
    with pytest.raises(MatrixError, match=msg):
        calculate("add", a, b)
