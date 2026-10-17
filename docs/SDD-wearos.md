# SDD — Ingesta directa desde el reloj (Wear OS)

Documento de diseño. Estado: **propuesta**. Fecha: 2026-09-07.

Sigue la convención de nombres del resto de SDDs (`SDD-*.md`) aunque se pidió
como `wearos.md`.

## 1. Objetivo

Eliminar la intervención manual de la ingesta de datos biométricos.

Hoy los datos llegan a Supabase recorriendo cinco saltos, **dos de ellos
manuales**:

| # | Salto | Latencia | Manual |
|---|---|---|---|
| 1 | Reloj → Mi Fitness (BLE) | minutos | **sí** (abrir app y pulsar sincronizar) |
| 2 | Mi Fitness → better-mi-fitness-sync → Health Connect | a demanda | **sí** (abrir app y pulsar sincronizar) |
| 3 | Health Connect → export `.zip` en Drive | 1 vez al día | no |
| 4 | Drive → PC | minutos, si el PC está encendido | no |
| 5 | `daily_sync.py` (Programador de tareas de Windows) | 1 vez al día | no |

El problema **no es la latencia**: es que el pipeline tiene un humano dentro.
Si se olvida un toque, `run_analysis` corre sobre datos viejos y **falla en
silencio** — el análisis se genera igual, solo que sobre información obsoleta.
Un fallo silencioso es peor que uno ruidoso.

**Objetivo:** que los datos lleguen a Supabase **sin que nadie toque nada**,
con granularidad horaria en lugar de diaria.

No objetivos de esta iteración:
- Sustituir Mi Fitness como app de reloj. Sigue instalada; solo deja de ser
  parte del camino de los datos.
- Métricas nuevas que hoy no se guardan (pasos, calorías, entrenamientos).
  Se acota a las cuatro tablas existentes.
- Multiusuario, o soporte para relojes que no sean el del dueño.
- Subir el backend a la nube (SDD aparte). Este documento asume que la API
  Django ya es accesible desde el reloj por HTTPS.

## 2. Decisión de arquitectura: app propia en el reloj, no en el móvil

**Opción elegida:** una app **Wear OS** instalada en el Xiaomi Watch 2 que
recoge métricas de **Health Services**, las almacena en un buffer local y las
envía **cada hora** a un endpoint nuevo de la API DRF.

```
   ANTES (5 saltos, 2 manuales)
   Reloj ──BLE──► Mi Fitness ──►  better-sync ──► Health Connect
                    (manual)        (manual)            │
                                                   export diario
                                                        ▼
                                              Drive ──► PC ──► Supabase

   DESPUÉS (1 salto, 0 manuales)
   ┌──────────────────────────────┐
   │  Watch 2 (Wear OS)           │
   │  Health Services (pasivo)    │
   │        │                     │
   │        ▼                     │
   │  Room (buffer local)         │      HTTPS + JWT
   │        │                     │  ──────────────────►  POST /api/ingest
   │  WorkManager (cada hora)     │                            │
   └──────────────────────────────┘                            ▼
                                                    supabase_data/services.py
                                                            │
                                                            ▼
                                                     Supabase (Postgres)
```

**Por qué en el reloj y no en el móvil:**
- Una app en el móvil leyendo Health Connect eliminaría los saltos 3, 4 y 5
  (export, Drive, PC), pero **no los dos toques manuales**, que son justamente
  el problema. Resolvería el problema equivocado.
- El Watch 2 corre **Wear OS 4**, no un RTOS propietario. Admite apps de
  terceros y tiene **WiFi propio**, así que puede hablar con la API sin
  intermediarios. Con una Band o un Watch S esta opción no existiría.
- Cuando no hay WiFi, Wear OS enruta el tráfico de red por el teléfono
  emparejado de forma transparente. El código no cambia.

**Por qué Health Services y no leer el sensor a pelo:**
`HealthServicesClient` es la API oficial de Google para datos de salud en Wear
OS. Su modo **pasivo** (`PassiveMonitoringClient`) hace que el sistema recoja
las muestras de forma continua y las entregue **en lotes**, en lugar de que la
app despierte cada hora a encender el sensor. Es la diferencia entre una app
que dura un día de batería y una que no se nota.

**Descartado: Tasker / MacroDroid automatizando los toques.** Una macro con
servicio de accesibilidad que abra Mi Fitness y pulse el botón. Es barato y
funcionaría mañana, pero cualquier actualización de la UI de Xiaomi lo rompe
**sin avisar** — vuelve el fallo silencioso que queremos eliminar. Es un
parche, no arquitectura.

