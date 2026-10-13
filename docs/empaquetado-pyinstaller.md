# Empaquetado de SEFEL con PyInstaller

## Objetivo
Empaquetar la aplicación mínima de SEFEL en un ejecutable de Windows.

## Configuración
El archivo `build.spec` define la configuración de PyInstaller.

Recursos incluidos:
- `app/static` → `static`
- `app/templates` → `templates`

Se recopilan submódulos de Uvicorn, FastAPI, Starlette y Jinja2.

## Comando de compilación

```powershell
python -m PyInstaller --noconfirm --workpath .\build_fresh --distpath .\dist_fresh .\build.spec
```

El ejecutable generado se encuentra en `dist_fresh\MiApp.exe`.

## Problemas encontrados y soluciones

### Error de permisos con --clean
Se produjo un `PermissionError: [WinError 5]` al eliminar archivos de compilaciones anteriores.

**Solución:** compilar sin `--clean` y utilizar directorios separados para el trabajo y la salida.

### Inclusión de recursos
PyInstaller no incluye automáticamente todos los templates y archivos estáticos.

**Solución:** declararlos en `datas` dentro de `build.spec`.

### Dependencias ocultas
Se recopilan submódulos de Uvicorn, FastAPI, Starlette y Jinja2, además de algunos módulos específicos de Uvicorn.

## Estado de las pruebas
- [x] Existe `build.spec`.
- [x] La sintaxis de `build.spec` es válida.
- [x] PyInstaller generó `dist_fresh\MiApp.exe`.
- [ ] Confirmar la apertura de la ventana con el ejecutable de la compilación final.
- [ ] Probar SQLite y otras dependencias dentro del ejecutable cuando se integren.

## Limitaciones conocidas
SQLite y `passlib` todavía no se han validado dentro del ejecutable. La configuración de PyWebView y sus hooks deberá revisarse si aparecen problemas al distribuir la aplicación en otros equipos.
