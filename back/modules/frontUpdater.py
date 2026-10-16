import os
import time
import webview

def obtener_ultima_modificacion(carpeta):
    max_mtime = 0
    for root, carpetas, archivos in os.walk(carpeta):
        for archivo in archivos:
            ruta_completa = os.path.join(root, archivo)
            try:
                mtime = os.path.getmtime(ruta_completa)
                if mtime > max_mtime:
                    max_mtime = mtime
            except Exception:
                pass
    return max_mtime

# Modificamos la función para que reciba 'carpeta_front' como segundo argumento
def vigilar_html(ventana, carpeta_front):
    ultima_modificacion = obtener_ultima_modificacion(carpeta_front)
    while True:
        if not webview.windows or ventana not in webview.windows:
            print("🚪 Ventana cerrada. Deteniendo vigilante de archivos...")
            break
        time.sleep(1)
        try:
            modificacion_actual = obtener_ultima_modificacion(carpeta_front)
            if modificacion_actual != ultima_modificacion:
                ultima_modificacion = modificacion_actual
                print("🔄 Cambios detectados en la carpeta front. Recargando ventana...")
                ventana.evaluate_js('window.location.reload(true)')
        except Exception:
            pass