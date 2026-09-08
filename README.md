# VEMO — Consolidated Executive Summary

Dashboard consolidado de FP&A de VEMO, generado a partir de los dashboards públicos de cada
negocio (DAE, VEMO Impulso/LTO, EV Fleets, VCN).

- **Sitio publicado:** https://vemo-fp-a.github.io/Consolidated_fpa/
- **Última actualización de datos:** Julio 2026 (se actualiza a mano volviendo a correr el
  script de extracción cuando los 4 dashboards individuales tengan un mes nuevo).
- **`index.html` es el único archivo que hace falta abrir** — CSS, JS y datos van todos
  incrustados ahí adentro.
- **`scripts/build.py` es el único script que hace falta correr** — descarga los 4 dashboards,
  extrae los datos y regenera `index.html`, todo en un solo comando. `scripts/logos/` son los
  logos que incrusta.

## Qué muestra

Para cada empresa:
- Logo y nombre.
- Las tarjetas KPI **reales** de su propio Executive Summary nativo (las mismas que en su
  dashboard individual — operativas/comerciales, no financieras genéricas): p.ej. Performance
  Ratio/Supply Hours/Utilization/Trips/Fleet/OOS para DAE; EPC Sales/Backlog/Pipeline/ZEE
  vehicles para EV Fleets; Installed Capacity/Connectors/Utilization/Revenue per kWh para VCN;
  Gross Portfolio/Active Fleet/Originación/Default Rate para VEMO Impulso.
- **KPI Trend** — un gráfico de línea por empresa, con selector desplegable para elegir cuál de
  sus KPIs graficar, checkbox de Presupuesto (línea punteada) y Run-Rate (proyección a 3 meses).
- Botón directo al dashboard completo de esa empresa.

Al final, una sección de **Consolidated P&L** con la suma agregada de las 4 empresas, en el mismo
formato de tabla que usan los P&L de los dashboards individuales (Actuals / Budget / Deviation $ /
Deviation %), con las líneas: Revenues (net of interco), COGS + Opex, Normalized Gross Profit,
Gross Margin, SG&A, Normalized EBITDA, EBITDA Margin, D&A, EBIT, Net Interest, EBT, Taxes,
Normalized Net Income, Net Margin.

Los **Actuals** de esta tabla se leen directamente del archivo oficial
`VEMO 2026 Consolidated Financials FV.xlsx` (carpeta `2026`, junto a `db bl`), hoja
**"Board Outputs"**, bloque **"Normalized"** — el mismo P&L consolidado, ya con eliminaciones
intercompañía, que usa el board. Si ese archivo no está disponible al correr el script (por
ejemplo desde otra máquina sin el OneDrive sincronizado), cae automáticamente a sumar los P&L de
los 4 dashboards individuales (sin eliminaciones) y lo indica en el pie de la tabla. El **Budget**
de esta sección sí es la suma de los 4 dashboards, ya que el archivo oficial no trae presupuesto
consolidado.

Todo el sitio (incluido este texto en pantalla) está en inglés — el UI de cada tarjeta reproduce
el formato de los dashboards individuales (etiqueta, valor, variación MoM, VS BUDGET, sparkline
con Actuals/Budget y rango de fechas).

## Cómo actualizar

1. Los 4 dashboards de origen (`DAE_BoardD`, `LTO_BoardD`, `EV_BoardD`, `VCN_BoardD` en
   `github.com/VEMO-FP-A`) se actualizan primero con el mes nuevo (flujo normal de cada uno,
   vía `update_dashboard.py`/`.bat`), y el archivo `VEMO 2026 Consolidated Financials FV.xlsx`
   también debe tener el mes nuevo cargado en su hoja "Board Outputs".
2. Se corre `python scripts/build.py` (requiere `pip install openpyxl` para leer el Excel) —
   descarga el `index.html` de cada uno, extrae el objeto `const D` embebido, lee el Consolidated
   P&L del Excel oficial, arma `consolidated_data.json` y regenera el `index.html` final, todo en
   un solo paso.
3. Se hace commit y push a este repo (rama `main`) — GitHub Pages lo publica solo. Correr
   `build.py` NO hace push por sí solo.

## Dashboards individuales

- [DAE](https://vemo-fp-a.github.io/DAE_BoardD/)
- [VEMO Impulso](https://vemo-fp-a.github.io/LTO_BoardD/)
- [EV Fleets](https://vemo-fp-a.github.io/EV_BoardD/)
- [VCN](https://vemo-fp-a.github.io/VCN_BoardD/)
