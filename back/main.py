import sys
import os
import json 
import re  

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(DIR_ACTUAL, "lib"))

import webview
from lark import Lark, LarkError
from lark.exceptions import UnexpectedCharacters, UnexpectedToken, UnexpectedEOF 
from modules.frontUpdater import vigilar_html
from modules.commentCleaner import limpiar_comentarios

CARPETA_FRONT = os.path.join(DIR_ACTUAL, "..", "front")
ARCHIVO_HTML = os.path.join(CARPETA_FRONT, "index.html")
ARCHIVO_CONFIG = os.path.join(DIR_ACTUAL, "..", "config.json")

class Api:
    def _tree_to_dict(self, tree):
        if not hasattr(tree, 'data'):
            return {"type": "token", "value": str(tree)}
        children = []
        for child in tree.children:
            if child is None:
                continue
            if isinstance(child, str):
                children.append({"type": "token", "value": str(child)})
            else:
                children.append(self._tree_to_dict(child))
        return {"type": "rule", "name": str(tree.data), "children": children}

    def __init__(self):
        self.gramatica_path = ""
        self.ultimo_mtime_bnf = 0
        self.ultimo_contenido_bnf = ""
        if os.path.exists(ARCHIVO_CONFIG):
            try:
                with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                    self.gramatica_path = datos.get("bnf_path", "")
                    if self.gramatica_path and os.path.exists(self.gramatica_path):
                        self.ultimo_mtime_bnf = os.path.getmtime(self.gramatica_path)
                        with open(self.gramatica_path, "r", encoding="utf-8") as bf:
                            self.ultimo_contenido_bnf = bf.read()
            except Exception:
                pass

    def seleccionar_archivo(self):
        ventana = webview.active_window()
        archivos = ventana.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=('Archivos BNF (*.bnf)', 'Todos los archivos (*.*)'))
        if archivos and len(archivos) > 0:
            self.gramatica_path = archivos[0]
            try:
                self.ultimo_mtime_bnf = os.path.getmtime(self.gramatica_path)
                with open(self.gramatica_path, "r", encoding="utf-8") as bf:
                    self.ultimo_contenido_bnf = bf.read()
            except Exception:
                pass
            with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
                json.dump({"bnf_path": self.gramatica_path}, f)
            return {"ok": True, "ruta": self.gramatica_path}
        return {"ok": False}

    def obtener_ruta_actual(self):
        return self.gramatica_path

    # Comprueba si el archivo BNF ha cambiado realmente en disco
    def comprobar_cambios_bnf(self):
        if not self.gramatica_path or not os.path.exists(self.gramatica_path):
            return {"hay_cambios": False}
        try:
            mtime = os.path.getmtime(self.gramatica_path)
            if mtime != self.ultimo_mtime_bnf:
                with open(self.gramatica_path, "r", encoding="utf-8") as f:
                    contenido = f.read()
                self.ultimo_mtime_bnf = mtime
                if contenido != self.ultimo_contenido_bnf:
                    self.ultimo_contenido_bnf = contenido
                    return {"hay_cambios": True}
        except Exception:
            pass
        return {"hay_cambios": False}

    # NUEVO: Recibe 'regla_inicio' desde JavaScript
    def validar(self, texto, regla_inicio="start"):
        if not self.gramatica_path or not os.path.exists(self.gramatica_path):
            return {"archivo_ok": False, "status": "error", "error_detallado": "Selecciona un archivo.", "reglas": []}
            
        try:
            with open(self.gramatica_path, "r", encoding="utf-8") as f:
                gramatica_cruda = f.read()
            try:
                self.ultimo_mtime_bnf = os.path.getmtime(self.gramatica_path)
                self.ultimo_contenido_bnf = gramatica_cruda
            except Exception:
                pass
            
            # 1. Extraemos todas las reglas automáticamente buscando <nombre> ::=
            reglas = re.findall(r'<([\w-]+)>\s*::=', gramatica_cruda)
            reglas_disponibles = list(dict.fromkeys(reglas)) # Eliminar duplicados
            
            if not reglas_disponibles:
                reglas_disponibles = ["start"]
            
            # Si la regla solicitada no existe, usamos la primera por defecto
            if regla_inicio not in reglas_disponibles:
                regla_inicio = reglas_disponibles[0]
                
            gramatica_lark = gramatica_cruda.replace("::=", ":")
            gramatica_lark = re.sub(r'<([\w-]+)>', r'\1', gramatica_lark)
            
            # 2. Compilamos Lark indicando que inicie donde el usuario eligió y preservando todos los tokens
            parser = Lark(gramatica_lark, start=regla_inicio, keep_all_tokens=True)
            mensaje_archivo = f"✅ Cargado: {os.path.basename(self.gramatica_path)}"
            
        except Exception as e:
            return {"archivo_ok": False, "status": "error", "error_detallado": f"Error al compilar:\n{str(e)}", "reglas": []}

        # Construimos el diccionario base que siempre devolveremos
        # Construimos el diccionario base que siempre devolveremos
        respuesta_base = {
            "archivo_ok": True,
            "mensaje_archivo": mensaje_archivo,
            "reglas": reglas_disponibles,
            "regla_actual": regla_inicio
        }

        # --- APLICAMOS EL LIMPIADOR AQUÍ ---
        texto_limpio = limpiar_comentarios(texto)

        # Usamos texto_limpio en lugar de texto
        if not texto_limpio.strip():
            return {**respuesta_base, "status": "vacio", "error_detallado": ""}

        try:
            # Parseamos el texto sin comentarios
            ast_tree = parser.parse(texto_limpio)
            return {**respuesta_base, "status": "valido", "error_detallado": "", "ast": self._tree_to_dict(ast_tree)}
            
        except UnexpectedCharacters as e:
            esperados = [str(t).replace("'", "").replace('"', '') for t in getattr(e, 'allowed', [])]
            # Pasamos texto_limpio a get_context para que el error muestre la línea correcta sin el comentario
            return {**respuesta_base, "status": "invalido", "error_detallado": f"❌ Símbolo no reconocido en línea {e.line}, columna {e.column}.\n\n{e.get_context(texto_limpio)}"}
            
        except UnexpectedEOF as e:
            esperados = []
            if hasattr(e, 'expected'):
                try:
                    exp_set = e.expected if isinstance(e.expected, (list, set)) else e.expected()
                    esperados = [str(t).replace("'", "").replace('"', '') for t in exp_set]
                except Exception: pass
            
            sug = f"\n\nSe esperaba: {', '.join(esperados[:5]) + ('...' if len(esperados)>5 else '')}" if esperados else ""
            return {**respuesta_base, "status": "invalido", "error_detallado": f"⚠️ La instrucción está incompleta.{sug}"}
            
        except UnexpectedToken as e:
            esperados = [str(t).replace("'", "").replace('"', '') for t in getattr(e, 'expected', [])]
            sug = f"\nSe esperaba: {', '.join(esperados[:5])}" if esperados else ""
            return {**respuesta_base, "status": "invalido", "error_detallado": f"❌ Símbolo fuera de lugar: '{e.token}' en línea {e.line}.\n\n{e.get_context(texto_limpio)}{sug}"}
            
        except LarkError as e:
            return {**respuesta_base, "status": "invalido", "error_detallado": f"Error de sintaxis:\n{str(e)}"}

if __name__ == "__main__":
    api = Api()
    ventana = webview.create_window(title="Validador BNF", url=ARCHIVO_HTML, js_api=api, width=900, height=650)
    webview.start(vigilar_html, args=(ventana, CARPETA_FRONT))