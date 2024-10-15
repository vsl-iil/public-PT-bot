-- Создадим пользователя для репликации
CREATE USER repl_user REPLICATION LOGIN PASSWORD 'Qq123456';

-- Создадим базу данных
CREATE DATABASE users;

-- Подключимся к ней
\c users;

-- Создадим таблицы для почт и телефонов
CREATE TABLE IF NOT EXISTS Телефоны(
	ID SERIAL PRIMARY KEY,
	phone VARCHAR(16));

CREATE TABLE IF NOT EXISTS Почта(
	ID SERIAL PRIMARY KEY,
	email VARCHAR(255));
