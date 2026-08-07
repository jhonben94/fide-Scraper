# Despliegue

Guía para desplegar FIDE Scraper en producción.

## Requisitos

- Docker y Docker Compose
- PostgreSQL 16 (incluido en Docker)
- Acceso a internet para descargar datos de FIDE

## Despliegue con Docker

Por defecto los datos viven en la **misma base `clubsync` que el backend**, esquema **`fide`** (migración Flyway `V6__fide_scraper_schema.sql`).

### 1. Levantar servicios (monorepo, recomendado)

Desde la **raíz** del monorepo SquareOne:

```bash
docker compose up -d postgres fide-scraper
```

- **postgres**: PostgreSQL 16 en el host `5432`
- **fide-scraper**: API en el puerto **8000**, `DATABASE_URL` → `clubsync@postgres:5432/clubsync`

### 1b. Solo desde `fide-Scraper/` (red compartida)

Primero levantá Postgres con el compose raíz. Luego, en esta carpeta:

```bash
docker compose up -d app
```

(`docker-compose.yml` aquí usa la red externa `squareone_default` para resolver el host `postgres`.)

### 2. Ejecutar importación inicial

Desde la raíz del monorepo:

```bash
docker compose --profile fide-import run --rm fide-import
```

O desde `fide-Scraper/`:

```bash
docker compose --profile fide-import run --rm import
```

La primera importación puede tardar varios minutos (~45 MB de datos).

### 3. Verificar

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/players?limit=5"
# Si configuraste FIDE_SCRAPER_API_KEY:
curl -H "X-API-Key: tu_clave" "http://localhost:8000/players?limit=5"
```

Desde **SquareOne** (Quarkus), `GET /api/fide/scraper/health` (rol `federation_admin` / `super_admin`) llama al `/health` del scraper usando `SQUAREONE_FIDE_SCRAPER_URL` y opcionalmente `SQUAREONE_FIDE_SCRAPER_API_KEY`.

### Producción / stack completo (`backend/deploy/compose.yaml`)

Incluye `fide-scraper` y la misma base `clubsync`. Las tablas `fide.players` y `fide.player_rating_history` las crea **Flyway** del backend; el scraper hace `create_all` idempotente si hace falta.

```bash
cd backend && docker compose -f deploy/compose.yaml --env-file deploy/.env up -d --build
```

Importación puntual:

```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env --profile fide-import run --rm fide-import
docker compose -f deploy/compose.yaml --env-file deploy/.env --profile fide-import-history run --rm fide-import-history
```

Si antes importabas en otra base (p. ej. `fide` aislada en el puerto 5433), los datos no se migran solos al esquema `fide` de `clubsync`; hace falta un `INSERT INTO fide.players ... SELECT ...` explícito si querés conservarlos.

## Producción

### Cambiar credenciales

Usá las mismas credenciales que el backend (`POSTGRES_*` / `DB_*`) y apuntá el scraper a esa instancia:

```env
DATABASE_URL=postgresql://usuario:contraseña_segura@postgres:5432/clubsync
```

### Volúmenes

- **postgres_data** (compose raíz / deploy): datos PostgreSQL
- **fide_exports** / **exports**: exportaciones JSON/CSV del scraper

### Actualización: snapshot mensual + sincronización diaria

Tres jobs con roles distintos, pensados para correr juntos, no uno en reemplazo del otro:

- **Catálogo vigente diario** (`fide-import`): alimenta `fide.players` — nombre, título, rating
  actual. Es lo que sostiene el **ranking en vivo** (la vista por defecto, sin `asOf`) y la ficha
  de jugador. Corré esto **todos los días**: si solo corre el mes 1, el ranking en vivo queda
  desactualizado el resto del mes aunque el historial (abajo) esté al día.
- **Sincronización diaria de historial** (`fide-daily-sync`): descarga los ZIP *actuales* de FIDE
  y solo escribe en `fide.player_rating_history` las filas donde el rating realmente cambió desde
  la última corrida (incluida la baja explícita a NULL si un jugador deja de figurar en una
  modalidad). No genera una fila por jugador por día — el volumen queda acotado a cambios
  reales — y es lo que mantiene frescos "Subidas del mes", "Nuevos rankeados" y el gráfico de
  Trayectoria. Corré esto todos los días también.
- **Snapshot mensual denso** (`fide-import-history`, sin `use_current_files`): deja una fila por
  jugador por calendario-mes en `fide.player_rating_history` — es lo que sostiene el selector de
  "ver el ranking de tal mes" en el sitio público. Esto sí alcanza con **una vez al mes**: no
  compite con el daily-sync (conviven en la misma tabla, ver
  [ARCHITECTURE.md](ARCHITECTURE.md#frecuencia-de-actualización-fide-y-estrategia-de-almacenamiento)).

```cron
# Catálogo vigente (fide.players) + sincronización de historial — todos los días
0 3 * * * cd /ruta/al/repo && docker compose --profile fide-import run --rm fide-import
0 4 * * * cd /ruta/al/repo && docker compose --profile fide-daily-sync run --rm fide-daily-sync

