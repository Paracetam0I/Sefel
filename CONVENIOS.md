## Nombres
- variables → snake_case: mi_variable
- constantes → UPPER_SNAKE_CASE: MI_CONSTANTE
- funciones → camelCase: miFuncion()
- clases → PascalCase: MiClase
- modelos → PascalCase singular: Usuario
- tablas BD → snake_case plural: usuarios
- archivos → snake_case: mi_archivo.py
- carpetas → snake_case: mi_carpeta
- rutas API/URL → kebab-case: /api/mi-ruta
- ramas Git → tipo/descripcion-corta: feature/login-usuario

## Ramas Git
- main → versión estable
- feature/nombre-corto → nueva funcionalidad
- tests/nombre-corto → pruebas
- bugfix/nombre-corto → corrección
- hotfix/nombre-corto → arreglo urgente
- docs/nombre-corto → documentación

## Reglas generales
- Sin espacios, tildes ni ñ en archivos, carpetas ni ramas.
- No mezclar mayúsculas y minúsculas en el mismo nombre.
- Cualquier cambio a estos convenios se hace por Pull Request y se actualiza este archivo.

## Dinero y cantidades

- **Siempre `Decimal`, nunca `float`.** Un `float` no puede guardar `0.1` con exactitud y el error se acumula al sumar. `toDecimal()` (en `app/services/calculations.py`) rechaza los `float` con un error.
- **Moneda: peso chileno (CLP), sin centavos.** Los subtotales y totales se redondean a pesos enteros; el valor está en una sola constante, `DECIMALES_MONEDA`.
- **Política de redondeo: half-up** (0.5 sube a 1, 2.5 sube a 3), como una calculadora o Excel. Se redondea **una sola vez**, en el subtotal de cada ítem; el total es la suma de subtotales ya redondeados.
- **Los cálculos viven en `app/services/calculations.py`** (`calculate_item_subtotal`, `calculate_budget_total`). Las plantillas y las rutas muestran el resultado: no calculan ni redondean por su cuenta.
- **En la base de datos** (SQLite no tiene `Decimal`): se usa el tipo `DecimalText` (`app/core/money.py`), que guarda el valor como texto. **Nunca se suma ni se ordena dinero en SQL** (`SUM`, `ORDER BY`, `>`), porque SQL vería texto: se hace en Python.
- **Formularios:** se acepta coma o punto decimal, hasta 2 decimales, sin negativos.