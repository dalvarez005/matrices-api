-- Crea la base de la app en el PostgreSQL de Yankees (una sola vez).
-- Las tablas las crea la API al arrancar.
--   sudo -u postgres psql -f database/create_database.sql
CREATE DATABASE matrices OWNER quantis;
