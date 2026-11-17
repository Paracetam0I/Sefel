# Rutas y nivel de protección

## Regla general
**Denegar por defecto**: toda ruta nueva requiere login, salvo que esté en la lista de rutas públicas de abajo y exista un motivo escrito aquí.

## Inventario

| Ruta | Método | Protección | Sin sesión |
|---|---|---|---|
| `/login` | GET, POST | Pública | Muestra el formulario |
| `/logout` | POST | Pública | Limpia la sesión y redirige a `/login` (con `?motivo=inactividad` muestra el aviso) |
| `/static/*` | GET | Pública | Sirve el archivo (el login necesita su CSS y JS) |
| `/` | GET | Login (`CurrentUser`) | Redirige a `/login` |
| `/dashboard` | GET | Login (`CurrentUser`); cada bloque de métricas solo para los roles con acceso a ese módulo | Redirige a `/login` |
| `/presupuestos` | GET | Rol de Presupuestos: `BUDGETS`, `BOTH`, `ADMIN`, `VIEWER` | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos` | POST | Rol de edición: `BUDGETS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 (VIEWER incluido) |
| `/presupuestos/nuevo` | GET | Rol de edición: `BUDGETS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/exportar` | GET | Rol de Presupuestos: `BUDGETS`, `BOTH`, `ADMIN`, `VIEWER` (selector del PDF) | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}/pdf` | GET | Rol de Presupuestos: `BUDGETS`, `BOTH`, `ADMIN`, `VIEWER`; 404 si no existe | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}/porcentajes` | GET | Rol de Presupuestos: `BUDGETS`, `BOTH`, `ADMIN`, `VIEWER` | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}/porcentajes` | POST | Rol de edición: `BUDGETS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}/editar` | GET | Rol de edición: `BUDGETS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}` | POST | Rol de edición: `BUDGETS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}/estado` | POST | Rol de edición: `BUDGETS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}/items/nuevo` | GET | Rol de edición: `BUDGETS`, `BOTH` o `ADMIN` (sin exclusividad por creador) | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}/items` | POST | Rol de edición: `BUDGETS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}/items/{item_id}` | POST | Rol de edición: `BUDGETS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/apu` | GET, POST | Rol de APU: `MATERIALS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/apu/nuevo` | GET | Rol de APU: `MATERIALS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/apu/{id}/editar` | GET | Rol de APU: `MATERIALS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/apu/{id}` | POST | Rol de APU: `MATERIALS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/apu/{id}/estado` | POST | Rol de APU: `MATERIALS`, `BOTH` o `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/admin/users` | GET, POST | Rol `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/admin/users/new` | GET | Rol `ADMIN` | Redirige a `/admin/users?nuevo=1` |
| `/admin/users/{id}` | POST | Rol `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/admin/users/{id}/estado` | POST | Rol `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/api/sesion/actividad` | POST | Login (`CurrentUser`); renueva la marca de actividad (204) | 401 en JSON con el motivo si venció por inactividad |
| `/api/saludo` | GET | Login (`getCurrentUser`) | 401 en JSON (HTMX: `HX-Redirect` a `/login`) |
| `/api/apu/buscar` | GET | Rol `ADMIN`, `BUDGETS` o `BOTH` | 401 en JSON; con otro rol, 403 en JSON |
| `/api/apu/{id}/autocompletar` | GET | Rol `ADMIN`, `BUDGETS` o `BOTH` (404 si el APU está inactivo) | 401 en JSON; con otro rol, 403 en JSON |
| `/protegido` | GET | Login (ruta de prueba) | Redirige a `/login` |
| `/prueba/solo-admin` | GET | Rol `ADMIN` (ruta de prueba) | Redirige a `/login`; con otro rol, 403 |
| `/prueba/presupuestos` | GET | Rol `ADMIN` o `BUDGETS` (ruta de prueba) | Redirige a `/login`; con otro rol, 403 |
| `/docs`, `/redoc`, `/openapi.json` | GET | Desactivadas | 404 |

## Cómo responde cada tipo de petición cuando falta la sesión o el permiso
- **Navegador:** sin sesión, redirección a `/login?next=...`; con rol insuficiente, página 403.
- **HTMX** (cabecera `HX-Request`): sin sesión, 401 con `HX-Redirect: /login`; con rol insuficiente, 403 en JSON.
- **API** (rutas bajo `/api/`): 401 en JSON sin sesión, y 403 en JSON con rol insuficiente.
- **Sesión vencida por inactividad (30 min):** igual que sin sesión, pero el login recibe `?motivo=inactividad` y muestra "Tu sesión se ha cerrado por inactividad." (API: el mensaje va en `detail`).

## Roles por módulo
Definidos en `app/core/permisos.py` (fuente única para routers y plantillas):

| Módulo | Roles |
|---|---|
| Usuarios (`/admin/users`) | `ADMIN` |
| APU | `MATERIALS`, `BOTH`, `ADMIN` |
| Presupuestos (ver y exportar) | `BUDGETS`, `BOTH`, `ADMIN`, `VIEWER` |
| Presupuestos (crear/editar) | `BUDGETS`, `BOTH`, `ADMIN` — cualquiera, sin exclusividad por creador |
| Dashboard | Todos los autenticados |

## Al agregar una ruta nueva
- Páginas internas: usar `CurrentUser`.
- Rutas por rol: usar los alias/tuplas de `app/core/permisos.py` (`requireRoles(*ROLES_APU)`, `UsuarioPresupuestosEdicion`, ...).
- Rutas bajo `/api/` y fragmentos HTMX: también llevan dependency de sesión.
- Si la ruta debe ser pública, agregarla a la tabla con el motivo.

## Test manual (sin sesión)
En una ventana privada nueva, abrir cada ruta del inventario:
- [x] Las protegidas redirigen a `/login`, salvo las `/api/`, que responden 401 en JSON.
- [x] `/docs`, `/redoc` y `/openapi.json` responden 404.
- [x] `/login` y `/static/css/output.css` son accesibles.
- [x] Con sesión de rol insuficiente, las rutas de rol muestran la página 403 (o JSON 403 bajo `/api/`).
- [x]Para comprobar que esta tabla coincide con las rutas reales de la app: `python -m scripts.listar_rutas`

## Pendiente
Las rutas `/protegido` y `/prueba/*` son de prueba y se eliminarán cuando existan las páginas reales. Las rutas de administración usan `requireRoles(UserRole.ADMIN)`.