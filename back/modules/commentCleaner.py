import re

def limpiar_comentarios(texto):
    """
    Elimina los comentarios del código fuente preservando los saltos de línea 
    para no desfasar el reporte de errores del parser.
    """
    if not texto:
        return texto

    # 1. Limpiar comentarios multilínea: /* ... */
    # Usamos una función lambda para reemplazar todo el bloque por la misma 
    # cantidad de saltos de línea (\n) que contenía originalmente.
    texto = re.sub(r'/\*[\s\S]*?\*/', lambda m: '\n' * m.group(0).count('\n'), texto)
    
    # 2. Limpiar comentarios de una sola línea: // ...
    # Eliminamos desde el // hasta el final de la línea.
    texto = re.sub(r'//.*', '', texto)
    
    return texto