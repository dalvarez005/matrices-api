from matrices_api.ocr import Token, split_token, tokens_to_matrices


def grid(values, x0=0, y0=0, dx=80, dy=60, w=30, h=30):
    """Tokens de una matriz dibujada a partir de (x0, y0)."""
    return [
        Token(v, x0 + c * dx, y0 + r * dy, w if len(v) < 3 else w * 2, h)
        for r, row in enumerate(values)
        for c, v in enumerate(row)
        if v is not None
    ]


def test_una_matriz():
    out = tokens_to_matrices(grid([["1", "2", "3"], ["4", "5", "6"]]))
    assert out["matrices"] == [{"rows": 2, "cols": 3, "values": [["1", "2", "3"], ["4", "5", "6"]]}]
    assert out["operation"] is None


def test_dos_matrices_con_signo_menos():
    tokens = grid([["1", "2"], ["3", "4"]]) + grid([["5", "6"], ["7", "8"]], x0=400)
    tokens.append(Token("-", 260, 45, 25, 8))  # entre las dos, a media altura
    out = tokens_to_matrices(tokens)
    assert [m["values"] for m in out["matrices"]] == [[["1", "2"], ["3", "4"]], [["5", "6"], ["7", "8"]]]
    assert out["operation"] == "subtract"


def test_dos_matrices_sin_signo_por_hueco():
    tokens = grid([["1", "2"], ["3", "4"]]) + grid([["5", "6"], ["7", "8"]], x0=500)
    out = tokens_to_matrices(tokens)
    assert len(out["matrices"]) == 2
    assert out["operation"] is None


def test_signo_negativo_separado_y_corchetes():
    tokens = grid([["1", "2"], ["3", "4"]], x0=100)
    tokens.append(Token("-", 70, 12, 20, 6))  # "- 1" leído en dos piezas
    tokens.append(Token("1", 40, -10, 15, 110))  # corchete leído como "1"
    out = tokens_to_matrices(tokens)
    assert out["matrices"][0]["values"] == [["-1", "2"], ["3", "4"]]


def test_celda_ilegible_queda_vacia():
    out = tokens_to_matrices(grid([["1", "2", "3"], ["4", None, "6"], ["7", "8", "9"]]))
    assert out["matrices"][0]["values"][1] == ["4", None, "6"]


def test_fila_junta_se_separa():
    parts = split_token(Token("3  -2  15", 100, 50, 90, 30))
    assert [p.text for p in parts] == ["3", "-2", "15"]
    assert parts[0].left < parts[1].left < parts[2].left


def test_corchetes_pegados():
    out = tokens_to_matrices(grid([["[1", "2]"], ["[3", "4]"]]))
    assert out["matrices"][0]["values"] == [["1", "2"], ["3", "4"]]
