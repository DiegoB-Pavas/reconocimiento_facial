-- SQL_INIT.sql - Script para inicializar la base de datos MySQL
-- Ejecutar este script en phpMyAdmin o MySQL Workbench

-- Crear tabla de entrenamientos faciales (Modificada para usar empleados)
CREATE TABLE IF NOT EXISTS tbl_facial_training (
    fac_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    fk_pem_id CHAR(36) NOT NULL,
    fac_training_date DATETIME,
    fac_num_photos_captured INT,
    fac_state ENUM('pendiente', 'entrenado', 'fallido') DEFAULT 'pendiente',
    fac_ruta_modelo VARCHAR(255),
    fac_precision FLOAT,
    fac_created_by CHAR(36),
    fac_updated_by CHAR(36),
    fac_created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fac_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (fk_pem_id) REFERENCES tbl_pay_employees(pem_id) ON DELETE CASCADE,
    INDEX idx_pem_id (fk_pem_id),
    INDEX idx_state (fac_state)
);

-- Asistencias: se utiliza la tabla preexistente tbl_attendances del sistema.
-- No se crea tabla asistencias pues existe tbl_attendances con el esquema de la app.

-- Verificar que la tabla usuarios existe (asumiendo que ya está creada)
-- Si no existe, descomentar y ejecutar:
-- CREATE TABLE IF NOT EXISTS tbl_pay_employees (
--     pem_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
--     pem_full_name VARCHAR(100) NOT NULL,
--     pem_email VARCHAR(100),
--     pem_created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     pem_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
-- );


COMMIT;