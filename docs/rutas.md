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
| `/api/saludo` | GET | Login (`getCurrentUser`) | 401 en JSON (HTMX: `HX-Redirect` a `/login`) |
| `/protegido` | GET | Login (ruta de prueba) | Redirige a `/login` |
| `/prueba/solo-admin` | GET | Rol `ADMIN` (ruta de prueba) | Redirige a `/login`; con otro rol, 403 |
| `/prueba/presupuestos` | GET | Rol `ADMIN` o `BUDGETS` (ruta de prueba) | Redirige a `/login`; con otro rol, 403 |
| `/docs`, `/redoc`, `/openapi.json` | GET | Desactivadas | 404 |

## Cómo responde cada tipo de petición cuando falta la sesión
- **Navegador:** redirección a `/login?next=...`.
- **HTMX** (cabecera `HX-Request`): respuesta 401 con `HX-Redirect: /login`.
- **API** (rutas bajo `/api/`): 401 en JSON.

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
- [x] Con sesión de rol insuficiente, las rutas de rol muestran la página 403.

## Pendiente
Las rutas `/protegido` y `/prueba/*` son de prueba y se eliminarán cuando existan las páginas reales. Aún no hay rutas de administración reales: cuando existan, deben usar `requireRoles(UserRole.ADMIN)`.