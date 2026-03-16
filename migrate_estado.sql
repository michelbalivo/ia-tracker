-- Migración: fusionar estado_excel + estado_override → estado
-- Ejecutar en Railway psql ANTES de desplegar el nuevo código

-- 1. Crear nueva columna "estado"
ALTER TABLE initiatives ADD COLUMN IF NOT EXISTS estado TEXT DEFAULT 'Pendiente';

-- 2. Poblar con el valor calculado (override > excel > Pendiente)
UPDATE initiatives
SET estado = COALESCE(NULLIF(estado_override, ''), NULLIF(estado_excel, ''), 'Pendiente');

-- 3. Eliminar las columnas antiguas
ALTER TABLE initiatives DROP COLUMN IF EXISTS estado_excel;
ALTER TABLE initiatives DROP COLUMN IF EXISTS estado_override;
