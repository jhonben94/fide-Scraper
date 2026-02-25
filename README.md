# fide-Scraper

Scraper que descarga los datos oficiales XML de la [FIDE](https://www.fide.com/) (Federación Internacional de Ajedrez), los procesa, los almacena en PostgreSQL y permite exportación a JSON/CSV. Dockerizado para despliegue en producción.

**Documentación completa**: [docs/](docs/README.md)

## Requisitos

- Python 3.12+
- PostgreSQL 16 (o usar Docker)

## Instalación local

```bash
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tu DATABASE_URL
```

## Uso con Docker

### Levantar servicios (API + base de datos)

```bash
docker compose up -d
```

La API estará disponible en `http://localhost:8000`. Documentación en `http://localhost:8000/docs`.

### Ejecutar importación

Construye todas las imágenes y ejecuta el import:

```bash
docker compose build
docker compose up -d db
docker compose run --rm import
```

**Importante**: Ejecuta `docker compose build` (o `docker compose build import`) antes del primer import para asegurar que la imagen tenga el código actualizado.

### Importación manual (sin Docker)

```bash
python -m scripts.run_import
```

Opciones:

- `--period YYYY-MM-DD`: Lista histórica de esa fecha
- `--no-json`: No exportar a JSON
- `--no-csv`: No exportar a CSV

### Importar historial (para Progress)

**Importante:** Ejecuta `docker compose build` antes si acabas de añadir o modificar archivos.

```bash
# Reconstruir imagen (necesario si run_import_history es nuevo)
docker compose build

# Importar últimos 24 meses
docker compose run --rm import_history

# O con meses personalizados
docker compose run --rm import_history python -m scripts.run_import_history --months 12
```

## API REST

| Endpoint | Descripción |
|----------|-------------|
| `GET /health` | Health check |
| `GET /players` | Lista jugadores (paginación, filtros) |
| `GET /players/{fideid}` | Perfil completo (datos, rankings, foa_title) |
| `GET /players/{fideid}/calculations?opponent_rating=1800` | Cálculos de rating (K-factor, puntuación esperada) |
| `GET /players/{fideid}/progress?months=24` | Evolución del rating en el tiempo |
| `GET /players/{fideid}/stats` | Estadísticas W/D/L por color (Total, Standard, Rapid, Blitz) |

**Progress** requiere ejecutar antes: `python -m scripts.run_import_history --months 24`

Parámetros de `GET /players`:

- `skip`, `limit`: Paginación
- `country`: Código federación (ej: ESP, USA)
- `min_rating`: Rating mínimo

## Estructura del proyecto

```
fide-Scraper/
├── src/
│   ├── config.py       # Configuración
│   ├── downloader.py   # Descarga XML FIDE
│   ├── parser.py      # Parseo XML
│   ├── models.py      # Modelo Player
│   ├── database.py    # Conexión DB
│   ├── importer.py    # Pipeline completo
│   ├── exporter.py    # Export JSON/CSV
│   ├── data/          # Mapeos (país-continente)
│   ├── services/      # Rankings, calculations, progress
│   ├── scrapers/      # Cliente API estadísticas FIDE
│   └── api/           # FastAPI
├── scripts/
│   ├── run_import.py       # CLI importación
│   └── run_import_history.py  # Import historial (Progress)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Actualización mensual

FIDE publica datos el último día de cada mes. Para actualizar automáticamente, configura un cron:

```cron
0 2 1 * * cd /ruta/fide-Scraper && docker compose run --rm import
```

## Documentación

| Documento | Descripción |
|-----------|-------------|
| [Arquitectura](docs/ARCHITECTURE.md) | Diseño del sistema y componentes |
| [API REST](docs/API.md) | Endpoints y ejemplos |
| [Configuración](docs/CONFIGURATION.md) | Variables de entorno |
| [Despliegue](docs/DEPLOYMENT.md) | Docker y producción |

## Licencia

Apache 2.0
