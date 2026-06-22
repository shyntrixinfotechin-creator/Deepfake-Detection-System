CREATE DATABASE IF NOT EXISTS deepfake_db; 
USE deepfake_db;

-- Admins
CREATE TABLE IF NOT EXISTS admin_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE,
    password VARCHAR(100)
);

INSERT INTO admin_users(username, password)
VALUES ('admin', 'admin123');

-- Complaints
CREATE TABLE IF NOT EXISTS complaints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    age VARCHAR(10),
    gender VARCHAR(10),
    mobile VARCHAR(20),
    description TEXT,
    image VARCHAR(255),
    status VARCHAR(20) DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);