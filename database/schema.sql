-- =========================================================
--  schema.sql  –  สร้างตารางพื้นฐานของโปรเจค
-- =========================================================

CREATE DATABASE IF NOT EXISTS `project_planner_db`
DEFAULT CHARACTER SET utf8mb4
DEFAULT COLLATE utf8mb4_unicode_ci;

USE `project_planner_db`;

-- ---------------------------------------------------------
--  ตารางเก็บข้อมูลการบ้าน (Assignments)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS `assignments` (
    `id`               VARCHAR(255) NOT NULL,
    `course_id`        VARCHAR(255) NULL,
    `course_name`      VARCHAR(255) NULL,
    `title`            VARCHAR(255) NOT NULL,
    `description`      TEXT NULL,
    `due_date`         DATETIME NULL,
    `alternate_link`   VARCHAR(511) NULL,
    `status`           ENUM('PENDING','PROCESSED','FAILED') NOT NULL DEFAULT 'PENDING',
    `raw_json`         TEXT NULL,
    `created_at`       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
--  ตารางเก็บ Subtasks ของแต่ละ Assignment
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS `subtasks` (
    `id`                     INT AUTO_INCREMENT,
    `assignment_id`          VARCHAR(255) NOT NULL,
    `task_order`             INT NOT NULL,
    `task_title`             VARCHAR(255) NOT NULL,
    `description`            TEXT NULL,
    `priority`               ENUM('HIGH','MEDIUM','LOW') NOT NULL DEFAULT 'MEDIUM',
    `estimated_hours`        DECIMAL(5,2) NOT NULL DEFAULT 1,
    `suggested_start_date`   DATETIME NULL,
    `suggested_due_date`     DATETIME NULL,
    `status`                 ENUM('TODO','IN_PROGRESS','DONE') NOT NULL DEFAULT 'TODO',
    PRIMARY KEY (`id`),
    KEY `fk_assignment` (`assignment_id`),
    CONSTRAINT `fk_subtasks_assignment`
        FOREIGN KEY (`assignment_id`) REFERENCES `assignments` (`id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
--  ตารางบันทึก log การรัน workflow / API
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS `execution_logs` (
    `id`           BIGINT AUTO_INCREMENT,
    `action`       VARCHAR(100) NOT NULL,
    `status`       VARCHAR(50) NOT NULL,
    `retry_count`  INT NOT NULL DEFAULT 0,
    `details`      TEXT NULL,
    `error_message`TEXT NULL,
    `created_at`   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------
--  ตัวอย่างข้อมูล (ไม่บังคับ) – สามารถลบได้เลย
-- ---------------------------------------------------------
INSERT IGNORE INTO assignments (id, title, status) VALUES
('sample-1', 'ตัวอย่างการบ้าน', 'PENDING');
