# Comparación de juegos SlotCatalog + SlotsTemple

Extracción automática de los 12 estudios solicitados: 3 Oaks, BGaming, ELK Studios, Endorphina, Hacksaw Gaming, KA Gaming, NetEnt, Nolimit City, Play'n GO, Playson, Playtech y Pragmatic Play.

## Descargar los resultados

- **CSV consolidado:** `data/slot-compare/juegos_unicos.csv` (solo existe después de una extracción verificada).
- **CSV bruto:** `data/slot-compare/juegos_por_fuente.csv` (solo después de una extracción verificada).
- **Informe de la primera ejecución, fallida por acceso:** [reporte.json](data/slot-compare/reporte.json).
- **Historial y ZIP descargable:** [GitHub Actions — Comparar catalogos SlotCatalog y SlotsTemple](https://github.com/Shisetsu-Code/Catalogo/actions/workflows/slot-compare.yml).

El CSV aparece en el repositorio **solo después de una ejecución con cobertura verificada**. Si el rastreo se corta, consultá el artifact de esa ejecución y `reporte.json` antes de considerar el resultado completo.

El workflow se ejecuta manualmente, cuando cambia el scraper, y los lunes. Usa GitHub Actions con Python y Chromium/Playwright; **no ejecuta las demos**, solamente enumera fichas de catálogos públicos.

## Campos principales

`proveedor`, `juego`, `nombre_normalizado`, `slotcatalog_url`, `slotstemple_url`, `fuentes`, `estado`.

La unión se realiza por **proveedor + nombre normalizado**. No mezcla versiones diferentes del mismo juego (por ejemplo, `1000`, `Megaways`, `Christmas`). Una colisión de URLs dentro de la misma fuente aparece en `colisiones.csv`. La lista puede incluir juegos no tragamonedas si los catálogos de origen los incluyen; no se inventan tipos o estados.

## Cobertura y límites

Ambos sitios pueden bloquear automatización, variar según región, cargar fichas mediante JavaScript o mostrar listas incompletas. **No interpretar un resultado parcial como inventario exhaustivo.** El campo `complete` por fuente indica si se detectaron errores de navegación o faltantes frente al contador anunciado. `all_complete` solo refleja esas verificaciones, no certifica que los sitios publiquen todos sus juegos históricos. Las peticiones son secuenciales, con demora y sin eludir bloqueos de acceso.

## Estado de la primera ejecución (2026-11-01)

GitHub Actions recibió **HTTP 403 de SlotCatalog para los 12 proveedores** y **HTTP 403 de SlotsTemple para 11 proveedores**. Para el único catálogo accesible inicialmente (3 Oaks) se detectaron enlaces ajenos al proveedor: **82 enlaces frente a 29 juegos anunciados**. Esos datos fueron retirados del repositorio porque no eran fiables. El validador ahora rechaza contaminaciones y hace fallar el workflow cuando falta cobertura. No hay un CSV completo descargable de ambas fuentes hasta que los sitios permitan la lectura desde GitHub Actions o se utilice un método autorizado de acceso/datos.
