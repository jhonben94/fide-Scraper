# API REST

Documentación de la API REST de FIDE Scraper.

**Base URL**: `http://localhost:8000` (por defecto)

**Documentación interactiva**: `http://localhost:8000/docs`.

---

## Endpoints

### Health check

```http
GET /health
```

Verifica que el servicio está disponible.

**Respuesta**

```json
{
  "status": "ok"
}
```

---

### Trigger import mensual/base (admin)

```http
POST /admin/import
X-API-Key: <secret>
Content-Type: application/json
```

Dispara importación en background y devuelve un `job_id`.

Body opcional:

```json
{
  "period": "2025-01-01",
  "export_json": true,
  "export_csv": true,
  "countries": ["PAR"]
}
```

- `countries`: opcional; lista de códigos FIDE (ej. solo Paraguay: `["PAR"]`). Sin el campo se importan todas las federaciones. No combinar con `fide_ids`.

Respuesta (`202 Accepted`):

```json
{
  "job_id": "f6a8b8f0d5834a73b0a8a52fc2f8a53d",
  "type": "import",
  "status": "queued"
}
```

Errores:
- `401` API key inválida o ausente
- `403` IP fuera de allowlist
- `409` ya hay un import en ejecución

---

### Trigger import histórico (admin)

```http
POST /admin/import-history
X-API-Key: <secret>
Content-Type: application/json
```

Body:

```json
{
  "months": 24,
  "period_scope": "rolling_months",
  "period": null,
  "use_current_files": false,
  "countries": ["PAR"],
  "include_club_affiliates": false,
  "skip_completed": false
}
```

- `period_scope`: `rolling_months` (usa `months`) o `current_year` (enero → mes actual del año en curso).
- `period`: opcional; fecha YYYY-MM-DD (obligatoriamente primer día del mes). Si se proporciona, solo se importa ese período y `months`/`period_scope` se ignoran.
- `use_current_files`: solo válido si se proporciona `period`. Si es `true`, descarga los ZIP XML actuales (`standard_rating_list_xml.zip`, `rapid_rating_list_xml.zip`, `blitz_rating_list_xml.zip`) y los persiste como el período indicado. Útil cuando FIDE publica anticipadamente la lista del mes siguiente.
- `countries`: opcional; lista de códigos FIDE (ej. solo Paraguay: `["PAR"]`). Sin el campo se importan todas las federaciones.
- `include_club_affiliates`: si es `true`, también incluye jugadores con club asignado (OR con `countries`).
- `skip_completed`: si es `true`, no vuelve a descargar/parsear periodos ya registrados en `fide.history_import_checkpoint` **para la misma clave de filtro** (`countries`/club o hash de `fide_ids`).
- `fide_ids`: opcional; lista de FIDE ID enteros (máx. 50000). Si se envía no vacía, **solo** se persisten esos jugadores; **no** debe combinarse con `countries` ni `include_club_affiliates` (la API devuelve error de validación). La clave de checkpoint es estable (`fides:<sha256>` del conjunto ordenado), así que el mismo listado + `skip_completed: true` reanuda sin repetir periodos ya hechos.

**Validaciones:**
- `period` debe ser el primer día del mes (YYYY-MM-01). Si no, devuelve error 422.
- `use_current_files: true` requiere `period`. Si no, devuelve error 422.

**Ejemplo: importar snapshot de julio 2026 usando archivos actuales (publicados anticipadamente el 29/06/2026):**

```json
{
  "period": "2026-07-01",
  "use_current_files": true,
  "countries": ["PAR"],
  "include_club_affiliates": true,
  "skip_completed": false
}
```

**Ejemplo: importar un período histórico específico (junio 2026) desde el archivo FIDE:**

```json
{
  "period": "2026-06-01",
  "use_current_files": false,
  "countries": ["PAR"],
  "skip_completed": false
}
```

**Ejemplo solo listado FIDE:**

```json
{
  "months": 12,
  "period_scope": "rolling_months",
  "skip_completed": true,
  "fide_ids": [123456, 789012]
}
```

**Recuperación tras borrar filas en `player_rating_history` o fallos parciales:** el checkpoint puede seguir marcando el periodo como completo. Opciones: ejecutar con `skip_completed: false` para forzar reproceso (los upserts repueblan huecos), o borrar las filas correspondientes en `fide.history_import_checkpoint` para ese `filter_key` (ver campo `filter_key` en la respuesta del job) y volver a lanzar con `skip_completed: true`.

**Nota sobre caches de consultas:** `latest-rating-snapshot` puede tardar hasta 30 minutos en reflejar nuevos snapshots, agregados 15 minutos e históricos hasta 60 minutos.

