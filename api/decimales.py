from decimal import Decimal, ROUND_HALF_UP

DECIMALES = 1
_PASO = Decimal(1).scaleb(-DECIMALES)      # 0.1


def redondear(valor):
    """Devuelve el valor como float con un decimal (None se queda como None)."""
    if valor is None:
        return None
    if valor != valor:                      # NaN: no hay nada que redondear
        return None
    if abs(valor) >= 1e15:                  # valor absurdo: no se redondea, el rango físico lo rechaza
        return float(valor)
    redondeado = Decimal(str(valor)).quantize(_PASO, rounding=ROUND_HALF_UP)
    return float(redondeado) + 0.0          # el + 0.0 evita el "-0.0"


def texto(valor):
    """Texto con un decimal para el LCD ('25.5'), o '--' si no hay valor."""
    v = redondear(valor)
    return "--" if v is None else f"{v:.{DECIMALES}f}"