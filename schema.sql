CREATE DATABASE IF NOT EXISTS school_erp;
USE school_erp;

CREATE TABLE IF NOT EXISTS students (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    student_class VARCHAR(50) NOT NULL,
    age INT
);

CREATE TABLE IF NOT EXISTS teachers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    subject VARCHAR(100) NOT NULL,
    phone VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS classes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    room VARCHAR(50),
    class_teacher VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS attendance (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    class_id INT NOT NULL,
    date DATE NOT NULL,
    status VARCHAR(10) NOT NULL  -- Present / Absent
);

CREATE TABLE IF NOT EXISTS notices (
    id INT PRIMARY KEY AUTO_INCREMENT,
    class_id INT NULL,          -- NULL means notice is for all classes
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    created_at DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS fees (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_name VARCHAR(100) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    paid_date DATE,
    status VARCHAR(20) NOT NULL  -- Paid / Unpaid
);

CREATE TABLE IF NOT EXISTS exams (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL,
    exam_date DATE NOT NULL,
    remarks VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'teacher'
);

ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'teacher';