**Descartado: ingerir por Supabase directamente desde el reloj** (con la
`service_role` key, como hace `extractor.py`). Metería una credencial de
administrador de la base de datos dentro de un APK instalado en un reloj.
La API DRF ya existe, ya tiene JWT y ya es la frontera correcta.

## 3. El tapón: qué se puede leer y qué no

Límite duro que condiciona todo el plan. De las cuatro tablas actuales:

| Tabla | Origen del dato | ¿Health Services? |
|---|---|---|
| `heart_rate_samples` | sensor óptico | **sí**, `DataType.HEART_RATE_BPM` |
| `oxygen_saturation_samples` | sensor SpO₂ | **probable**, depende del dispositivo |
| `resting_heart_rate_samples` | **algoritmo de Xiaomi** | dudoso |
| `sleep_stages` | **algoritmo de Xiaomi** | dudoso |

La FC en reposo y las fases del sueño no son lecturas de sensor: son la salida
de modelos propietarios que corren en la app y la nube de Xiaomi. Una app
propia **no puede recalcularlas**.

Lo que sí soporta el dispositivo concreto se consulta **en tiempo de
ejecución** con `PassiveMonitoringClient.getCapabilities()`. No hay forma de
saberlo por documentación: hay que preguntárselo al reloj. De ahí la Fase 0.

> **Aviso de una prueba anterior.** Cuando se investigó el hueco de FC
> (2026-08-29) se comprobó que **Google Fit y Fitbit instalados en este mismo
> Watch 2 solo capturaban FC durante entrenamientos**: el reloj no parecía dar
> acceso *continuo* al sensor a apps de terceros. Si ese límite es del
> dispositivo y no de esas apps, afecta también a una app propia, y la Fase 2
> se quedaría en FC solo durante entrenos — insuficiente.
>
> Es la razón por la que la Fase 0 **no basta con listar capacidades**: hay que
> confirmar que llegan muestras en reposo, no solo que el tipo de dato figura
> como soportado. Si el límite se confirma, este SDD se archiva y la vía
> realista pasa a ser la app en el móvil sobre Health Connect (§2), asumiendo
> que no elimina los toques manuales.

**Consecuencia asumida:** si el sueño no está disponible, el diseño es
**híbrido** — la app cubre FC y SpO₂ en tiempo casi real, y la cadena manual
se conserva **solo para el sueño**, que es la métrica que mejor tolera un día
de retraso (se genera de noche, se consume por la mañana).

## 4. Contrato de datos

### 4.1 El problema de `parent_key`

`heart_rate_samples` y `sleep_stages` tienen clave única compuesta
`(parent_key, ...)`, donde `parent_key` es el identificador de la *serie padre*
en Health Connect. La app del reloj no tiene ese concepto.

`supabase_data` es **`managed = False`** y el esquema no se toca (CLAUDE.md),
así que **no** se añade una columna `source`. Solución: la app envía y el
servidor asigna un **`parent_key` sintético negativo** derivado del día local:

```
parent_key = -(YYYYMMDD)     # p. ej. 2026-09-07 -> -20260907
```

Health Connect solo genera claves positivas, así que el rango negativo está
libre por construcción y **nunca colisiona** con la cadena antigua. Junto a
`recorded_at`, la clave única sigue garantizando idempotencia.

### 4.2 UUID determinista, no aleatorio

`oxygen_saturation_samples` y `resting_heart_rate_samples` tienen `uuid` como
clave única. Si la app generase un UUID aleatorio, **cada reintento duplicaría
la fila**. La app genera un **UUIDv5 determinista**:

```
uuid = uuidv5(NAMESPACE_PROYECTO, "wearos:{metrica}:{recorded_at_iso}")
```

Mismo dato reenviado ⇒ mismo UUID ⇒ el upsert no duplica. Esto es lo que hace
que el reintento sea seguro, y es el requisito que convierte "enviar cada hora"
en algo viable.

### 4.3 Payload

`POST /api/ingest` — todos los bloques opcionales, `recorded_at` en **ISO-8601
UTC** (el reloj nunca envía hora local; así desaparecen los problemas de zona
horaria y de cambio de horario que hoy resuelve `LOCAL_TZ` en `extractor.py`).

