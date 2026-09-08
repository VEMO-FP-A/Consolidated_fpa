# VEMO — Consolidated Executive Summary

Dashboard consolidado de FP&A de VEMO, generado a partir de los dashboards públicos de cada
negocio (DAE, VEMO Impulso/LTO, EV Fleets, VCN).

- **Sitio publicado:** https://vemo-fp-a.github.io/Consolidated_fpa/
- **Última actualización de datos:** Julio 2026 (se actualiza a mano volviendo a correr el
  script de extracción cuando los 4 dashboards individuales tengan un mes nuevo).
- **`index.html` es el único archivo que hace falta abrir** — CSS, JS y datos van todos
  incrustados ahí adentro. Todo lo demás en esta carpeta (`scripts/`) es solo la herramienta
  para regenerarlo cada mes; no son páginas para ver.

## Qué muestra

Para cada empresa:
- Logo y nombre.
- Mini KPI cards con las métricas principales (Revenue, EBITDA, EBITDA Margin, Utilidad Neta
  para DAE/EV Fleets/VCN; Ingreso Operativo Neto, Utilidad Neta, Cartera Neta y ROE para VEMO
  Impulso, que es un negocio financiero de leasing y no reporta EBITDA de forma nativa).
- Toggle YTD 2026 / Mes actual, con variación vs. presupuesto.
- Gráfico mensual (Revenue/Ingreso vs. EBITDA/Utilidad Neta), Ene-2025 a la fecha.
- Botón directo al dashboard completo de esa empresa.

Al final, una sección de **P&L Consolidado — Conciliación** con la suma agregada de las 4
empresas línea por línea (Revenue, Opex, Utilidad Bruta, SG&A, EBITDA, D&A, EBIT, Gastos
Financieros, EBT, Impuestos, Utilidad Neta).

## Cómo actualizar

1. Los 4 dashboards de origen (`DAE_BoardD`, `LTO_BoardD`, `EV_BoardD`, `VCN_BoardD` en
   `github.com/VEMO-FP-A`) se actualizan primero con el mes nuevo (flujo normal de cada uno,
   vía `update_dashboard.py`/`.bat`).
2. Se corre, en orden, `python scripts/build_data.py` (descarga el `index.html` de cada uno,
   extrae el objeto `const D` embebido y arma `consolidated_data.json`) y luego
   `python scripts/build.py` (regenera el único `index.html` final, con todo incrustado).
3. Se hace commit y push a este repo (rama `main`) — GitHub Pages lo publica solo.

## Dashboards individuales

- [DAE](https://vemo-fp-a.github.io/DAE_BoardD/)
- [VEMO Impulso](https://vemo-fp-a.github.io/LTO_BoardD/)
- [EV Fleets](https://vemo-fp-a.github.io/EV_BoardD/)
- [VCN](https://vemo-fp-a.github.io/VCN_BoardD/)
