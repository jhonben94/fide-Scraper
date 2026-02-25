# Despliegue

Guía para desplegar FIDE Scraper en producción.

## Requisitos

- Docker y Docker Compose
- PostgreSQL 16 (incluido en Docker)
- Acceso a internet para descargar datos de FIDE

## Despliegue con Docker

### 1. Levantar servicios

```bash
docker compose up -d
```

Esto levanta:

- **db**: PostgreSQL 16 en el puerto 5432
- **app**: API REST en el puerto 8000

### 2. Ejecutar importación inicial

```bash
docker compose up -d db
docker compose run --rm import
```

La primera importación puede tardar varios minutos (~45 MB de datos).

### 3. Verificar

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/players?limit=5"
```

## Producción

### Cambiar credenciales

Edita `docker-compose.yml` o usa un archivo `.env`:

```env
DATABASE_URL=postgresql://usuario:contraseña_segura@db:5432/fide
```

Y en el servicio `db`:

```yaml
environment:
  POSTGRES_USER: usuario
  POSTGRES_PASSWORD: contraseña_segura
  POSTGRES_DB: fide
```

### Volúmenes

Los volúmenes `pgdata` y `exports` persisten los datos:

- **pgdata**: Base de datos PostgreSQL
- **exports**: Archivos JSON/CSV exportados

### Actualización mensual

FIDE publica datos el último día de cada mes. Configura un cron para ejecutar el import el día 1:

```cron
0 2 1 * * cd /ruta/fide-Scraper && docker compose run --rm import
```

O con el perfil:

```cron
0 2 1 * * cd /ruta/fide-Scraper && docker compose --profile import run --rm import
```

### Escalabilidad

- **API**: Stateless. Puedes escalar horizontalmente con un load balancer.
- **DB**: PostgreSQL soporta conexiones concurrentes.
- **Import**: Ejecutar como job único (cron o similar). No paralelizar.

## Despliegue sin Docker

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. PostgreSQL

Necesitas PostgreSQL 16 en ejecución. Crea la base de datos:

```sql
CREATE DATABASE fide;
CREATE USER fide WITH PASSWORD 'tu_password';
GRANT ALL PRIVILEGES ON DATABASE fide TO fide;
```

### 3. Configurar

```bash
cp .env.example .env
# Editar .env con tu DATABASE_URL
```

### 4. Importar datos

```bash
python -m scripts.run_import
```

### 5. Levantar API

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

## Troubleshooting

### Error de conexión a la base de datos

- Verifica que PostgreSQL esté en ejecución.
- Comprueba `DATABASE_URL` (host, puerto, usuario, contraseña).
- Con Docker: asegúrate de que el servicio `db` esté healthy antes de `app`.

### Import no encuentra datos

- Verifica conectividad a `ratings.fide.com`.
- Comprueba que `FIDE_XML_URL` sea correcta.
- Para listas históricas, usa `--period YYYY-MM-DD`.

### API retorna 500

- Revisa los logs: `docker compose logs app`.
- Verifica que la importación se haya ejecutado al menos una vez.
- Comprueba que las tablas existan: `init_db` se ejecuta al arrancar.
