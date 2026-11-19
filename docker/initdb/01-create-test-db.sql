-- Runs once, the first time the database container starts with an empty volume.
-- A second database for integration tests, so they never touch your dev data.
CREATE DATABASE app_test;