```json
{
  "source": "wearos",
  "heart_rate":          [{"bpm": 72, "recorded_at": "2026-09-07T10:15:03Z"}],
  "oxygen_saturation":   [{"percentage": 97.0, "recorded_at": "..."}],
  "resting_heart_rate":  [{"resting_bpm": 54, "recorded_at": "..."}],
  "sleep_stages":        [{"stage_type": 4, "stage_start": "...", "stage_end": "..."}]
}
```

Respuesta `200`:

```json
{"received": {"heart_rate": 120}, "written": {"heart_rate": 118}}
```

`received` ≠ `written` significa que hubo duplicados descartados. No es un
error: es la confirmación de que la idempotencia funciona.

## 5. Componentes nuevos

### 5.1 Backend

- **`supabase_data/services.py`** — `ingest_samples(payload) -> dict`. Aquí vive
  la lógica: validar, calcular `parent_key` sintético y UUIDs, escribir. Usa
  `bulk_create(..., ignore_conflicts=True)` para insertar en un solo viaje a la
  base de datos en vez de una `INSERT` por muestra (con 120 muestras por hora,
  la diferencia entre una consulta y 120 es real).
- **`api/serializers.py`** — serializadores de entrada por métrica, con
  validación de rangos (FC 20-250, SpO₂ 50-100) para que un sensor loco no
  contamine el histórico que alimenta a Gemini.
- **`api/views.py`** — `IngestView`, capa fina: valida, llama al servicio,
  devuelve contadores. Con `throttling` de DRF.
- **`api/urls.py`** — `path("ingest", IngestView.as_view(), name="ingest")`.

### 5.2 App Wear OS (`wearos/`, nueva carpeta del monorepo)

Kotlin + Jetpack Compose for Wear OS. Cuatro piezas:

| Pieza | Responsabilidad |
|---|---|
| `PassiveDataService` | recibe los lotes de Health Services y los persiste |
| `Room` (`samples`) | buffer local; sobrevive a reinicios y a la falta de red |
| `UploadWorker` (`WorkManager`) | cada hora: lee el buffer, hace `POST`, borra lo confirmado |
| Pantalla única | estado de la conexión, último envío, botón de "enviar ahora" |

El buffer local es la pieza que hace el sistema **resistente a la desconexión**:
sin red, las muestras se acumulan; cuando vuelve, se envían todas. `WorkManager`
aplica la restricción `NetworkType.CONNECTED` y **backoff exponencial** en los
reintentos, así que no hay que programar nada de eso a mano.

## 6. Autenticación

La app obtiene un par de tokens con `POST /api/auth/login` y guarda el
**refresh token** en `EncryptedSharedPreferences` (cifrado respaldado por el
almacén de claves del dispositivo). El access token, de vida corta, se refresca
con `/api/auth/refresh` antes de cada envío.

Se reutiliza `IsTheOwner` (`api/permissions.py`) sin cambios: el reloj entra
como el mismo superusuario que la web. Emitir credenciales separadas por
dispositivo sería lo correcto en una app multiusuario; aquí, con un único
dueño, añade complejidad sin reducir riesgo real.

## 7. Riesgos / notas

- **El sueño puede no estar disponible.** Riesgo principal. Mitigado por el
  diseño híbrido (§3) y despejado por la Fase 0 antes de escribir nada serio.
- **Doble ingesta durante la transición.** Si la app y la cadena antigua
  escriben FC a la vez, no hay colisión de claves (rangos disjuntos de
  `parent_key`) pero **sí filas duplicadas del mismo latido**, que sesgarían
  las medias. Al activar la Fase 2 se deja de sincronizar FC por la vía
  antigua.
- **Batería.** El modo pasivo está diseñado para esto, pero hay que medir el
  consumo real durante 48 h antes de darlo por bueno.
- **Sin firma de app / instalación por ADB.** No hay Play Store de por medio;
  se instala por `adb` con el reloj en modo desarrollador. Aceptable para un
  dispositivo propio, y hay que documentar el procedimiento porque se olvida.
- **Deriva silenciosa.** Si la app deja de enviar, hoy nadie se entera.
  Ver la alerta de la Fase 1.
- **Wear OS por WiFi requiere que la API sea accesible desde internet.** Hasta
  que el backend esté desplegado, las pruebas van contra la IP local de la red
  doméstica.

## 8. Decisiones abiertas

1. **¿Frecuencia de envío?** Una hora es el punto de partida. Con buffer local
   el coste de bajarla a 15 min es pequeño; se decide tras medir batería.
2. **¿Qué hacer con `daily_sync.py` al final?** Si la Fase 0 confirma que el
   sueño no es accesible, se queda para siempre (reducido a una tabla). Si sí
   lo es, se retira y desaparecen Drive, el zip y el Programador de tareas.
