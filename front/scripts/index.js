let debounceTimer;
let reglaSeleccionada = "start"; // Por defecto iniciamos con start
let reglasCacheadas = "";        // Para saber si debemos redibujar los botones
let ultimoASTJSON = "";          // Para evitar redibujados innecesarios y parpadeos
let ultimoStatus = "";

window.addEventListener('pywebviewready', async function() {
    const textArea = document.getElementById('textContainer');

    // Valida automáticamente al escribir con un pequeño debounce
    textArea.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(validarTexto, 120);
    });

    const ruleSelector = document.getElementById('ruleSelector');
    if (ruleSelector) {
        ruleSelector.addEventListener('wheel', function(e) {
            if (e.deltaY !== 0) {
                e.preventDefault();
                ruleSelector.scrollLeft += e.deltaY;
            }
        });
    }

    validarTexto();
    iniciarVigilanteArchivoBNF();
});

async function seleccionarArchivoBNF() {
    const respuesta = await pywebview.api.seleccionar_archivo();
    if (respuesta.ok) {
        ultimoASTJSON = "";
        ultimoStatus = "";
        validarTexto();
    }
}

// Función que ejecuta Python
async function validarTexto() {
    const textArea = document.getElementById('textContainer');
    const errorBox = document.getElementById('errorBox');
    const astContainer = document.getElementById('astContainer');
    
    // Le enviamos a python el texto Y LA REGLA que queremos probar
    const data = await pywebview.api.validar(textArea.value, reglaSeleccionada);

    actualizarEstadoVisual(textArea, data.status);
    
    // 1. DIBUJAR LOS BOTONES DE REGLAS (Solo si cambiaron)
    const reglasString = JSON.stringify(data.reglas);
    if (data.reglas && reglasString !== reglasCacheadas) {
        reglasCacheadas = reglasString;
        dibujarBotonesReglas(data.reglas, data.regla_actual);
    }
    
    // 2. MOSTRAR ERRORES Y AST
    const astInspector = document.getElementById('astInspector');
    if (data.status === 'invalido' || data.status === 'error') {
        errorBox.textContent = data.error_detallado || "Error en la validación.";
        errorBox.style.display = "block";
        if (ultimoStatus !== data.status) {
            astContainer.innerHTML = '<p style="color: #ce0000; font-style: italic;">Sintaxis inválida.</p>';
            if (astInspector) astInspector.innerHTML = '<span style="color: #ce0000;">Error en sintaxis</span>';
            ultimoASTJSON = "";
            ultimoStatus = data.status;
        }
    } else {
        errorBox.style.display = "none";
        if (data.status === 'valido' && data.ast) {
            const nuevoASTJSON = JSON.stringify(data.ast);
            // Solo redibujar si el AST realmente cambió, evitando que la interfaz "palpite"
            if (nuevoASTJSON !== ultimoASTJSON || ultimoStatus !== 'valido') {
                ultimoASTJSON = nuevoASTJSON;
                ultimoStatus = 'valido';
                astContainer.innerHTML = ''; 
                const nodoRenderizado = renderizarAST(data.ast);
                if (nodoRenderizado) {
                    astContainer.appendChild(nodoRenderizado);
                } else {
                    astContainer.innerHTML = '<span class="ast-token" style="color: gray;">(Regla vacía ε)</span>';
                }
                if (astInspector) astInspector.innerHTML = '<span style="color: #666; font-style: italic;">Pasa el mouse sobre una letra o regla...</span>';
            }
        } else if (data.status === 'vacio') {
            if (ultimoStatus !== 'vacio') {
                ultimoStatus = 'vacio';
                ultimoASTJSON = "";
                astContainer.innerHTML = '<p style="color: gray; font-style: italic;">Esperando texto...</p>';
                if (astInspector) astInspector.innerHTML = '<span style="color: #666; font-style: italic;">Sin selección</span>';
            }
        }
    }
}

