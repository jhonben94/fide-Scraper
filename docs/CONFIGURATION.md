# Configuración

Todas las opciones se configuran mediante variables de entorno.

## Variables

| Variable | Tipo | Default | Descripción |
|----------|------|---------|-------------|
| `DATABASE_URL` | str | `postgresql://fide:fide@localhost:5432/fide` | URL de conexión PostgreSQL |
| `FIDE_XML_URL` | str | `https://ratings.fide.com/download/standard_rating_list_xml.zip` | URL de descarga del XML |
| `EXPORT_PATH` | str | `data/exports` | Directorio para exportaciones JSON/CSV |
| `LOG_LEVEL` | str | `INFO` | Nivel de log (DEBUG, INFO, WARNING, ERROR) |

## Archivo .env

Copia `.env.example` a `.env` y ajusta los valores:

```bash
cp .env.example .env
```

Ejemplo:

```env
# Base de datos PostgreSQL
DATABASE_URL=postgresql://fide:fide@localhost:5432/fide

# URL de descarga FIDE (ver https://ratings.fide.com/download_lists.phtml)
# Opciones: standard_rating_list_xml.zip, players_list_xml.zip, rapid_rating_list_xml.zip, blitz_rating_list_xml.zip
FIDE_XML_URL=https://ratings.fide.com/download/standard_rating_list_xml.zip

# Directorio para exportaciones
EXPORT_PATH=data/exports

# Nivel de log
LOG_LEVEL=INFO
```

## Docker

En `docker-compose.yml` las variables se definen por servicio:

- **app**: API REST
- **import**: Job de importación

Para producción, sobrescribe las variables con un archivo `.env` o con secrets de tu plataforma.

## Listas históricas

Para descargar una lista de un mes concreto, usa el parámetro `period` en la URL:

```
https://ratings.fide.com/download/players_list_xml.zip?period=2024-12-01
```

En el script de importación:

```bash
python -m scripts.run_import --period 2024-12-01
```
