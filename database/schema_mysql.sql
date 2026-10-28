-- NEON SLITHER - MySQL 8.0+ / 8.4. Import once with MySQL Workbench or mysql CLI.
-- This script preserves existing data. Run it before starting --database mysql.
CREATE DATABASE IF NOT EXISTS slither_network
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE slither_network;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(24) NOT NULL,
  display_name VARCHAR(20) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  skin_color CHAR(7) NOT NULL DEFAULT '#54E8B0',
  highest_score INT UNSIGNED NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username),
  KEY idx_users_highest_score (highest_score)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS rooms (
  id CHAR(12) NOT NULL,
  name VARCHAR(32) NOT NULL,
  owner_id BIGINT UNSIGNED NOT NULL,
  capacity TINYINT UNSIGNED NOT NULL DEFAULT 8,
  status VARCHAR(12) NOT NULL DEFAULT 'WAITING',  
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  closed_at TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (id),
  KEY idx_rooms_status (status),
  CONSTRAINT fk_rooms_owner FOREIGN KEY (owner_id) REFERENCES users(id),
  CONSTRAINT ck_room_capacity CHECK (capacity BETWEEN 2 AND 8),
  CONSTRAINT ck_room_status CHECK (status IN ('WAITING','PLAYING','CLOSED'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS match_history (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_id CHAR(32) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  room_id CHAR(12) NOT NULL,
  score INT UNSIGNED NOT NULL,
  final_score INT UNSIGNED NOT NULL,
  max_length INT UNSIGNED NOT NULL,
  duration_seconds DECIMAL(10,2) NOT NULL,
  death_reason VARCHAR(24) NOT NULL,
  played_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_match_run (run_id),
  KEY idx_match_user_time (user_id, played_at),
  CONSTRAINT fk_match_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_match_room FOREIGN KEY (room_id) REFERENCES rooms(id)
) ENGINE=InnoDB;