// Función para cambiar de regla cuando el usuario hace clic en un botón
function cambiarRegla(nuevaRegla) {
    if (reglaSeleccionada === nuevaRegla) return;
    reglaSeleccionada = nuevaRegla;
    
    // Actualizamos las clases visuales de los botones
    document.querySelectorAll('.rule-btn').forEach(btn => {
        if (btn.dataset.rule === nuevaRegla) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Forzamos una validación inmediata con la nueva regla
    ultimoASTJSON = "";
    ultimoStatus = "";
    validarTexto();
}

// Dibuja los botones en la barra superior
function dibujarBotonesReglas(reglas, reglaActual) {
    const contenedor = document.getElementById('ruleSelector');
    contenedor.innerHTML = ''; // Limpiamos

    reglas.forEach(regla => {
        const btn = document.createElement('button');
        btn.className = `rule-btn ${regla === reglaActual ? 'active' : ''}`;
        btn.textContent = `<${regla}>`;
        btn.dataset.rule = regla; // Guardamos el nombre internamente
        
        btn.onclick = () => cambiarRegla(regla);
        contenedor.appendChild(btn);
    });
}

function actualizarEstadoVisual(elemento, estado) {
    elemento.classList.remove('valid', 'wrong', 'pBorder');
    if (estado === 'valido') elemento.classList.add('valid');
    else if (estado === 'invalido' || estado === 'error') elemento.classList.add('wrong');
    else elemento.classList.add('pBorder');
}

// Vigilante periódico que comprueba si el archivo BNF fue modificado en disco
function iniciarVigilanteArchivoBNF() {
    setInterval(async () => {
        try {
            if (window.pywebview && pywebview.api && pywebview.api.comprobar_cambios_bnf) {
                const res = await pywebview.api.comprobar_cambios_bnf();
                if (res && res.hay_cambios) {
                    // Solo si realmente hubo cambios en el archivo, se fuerzan la recompilación y redibujado
                    ultimoASTJSON = "";
                    reglasCacheadas = "";
                    ultimoStatus = "";
                    validarTexto();
                }
            }
        } catch (e) {
            // Manejo silencioso en caso de cierre de ventana
        }
    }, 1000);
}

// Función auxiliar para determinar si un nodo o alguno de sus hijos contiene tokens
function tieneTokens(nodo) {
    if (nodo.type === 'token') return true;
    if (!nodo.children || nodo.children.length === 0) return false;
    return nodo.children.some(tieneTokens);
}

// Dibujante del Árbol Sintáctico (AST Horizontal)
function renderizarAST(nodo, caminoReglas = []) {
    const inspector = document.getElementById('astInspector');

    if (nodo.type === 'token') {
        const span = document.createElement('span');
        span.className = 'ast-token';
        let valor = nodo.value;
        if (valor === '\n') valor = '↵';
        else if (valor.trim() === '') valor = '·'; 
        span.textContent = valor;
        
        // Obtener la regla inmediata que contiene este token
        const reglaPadre = caminoReglas.length > 0 ? caminoReglas[caminoReglas.length - 1] : 'token';
        span.setAttribute('data-tooltip', `<${reglaPadre}>`);

        // Eventos de hover para revelar la regla y jerarquía
        span.addEventListener('mouseenter', (e) => {
            e.stopPropagation();
            if (inspector) {
                const ruta = caminoReglas.map(r => `<${r}>`).join(' ➔ ');
                inspector.innerHTML = `<span>Valor: <b style="background:#fff; color:#000; padding:1px 6px; border-radius:3px;">${valor}</b></span> <span>Regla: <b style="color:#00e676;">&lt;${reglaPadre}&gt;</b></span> <span>Jerarquía: <span style="color:#64b5f6;">${ruta}</span></span>`;
            }
        });

        span.addEventListener('mouseleave', () => {
            if (inspector) {
                inspector.innerHTML = '<span style="color: #666; font-style: italic;">Pasa el mouse sobre una letra o regla...</span>';
            }
        });

        return span;
    }
    
    // Si la regla no contiene ningún token descendiente (derivación vacía ε), omitir contenedor vacío
    if (!tieneTokens(nodo)) {
        return null;
    }

    const div = document.createElement('div');
    div.className = 'ast-rule';
    div.setAttribute('data-rule', nodo.name);
    div.title = `<${nodo.name}>`;

    const nuevoCamino = [...caminoReglas, nodo.name];

    div.addEventListener('mouseenter', (e) => {
        e.stopPropagation();
        if (inspector) {
            const ruta = nuevoCamino.map(r => `<${r}>`).join(' ➔ ');
            inspector.innerHTML = `<span>Contenedor de Regla: <b style="color:#8bc34a;">&lt;${nodo.name}&gt;</b></span> <span>Jerarquía: <span style="color:#64b5f6;">${ruta}</span></span>`;
        }
    });

    div.addEventListener('mouseleave', () => {
        if (inspector) {
            inspector.innerHTML = '<span style="color: #666; font-style: italic;">Pasa el mouse sobre una letra o regla...</span>';
        }
    });
    
    const childrenContainer = document.createElement('div');
    childrenContainer.className = 'ast-children';
    for (const hijo of nodo.children) {
        const elementoHijo = renderizarAST(hijo, nuevoCamino);
        if (elementoHijo) {
            childrenContainer.appendChild(elementoHijo);
        }
    }
    div.appendChild(childrenContainer);
    return div;
}