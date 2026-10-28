# Catálogo de proveedores

Aplicación de escritorio en Rust para Windows 11. Muestra una casilla por proveedor y cuenta **Tengo / Me faltan / Total**.

## Descargar el EXE sin compilarlo

1. Abrir la pestaña **Actions** de este repositorio.
2. Entrar en la última ejecución correcta de **Compilar Windows**.
3. Descargar el archivo **Catalogo-Proveedores-Windows** en *Artifacts*.
4. Extraer el ZIP, dejando **catalogo-proveedores.exe** y **proveedores.json** en la misma carpeta.
5. Abrir el EXE. No necesita servidor ni conexión.

Si todavía no aparece ninguna ejecución, revisar que GitHub Actions esté habilitado en el repositorio.

## Editar la lista de proveedores

**Archivo principal: [proveedores.json](proveedores.json).** Es una lista JSON de cadenas de texto, editable en GitHub o con cualquier editor:

~~~json
[
  "Pragmatic",
  "Endorphina",
  "Playtech"
]
~~~

Agregar o quitar elementos respetando comas y comillas. Los duplicados se filtran automáticamente (ignorando diferencias de mayúsculas, espacios y alias básicos).

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
cargo test
cargo build --release
.\target\release\catalogo-proveedores.exe
~~~

O ejecutar **compilar-windows.bat**, que genera una carpeta **dist** con el ejecutable y catálogo.

## Archivos

- [proveedores.json](proveedores.json): lista de proveedores, editable sin recompilar.
- [src/main.rs](src/main.rs): interfaz, búsqueda, filtros, casillas y persistencia.
- [.github/workflows/windows.yml](.github/workflows/windows.yml): compilación automática para Windows.
- [compilar-windows.bat](compilar-windows.bat): compilación local.

No se conecta a una API: cada casilla se marca manualmente.
