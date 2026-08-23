-- create_database.sql
-- ---------------------------------------------------------------------
-- Creates the olist_analytics database.
-- Run this once, connected as a superuser (e.g. `psql -U postgres`).
-- ---------------------------------------------------------------------

SELECT 'CREATE DATABASE olist_analytics'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'olist_analytics'
)\gexec

\c olist_analytics

-- Optional: dedicated schema to keep governance/control tables separate
-- from the star schema if you want stricter separation of concerns.
CREATE SCHEMA IF NOT EXISTS governance;