3. **¿Añadir métricas nuevas (pasos, entrenamientos)?** Health Services las da
   casi gratis, pero implican tablas nuevas y tocar el prompt de Gemini. Fuera
   de esta iteración.
4. **¿Vista de la app en el reloj?** Empezar con estado de sincronización. Que
   muestre el último análisis de Gemini es tentador, pero es otra iteración.

## 9. Plan de implementación (por fases)

Cada fase se verifica con una **prueba real end-to-end** antes de pasar a la
siguiente (CLAUDE.md).

### Fase 0 — Sondeo de capacidades del reloj

Lo más barato que elimina la mayor incertidumbre. Una app Wear OS mínima —una
pantalla, un contador— con dos preguntas que responder, en este orden:

1. **¿Qué tipos soporta?** `PassiveMonitoringClient.getCapabilities()`, lista
   en pantalla.
2. **¿Llegan muestras en reposo?** Registrar un `PassiveListenerService` para
   `HEART_RATE_BPM`, llevar el reloj **sin iniciar ningún entrenamiento** y
   contar cuántas muestras entran en una hora. Esta es la pregunta que de
   verdad decide el proyecto (ver el aviso de §3): si solo llegan muestras
   durante un entreno, la Fase 2 no es viable.

*Prerequisitos:* Android Studio, reloj en modo desarrollador, emparejado por
`adb` (WiFi o USB).

**Verificación:** al cabo de una hora en reposo, el contador en pantalla es
mayor que cero y crece de forma regular. Si es 0 y solo sube al arrancar un
entrenamiento, se para aquí y se replantea (§3). Sin este dato, todo lo demás
es especulación.

### Fase 1 — Endpoint de ingesta + alerta de datos obsoletos

Backend puro, sin tocar el reloj. Sirve para cualquier vía, así que no se tira
nada aunque la Fase 0 dé un mal resultado.

- `ingest_samples()` en `supabase_data/services.py` con `parent_key` sintético,
  UUIDv5 determinista y `bulk_create(ignore_conflicts=True)`.
- `POST /api/ingest` con validación de rangos y throttling.
- Tests con el patrón del repo: prefijo único, limpieza en `tearDown`.
- **Alerta de obsolescencia:** `extractor.py:45` ya calcula `STALE_AFTER_DAYS`,
  pero solo avisa en el log. Que mande un mensaje de Telegram cuando una
  métrica lleve N días sin datos. Convierte el fallo silencioso en ruidoso, que
  es lo que separa un sistema fiable de uno que *parece* fiable.

**Verificación:** `curl` con JWT enviando muestras reales; comprobar en
Supabase que se escriben. Reenviar el mismo payload y comprobar que
`written` es 0 y que no hay filas duplicadas.

### Fase 2 — App Wear OS enviando frecuencia cardíaca

La métrica con más volumen y la que seguro está disponible.

- `PassiveDataService` + Room + `UploadWorker` horario.
- Login y almacenamiento cifrado del refresh token.
- Pantalla de estado.

**Verificación:** dejar el reloj puesto una tarde. Al cabo de tres horas debe
haber tres tandas de FC en Supabase sin haber tocado nada. Probar el modo avión
media hora y confirmar que al recuperar la red se envía lo acumulado.

### Fase 3 — Resto de métricas disponibles

Añadir SpO₂ y lo que la Fase 0 haya confirmado. Al activar cada una, retirarla
de la cadena antigua para evitar la doble ingesta (§7).

**Verificación:** 48 h de funcionamiento continuo. Medir el consumo de batería
antes/después y comprobar que el análisis diario de Gemini sigue recibiendo
datos completos.

### Fase 4 — Retirada de la cadena manual

Reducir `daily_sync.py` a las métricas que el reloj no pueda dar (o eliminarlo
entero). Actualizar `CLAUDE.md` y este documento con el estado final.

**Verificación:** una semana sin abrir Mi Fitness ni better-sync, con el
análisis diario completo todos los días.

## 10. Lo que aporta al proyecto

Además de arreglar el problema: pasa de dos clientes a **tres** sobre la misma
capa de servicios —Telegram, web y reloj— entrando todos por el mismo contrato.
Es la historia arquitectónica de *API REST como frontera única con clientes
heterogéneos*, que es exactamente lo que se pregunta en una entrevista. Y añade
al portfolio ingesta de datos en tiempo casi real desde un dispositivo,
con buffer local, reintentos y escrituras idempotentes.
