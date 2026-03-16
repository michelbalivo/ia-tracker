-- Migración: Crear tabla maestra areas_funcionales y campo en initiatives
-- Ejecutar en Railway psql ANTES de desplegar el nuevo código

-- 1. Tabla maestra
CREATE TABLE IF NOT EXISTS areas_funcionales (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    color TEXT DEFAULT '#a3a3a3',
    orden INT DEFAULT 0
);

-- 2. Poblar con las 11 áreas
INSERT INTO areas_funcionales (nombre, descripcion, orden) VALUES
    ('SAP Finance Copilot', 'Capa de IA transversal sobre el ecosistema SAP', 1),
    ('Compras Intelligence', 'Asistente inteligente para compras indirectas', 2),
    ('Energy Intelligence', 'Plataforma de IA para gestión energética', 3),
    ('Contract Intelligence Hub', 'Extracción, análisis y consulta de contratos', 4),
    ('Global Retail Support', 'Hub de soporte inteligente a tiendas', 5),
    ('Extensiones Apps', 'IA integrada en aplicaciones específicas', 6),
    ('Finance Risk Intelligence', 'Control interno y gestión de riesgos financieros', 7),
    ('Legal & PI', 'Propiedad industrial y análisis legal', 8),
    ('Sustainability Hub', 'Iniciativas de sostenibilidad', 9),
    ('Transport Intelligence', 'Optimización logística y transporte', 10),
    ('Otros', 'Iniciativas transversales o sin clasificar', 11)
ON CONFLICT (nombre) DO NOTHING;

-- 3. Añadir campo area_funcional a initiatives
ALTER TABLE initiatives ADD COLUMN IF NOT EXISTS area_funcional TEXT;

-- 4. Poblar area_funcional según CSV
UPDATE initiatives SET area_funcional = 'SAP Finance Copilot' WHERE id IN (1,2,3,5,6,7,9,10,14,15,40,41,44,45,46,47,49,53,59);
UPDATE initiatives SET area_funcional = 'Compras Intelligence' WHERE id IN (18,19,20,21,22,23);
UPDATE initiatives SET area_funcional = 'Energy Intelligence' WHERE id IN (29,30,31,32,33,50);
UPDATE initiatives SET area_funcional = 'Contract Intelligence Hub' WHERE id IN (4,8,17,35,37,43);
UPDATE initiatives SET area_funcional = 'Global Retail Support' WHERE id IN (24,25,26,27,28);
UPDATE initiatives SET area_funcional = 'Extensiones Apps' WHERE id IN (13,16,55,57);
UPDATE initiatives SET area_funcional = 'Finance Risk Intelligence' WHERE id IN (11,12,51);
UPDATE initiatives SET area_funcional = 'Legal & PI' WHERE id IN (34,36);
UPDATE initiatives SET area_funcional = 'Sustainability Hub' WHERE id IN (56);
UPDATE initiatives SET area_funcional = 'Transport Intelligence' WHERE id IN (42);
UPDATE initiatives SET area_funcional = 'Otros' WHERE id IN (38,39,48,52,54,58);
