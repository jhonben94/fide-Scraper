# Configuración

Todas las opciones se configuran mediante variables de entorno.

## Variables

| Variable | Tipo | Default | Descripción |
|----------|------|---------|-------------|
| `DATABASE_URL` | str | `postgresql://clubsync:clubsync@localhost:5435/clubsync` | Misma BD que el backend; tablas FIDE en esquema `fide` (Flyway V6) |
| `FIDE_XML_URL` | str | `https://ratings.fide.com/download/players_list_xml.zip` | Lista **combinada** STD+RPD+BLZ (misma familia que la web FIDE; ~48 MB) |
| `FIDE_SCRAPER_API_KEY` | str | *(vacío)* | Si está definida, la API exige el mismo valor en header `X-API-Key` |
| `FIDE_SCRAPER_ADMIN_ALLOWLIST` | str | *(vacío)* | Allowlist para `/admin/*` (IPs/CIDRs separados por coma). Vacío: solo API key |
| `FIDE_SCRAPER_TRUST_FORWARDED_FOR` | bool | `true` | Si está en `true`, usa el primer `X-Forwarded-For` para la allowlist |
| `EXPORT_PATH` | str | `data/exports` | Directorio para exportaciones JSON/CSV |
| `LOG_LEVEL` | str | `INFO` | Nivel de log (DEBUG, INFO, WARNING, ERROR) |
| `FIDE_HISTORY_COUNTRY_CODES` | str | *(vacío)* | CSV de códigos FIDE para `scripts.run_import_history` cuando no pasás `--country` (ej. `PAR`) |
| `FIDE_HISTORY_PERIOD_SCOPE` | str | `rolling_months` | `current_year` o `rolling_months` si no usás `--current-year` / `--period-scope` en CLI |
| `FIDE_HISTORY_INCLUDE_CLUB_AFFILIATES` | bool | `false` | Si es `true`, también incluye jugadores con club asignado en tabla `player` (OR con `FIDE_HISTORY_COUNTRY_CODES`) |

## Archivo .env

Copia `.env.example` a `.env` y ajusta los valores:

```bash
cp .env.example .env
```

Ejemplo:

```env
DATABASE_URL=postgresql://clubsync:clubsync@localhost:5435/clubsync
FIDE_XML_URL=https://ratings.fide.com/download/players_list_xml.zip
# FIDE_SCRAPER_API_KEY=opcional_para_proteger_la_API
FIDE_SCRAPER_ADMIN_ALLOWLIST=203.0.113.10/32
FIDE_SCRAPER_TRUST_FORWARDED_FOR=true
EXPORT_PATH=data/exports
LOG_LEVEL=INFO
```

Para Jenkins sobre dominio público:
- Definí `FIDE_SCRAPER_API_KEY` y enviala en `X-API-Key`.
- Definí `FIDE_SCRAPER_ADMIN_ALLOWLIST` con la(s) IP(s) pública(s) de Jenkins.

## Docker

En la **raíz del monorepo**, `docker-compose.yml` incluye `postgres` y `fide-scraper` apuntando a la misma BD `clubsync` (esquema `fide`).

En `fide-Scraper/docker-compose.yml` (solo esta carpeta) la API usa la red externa `squareone_default`: levantá antes Postgres con el compose raíz.

- **app**: API REST
- **import** / **import_history**: jobs (perfiles `fide-import` / `fide-import-history`)

Para producción, sobrescribe las variables con un archivo `.env` o con secrets de tu plataforma.

## Versión de imagen Docker (fide-scraper)

El tag de la imagen `jhonybenitez/squareone-fide-scraper:<tag>` se toma del archivo **`VERSION`** en la raíz de `fide-Scraper/` (una línea, p. ej. `1.0.0`). Actualizalo al publicar releases.

## Listas históricas

El historial mensual usa la página de archivo FIDE (`a_download.php`); el importador lo resuelve automáticamente. Para el import de lista combinada puntual:

```bash
python -m scripts.run_import --period 2024-12-01
```
