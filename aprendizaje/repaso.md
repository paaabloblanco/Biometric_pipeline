# Lista de repaso

Ficheros pendientes de recorrer con `/revisar`. El orden va de la capa más
fina a la más enredada, y agrupa los ficheros que solo se entienden juntos.

Marca `[x]` cuando termines uno. El hook de arranque lee la **primera línea
sin marcar** y te la sugiere.

- [ ] `backend/api/views.py` — por qué la vista es una capa fina y no lleva lógica
- [ ] `backend/api/serializers.py` — qué hace un serializador y dónde está el límite
- [ ] `backend/api/auth.py` + `backend/core/settings/base.py` — JWT vs sesiones, settings por entorno
- [ ] `backend/supabase_data/models.py` — `managed = False` y qué implica
- [ ] `backend/supabase_data/services.py` — ORM idiomático, N+1, `select_related`
- [ ] `backend/nevera/services.py` — lógica de negocio, transacciones
- [ ] `backend/nevera/models.py` — `managed = True`, migraciones
- [ ] `backend/nevera/parsing.py` + `backend/nevera/units.py` — parseo y normalización
- [ ] `backend/health_ai/pruebas.py` — construcción del prompt y llamada a Gemini
- [ ] `backend/extractor.py` — sync SQLite -> Postgres
- [ ] `backend/daily_sync.py` — orquestación de la sync diaria
- [ ] `backend/bot/handlers.py` — capa fina del bot y estado conversacional en memoria