Respuesta (`202 Accepted`): igual formato que `/admin/import`, con `"type": "import-history"`.

---

### Estado de job (admin)

```http
GET /admin/jobs/{job_id}
X-API-Key: <secret>
```

Devuelve estado del job: `queued`, `running`, `success` o `failed`.

---

### Listar jugadores

```http
GET /players
```

Lista jugadores con paginación y filtros opcionales.

**Parámetros de consulta**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `skip` | int | 0 | Jugadores a saltar (paginación) |
| `limit` | int | 50 | Máximo jugadores (1-500) |
| `country` | str | - | Código federación (ej: ESP, USA) |
| `min_rating` | int | - | Rating mínimo (0-3000) |

**Ejemplos**

```bash
# Primeros 50 jugadores
curl "http://localhost:8000/players"

# Página 2 (saltar 50)
curl "http://localhost:8000/players?skip=50&limit=50"

# Jugadores españoles
curl "http://localhost:8000/players?country=ESP"

# Jugadores con rating >= 2500
curl "http://localhost:8000/players?min_rating=2500"

# Combinado: españoles con rating >= 2400
curl "http://localhost:8000/players?country=ESP&min_rating=2400&limit=100"
```

**Respuesta**

```json
{
  "total": 50,
  "skip": 0,
  "limit": 50,
  "players": [
    {
      "fideid": 1503014,
      "name": "Carlsen, Magnus",
      "country": "NOR",
      "sex": "M",
      "title": "g",
      "rating": 2830,
      "games": 120,
      "rapid_rating": 2840,
      "rapid_games": 45,
      "blitz_rating": 2850,
      "blitz_games": 60,
      "birthday": 1990,
      "flag": null
    }
  ]
}
```

---

### Obtener jugador por ID (perfil completo)

```http
GET /players/{fideid}
```

Obtiene un jugador por su ID FIDE con perfil completo: datos personales, ratings, títulos (FIDE, FOA) y rankings (mundial, nacional, continental).

**Parámetros de ruta**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `fideid` | int | ID único FIDE del jugador |

**Ejemplo**

```bash
curl "http://localhost:8000/players/1503014"
```

**Respuesta**

```json
{
  "fideid": 1503014,
  "name": "Carlsen, Magnus",
  "country": "NOR",
  "sex": "M",
  "title": "g",
  "foa_title": null,
  "rating": 2830,
  "games": 120,
  "rapid_rating": 2840,
  "rapid_games": 45,
  "blitz_rating": 2850,
  "blitz_games": 60,
  "birthday": 1990,
  "flag": null,
  "rankings": {
    "world": {"rank_active": 1, "rank_all": 1, "total_active": 200000, "total_all": 537407},
    "national": {"rank_active": 1, "rank_all": 1, "total_active": 5000, "total_all": 8000},
    "continent": {"rank_active": 1, "rank_all": 1, "total_active": 50000, "total_all": 80000}
  }
}
```

**Errores**

| Código | Descripción |
|--------|-------------|
| 404 | Jugador no encontrado |

---

### Cálculos de rating (Calculations)

```http
GET /players/{fideid}/calculations?opponent_rating=1800
```

Ejemplo de cálculo FIDE: puntuación esperada, K-factor y cambio de rating para victoria/tablas/derrota contra un oponente.

**Parámetros**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `opponent_rating` | int | 1800 | Rating del oponente (1000-3000) |

---

### Evolución del rating (Progress)

```http
GET /players/{fideid}/progress?months=24
```

Serie temporal de ratings (Standard, Rapid, Blitz). Requiere datos en `fide.player_rating_history` (p. ej. `python -m scripts.run_import_history --current-year --country PAR`).

**Parámetros**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `months` | int | 24 | Meses de historial (1-120) |

---

### Estadísticas W/D/L (Stats)

```http
GET /players/{fideid}/stats
```

Victorias, tablas y derrotas por color (Total, Standard, Rapid, Blitz). Obtiene datos desde la API de FIDE.

**Errores**

| Código | Descripción |
|--------|-------------|
| 503 | No se pudieron obtener estadísticas (jugador sin partidas o FIDE no disponible) |

---

## Códigos de título FIDE

| Código | Título |
|--------|--------|
| g | Gran Maestro (GM) |
| wg | Gran Maestro Femenino (WGM) |
| m | Maestro Internacional (IM) |
| wm | Maestro Internacional Femenino (WIM) |
| f | Maestro FIDE (FM) |
| wf | Maestro FIDE Femenino (WFM) |
| c | Candidato a Maestro (CM) |
| wc | Candidato a Maestro Femenino (WCM) |