# Snapshot mensual denso (selector de mes histórico) — día 1
0 2 1 * * cd /ruta/al/repo && docker compose --profile fide-import-history run --rm fide-import-history
```

O desde `fide-Scraper/` (con Postgres del compose raíz ya en marcha):

```cron
0 3 * * * cd /ruta/al/repo/fide-Scraper && docker compose --profile fide-import run --rm import
0 4 * * * cd /ruta/al/repo/fide-Scraper && docker compose --profile fide-daily-sync run --rm fide-daily-sync
0 2 1 * * cd /ruta/al/repo/fide-Scraper && docker compose --profile fide-import-history run --rm fide-import-history
```

Sin acceso al host (solo la URL pública del scraper desplegado), el equivalente vía API son
[`scripts/trigger_daily_import_remote.sh`](../scripts/trigger_daily_import_remote.sh) y
[`scripts/trigger_daily_sync_remote.sh`](../scripts/trigger_daily_sync_remote.sh) — mismo par,
pensados para pegar en un scheduler externo (Coolify/Dokploy "Create Schedule", Jenkins, cron).

Si un día se salta alguno de los crons diarios, no pasa nada grave: `fide-daily-sync` no depende
de "el día anterior" sino del último valor conocido en la base, así que la corrida siguiente
captura igual todos los cambios acumulados; `fide-import` simplemente deja el catálogo un día más
desactualizado hasta la próxima corrida (upsert, sin pérdida de datos).

### Trigger remoto desde Jenkins (sin `docker compose run`)

Si usás un pipeline Jenkins por HTTP, podés disparar los jobs administrativos:

```bash
# Import mensual/base
curl -sS -X POST "https://tu-scraper/admin/import" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${FIDE_SCRAPER_API_KEY}" \
  -d '{"export_json": true, "export_csv": true}'

# Import histórico (24 meses)
curl -sS -X POST "https://tu-scraper/admin/import-history" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${FIDE_SCRAPER_API_KEY}" \
  -d '{"months": 24}'

# Solo ciertos FIDE ID (checkpoint estable; requiere Flyway V9 en la BD para VARCHAR(128) en history_import_checkpoint)
curl -sS -X POST "https://tu-scraper/admin/import-history" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${FIDE_SCRAPER_API_KEY}" \
  -d '{"months": 12, "period_scope": "rolling_months", "skip_completed": true, "fide_ids": [123456, 789012]}'

# Sincronización diaria basada en cambios
curl -sS -X POST "https://tu-scraper/admin/sync-daily" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${FIDE_SCRAPER_API_KEY}" \
  -d '{"countries": ["PAR"]}'
```

**skip_completed vs reproceso:** si `skip_completed` está activo y el checkpoint marca un periodo como listo pero faltan filas (borrado manual o error parcial), ejecutá el job con `skip_completed: false` o borrá las filas correspondientes en `fide.history_import_checkpoint` antes de relanzar.

Consultar estado:

```bash
curl -sS -H "X-API-Key: ${FIDE_SCRAPER_API_KEY}" \
  "https://tu-scraper/admin/jobs/<job_id>"
```

Seguridad recomendada:
- `FIDE_SCRAPER_API_KEY` obligatoria para `/admin/*`.
- `FIDE_SCRAPER_ADMIN_ALLOWLIST` con IP(s)/CIDR(s) de Jenkins.
- `FIDE_SCRAPER_TRUST_FORWARDED_FOR=true` si estás detrás de proxy/reverse proxy.

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

Usá la misma instancia PostgreSQL que el backend SquareOne (base típica **`clubsync`**). El esquema **`fide`** y los permisos para el usuario de la app deben existir (arranque del backend con Flyway, o equivalente).

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
- Con Docker: asegúrate de que el servicio `postgres` del compose raíz esté healthy antes del scraper o de los jobs de import.

### Import no encuentra datos

- Verifica conectividad a `ratings.fide.com`.
- Comprueba que `FIDE_XML_URL` sea correcta.
- Para listas históricas, usa `--period YYYY-MM-DD`.

### API retorna 500

- Revisa los logs: `docker compose logs app`.
- Verifica que la importación se haya ejecutado al menos una vez.
- Comprueba que las tablas existan: `init_db` se ejecuta al arrancar.
