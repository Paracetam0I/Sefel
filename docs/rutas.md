# Rutas y nivel de protección

## Regla general
**Denegar por defecto**: toda ruta nueva requiere login, salvo que esté en la lista de rutas públicas de abajo y exista un motivo escrito aquí.

## Inventario

| Ruta | Método | Protección | Sin sesión |
|---|---|---|---|
| `/login` | GET, POST | Pública | Muestra el formulario |
| `/logout` | POST | Pública | Limpia la sesión y redirige a `/login` |
| `/static/*` | GET | Pública | Sirve el archivo (el login necesita su CSS y JS) |
| `/` | GET | Login (`CurrentUser`) | Redirige a `/login` |
| `/dashboard` | GET | Login (`CurrentUser`) | Redirige a `/login` |
| `/presupuestos` | GET, POST | Login (`CurrentUser`) | Redirige a `/login` |
| `/presupuestos/nuevo` | GET | Login (`CurrentUser`) | Redirige a `/login` |
| `/presupuestos/{id}/editar` | GET | Login (`CurrentUser`) | Redirige a `/login` |
| `/presupuestos/{id}` | POST | Login (`CurrentUser`) | Redirige a `/login` |
| `/presupuestos/{id}/estado` | POST | Login (`CurrentUser`) | Redirige a `/login` |
| `/presupuestos/{id}/items` | GET, POST | Rol `ADMIN`, `BUDGETS` o `BOTH`, y presupuesto propio | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}/items/nuevo` | GET | Rol `ADMIN`, `BUDGETS` o `BOTH`, y presupuesto propio | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}/items/{item_id}/editar` | GET | Rol `ADMIN`, `BUDGETS` o `BOTH`, y presupuesto propio | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}/items/{item_id}` | POST | Rol `ADMIN`, `BUDGETS` o `BOTH`, y presupuesto propio | Redirige a `/login`; con otro rol, 403 |
| `/presupuestos/{id}/items/{item_id}/eliminar` | POST | Rol `ADMIN`, `BUDGETS` o `BOTH`, y presupuesto propio | Redirige a `/login`; con otro rol, 403 |
| `/apu` | GET, POST | Login (`CurrentUser`) | Redirige a `/login` |
| `/apu/nuevo` | GET | Login (`CurrentUser`) | Redirige a `/login` |
| `/apu/{id}/editar` | GET | Login (`CurrentUser`) | Redirige a `/login` |
| `/apu/{id}` | POST | Login (`CurrentUser`) | Redirige a `/login` |
| `/apu/{id}/estado` | POST | Login (`CurrentUser`) | Redirige a `/login` |
| `/admin/users` | GET, POST | Rol `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/admin/users/new` | GET | Rol `ADMIN` | Redirige a `/admin/users?nuevo=1` |
| `/admin/users/{id}` | POST | Rol `ADMIN` | Redirige a `/login`; con otro rol, 403 |
| `/admin/users/{id}/estado` | POST | Rol `ADMIN` | Redirige a `/login`; con otro rol, 403 |
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

## Al agregar una ruta nueva
- Páginas internas: usar `CurrentUser`.
- Rutas por rol: `Depends(requireRoles(UserRole.X, ...))`.
- Rutas bajo `/api/` y fragmentos HTMX: también llevan dependency de sesión.
- Si la ruta debe ser pública, agregarla a la tabla con el motivo.

## Test manual (sin sesión)
En una ventana privada nueva, abrir cada ruta del inventario:
- [x] Las protegidas redirigen a `/login`, salvo las `/api/`, que responden 401 en JSON.
- [x] `/docs`, `/redoc` y `/openapi.json` responden 404.
- [x] `/login` y `/static/css/output.css` son accesibles.
- [x] Con sesión de rol insuficiente, las rutas de rol muestran la página 403 (o JSON 403 bajo `/api/`).

Para comprobar que esta tabla coincide con las rutas reales de la app: `python -m scripts.listar_rutas`

## Pendiente
Las rutas `/protegido` y `/prueba/*` son de prueba y se eliminarán cuando existan las páginas reales. Las rutas de administración usan `requireRoles(UserRole.ADMIN)`.