# Comparación de juegos SlotCatalog + SlotsTemple

Extracción automática de los 12 estudios solicitados: 3 Oaks, BGaming, ELK Studios, Endorphina, Hacksaw Gaming, KA Gaming, NetEnt, Nolimit City, Play'n GO, Playson, Playtech y Pragmatic Play.

## Descargar los resultados

- **CSV consolidado:** [juegos_unicos.csv](data/slot-compare/juegos_unicos.csv) — un registro por proveedor y título normalizado, con enlaces a ambas fuentes.
- **CSV bruto:** [juegos_por_fuente.csv](data/slot-compare/juegos_por_fuente.csv) — un registro por URL encontrada.
- **Informe de cobertura:** [reporte.json](data/slot-compare/reporte.json).
- **Historial y ZIP descargable:** [GitHub Actions — Comparar catalogos SlotCatalog y SlotsTemple](https://github.com/Shisetsu-Code/Catalogo/actions/workflows/slot-compare.yml).

El CSV aparece en el repositorio **después de la primera ejecución exitosa**. Si el rastreo se corta, consultá el artifact de esa ejecución y `reporte.json` antes de considerar el resultado completo.

El workflow se ejecuta manualmente, cuando cambia el scraper, y los lunes. Usa GitHub Actions con Python y Chromium/Playwright; **no ejecuta las demos**, solamente enumera fichas de catálogos públicos.

## Campos principales

`proveedor`, `juego`, `nombre_normalizado`, `slotcatalog_url`, `slotstemple_url`, `fuentes`, `estado`.

La unión se realiza por **proveedor + nombre normalizado**. No mezcla versiones diferentes del mismo juego (por ejemplo, `1000`, `Megaways`, `Christmas`). Una colisión de URLs dentro de la misma fuente aparece en `colisiones.csv`. La lista puede incluir juegos no tragamonedas si los catálogos de origen los incluyen; no se inventan tipos o estados.

## Cobertura y límites

Ambos sitios pueden bloquear automatización, variar según región, cargar fichas mediante JavaScript o mostrar listas incompletas. **No interpretar un resultado parcial como inventario exhaustivo.** El campo `complete` por fuente indica si se detectaron errores de navegación o faltantes frente al contador anunciado. `all_complete` solo refleja esas verificaciones, no certifica que los sitios publiquen todos sus juegos históricos. Las peticiones son secuenciales, con demora y sin eludir bloqueos de acceso.
