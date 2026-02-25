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

Serie temporal de ratings (Standard, Rapid, Blitz). Requiere ejecutar `python -m scripts.run_import_history` previamente.

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
