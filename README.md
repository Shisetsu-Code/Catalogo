# Catálogo de proveedores

Aplicación de escritorio en Rust para Windows 11. Muestra una casilla por proveedor y cuenta **Tengo / Me faltan / Total**.

## Descargar el EXE sin compilarlo

1. Abrir la pestaña **Actions** de este repositorio.
2. Entrar en la última ejecución correcta de **Compilar Windows**.
3. Descargar el archivo **Catalogo-Proveedores-Windows** en *Artifacts*.
4. Extraer el ZIP, dejando **catalogo-proveedores.exe**, **proveedores.json** y la carpeta **logos** juntos.
5. Abrir el EXE. No necesita servidor ni conexión.

Si todavía no aparece ninguna ejecución, revisar que GitHub Actions esté habilitado en el repositorio.

## Editar la lista de proveedores

**Archivo principal: [proveedores.json](proveedores.json).** Es una lista de objetos JSON. Cada proveedor tiene un `id` estable, su `name` comercial y su `domain` para obtener la miniatura. Se puede editar directamente en GitHub:

~~~json
[
  {"id": "pragmatic", "name": "Pragmatic Play", "domain": "pragmaticplay.com"},
  {"id": "endorphina", "name": "Endorphina", "domain": "endorphina.com"},
  {"id": "playtech", "name": "Playtech", "domain": "playtech.com"}
]
~~~

Agregar o quitar objetos respetando comas y comillas. **No cambies el `id` al corregir un nombre:** identifica la casilla guardada. Para agregar un proveedor nuevo, podés omitir el `id`; la app lo generará automáticamente. El campo opcional `logo_url` permite indicar una URL HTTPS de imagen propia (PNG/JPG). También siguen funcionando catálogos antiguos formados por una lista de nombres.

- Al cambiarlo desde GitHub, el archivo queda actualizado en el repositorio. Para utilizarlo localmente, reemplazar **proveedores.json** junto al ejecutable y pulsar **Recargar catálogo**. **No hace falta recompilar**.
- También se pueden añadir o quitar proveedores desde la interfaz; esas operaciones modifican el archivo local **proveedores.json**.
- La versión inicial incluye **42 proveedores únicos**; se omitieron las repeticiones de Wazdan, ELA Games y Spinometal.
- Las marcas no están dentro del catálogo: editar la lista no borra las casillas previamente seleccionadas.

**Importante:** GitHub y tu copia local son independientes. Para sincronizarlas, reemplazá la copia de proveedores.json al lado del EXE.

## Guardado y privacidad

Los checks se guardan automáticamente en:

- Windows: **%APPDATA%\ProveedoresChecklist\estado.json**.
- Linux: **$XDG_CONFIG_HOME/catalogo-proveedores/estado.json** o **~/.config/catalogo-proveedores/estado.json**.

El archivo privado **estado.json** no se sube al repositorio. Si existe un estado antiguo, se intenta importar desde el viejo archivo **%APPDATA%\ProveedoresChecklist\proveedores.json**.

El botón **Exportar CSV** genera un CSV para Excel en la misma carpeta del estado.

## Compilar en Windows

Con Rust instalado:

~~~powershell
cargo test --locked
cargo build --release --locked
.\target\release\catalogo-proveedores.exe
~~~

O ejecutar **compilar-windows.bat**, que genera una carpeta **dist** con el ejecutable y catálogo.

## Archivos

- [proveedores.json](proveedores.json): lista de proveedores, editable sin recompilar.
- [src/main.rs](src/main.rs): interfaz, búsqueda, filtros, casillas y persistencia.
- [.github/workflows/windows.yml](.github/workflows/windows.yml): compilación automática para Windows.
- [compilar-windows.bat](compilar-windows.bat): compilación local.

No se conecta a una API: cada casilla se marca manualmente.

## Preparar miniaturas en una compilación local

```powershell
python -m pip install pillow
python scripts/fetch_logos.py
cargo build --release --locked
```

La CI de Windows realiza estos pasos automáticamente e incluye todos los PNG en el ZIP. Los logos son favicons de los sitios indicados en el catálogo, no necesariamente los logotipos completos oficiales. Donde no se pudo obtener favicon, se muestra una miniatura con iniciales, sin inventar la marca. La app no hace solicitudes de red al abrirse; funciona sin conexión con la carpeta `logos/`.

## Dependencias y actualizaciones

Versiones revisadas el 28 de octubre de 2026:

| Componente | Versión |
|---|---|
| eframe / egui | 0.37.0 |
| serde | 1.0.229 |
| serde_json | 1.0.154 |
| image | 0.25.10 |
| Pillow (generación de logos) | 13.0.0 |
| actions/checkout | 7.0.1 |
| actions/upload-artifact | 7.0.2 |
| Swatinem/rust-cache | 2.9.3 |
| rustc | stable (se instala con rustup en GitHub Actions) |

Las dependencias directas Rust están declaradas en `Cargo.toml`; el archivo `Cargo.lock` congela las transitivas. `requirements-build.txt` fija Pillow. GitHub Actions ejecuta `cargo test --locked` y `cargo build --release --locked`. Dependabot está configurado para comprobar semanalmente las actualizaciones disponibles en Cargo, pip y GitHub Actions: genera propuestas de cambio, que deben revisarse antes de incorporarlas.
