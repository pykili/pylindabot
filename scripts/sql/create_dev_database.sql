CREATE USER semicode_user WITH ENCRYPTED PASSWORD 'semicode_password';
CREATE DATABASE semicode_db;
GRANT ALL PRIVILEGES ON DATABASE semicode_db TO semicode_user;
