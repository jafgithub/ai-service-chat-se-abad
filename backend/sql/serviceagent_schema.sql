-- The Service Assistant's tables, empty, for a database that does not exist yet.
--
-- Generated from the live dev database on 28 August 2026 with
--   mysqldump --no-data --skip-comments --skip-add-drop-table --no-tablespaces
-- so it creates structure and nothing else. Checked: zero INSERT statements.
--
-- WHY THIS FILE EXISTS SEPARATELY FROM THE SYNC
--
-- The Service Assistant needs its own database on the client's GoDaddy host.
-- We cannot create it. The MySQL user we hold, jjui_usr, has ALL PRIVILEGES on
-- aidata2prd_dev and USAGE on everything else, which means no rights anywhere
-- but the grocery product's database. Attempting CREATE DATABASE returns
--
--   ERROR 1044: Access denied for user 'jjui_usr'@'35.91.251.211'
--
-- On GoDaddy shared hosting a database is created in cPanel by the account
-- owner. So the client creates it and sends four things, and then this file is
-- the first thing that runs against it:
--
--   mysql -h <host> -u <user> -p <newdb> < serviceagent_schema.sql
--
-- WHAT THE CLIENT NEEDS TO DO, IN cPANEL
--
--   1. MySQL Databases -> create the database
--   2. same page -> create a user, with a password
--   3. same page -> add that user to that database, with ALL PRIVILEGES
--   4. Remote MySQL -> add 35.91.251.211 as an allowed host
--
-- Step 4 is the one people forget, and without it the connection times out
-- rather than saying anything useful. If the assistant later moves to its own
-- instance, that new address has to be added there too: the existing grant is
-- pinned to a single IP.
--
-- NOTHING HERE TOUCHES THE GROCERY DATABASE. These 19 tables are the Service
-- Assistant's own, and aidata2prd_dev holds none of them.


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `email` varchar(255) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` enum('customer','provider','admin') NOT NULL DEFAULT 'customer',
  `customer_id` int DEFAULT NULL,
  `provider_id` int DEFAULT NULL,
  `last_login_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  KEY `ix_account_role` (`role`)
) ENGINE=InnoDB AUTO_INCREMENT=24 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `appointments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `job_id` int NOT NULL,
  `starts_at` datetime NOT NULL,
  `ends_at` datetime NOT NULL,
  `technician_id` int DEFAULT NULL,
  `status` enum('held','booked','rescheduled','cancelled','completed') NOT NULL,
  `hold_expires_at` datetime DEFAULT NULL,
  `calendly_uri` varchar(255) DEFAULT NULL,
  `calendly_invitee_uri` varchar(255) DEFAULT NULL,
  `cancel_reason` text,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `provider_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `job_id` (`job_id`),
  KEY `ix_appointment_calendly` (`calendly_uri`),
  KEY `ix_appointment_day` (`starts_at`),
  KEY `ix_appointment_provider` (`provider_id`,`starts_at`),
  CONSTRAINT `appointments_ibfk_1` FOREIGN KEY (`job_id`) REFERENCES `jobs` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cart_items` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `session_id` varchar(64) NOT NULL,
  `item_id` bigint NOT NULL,
  `quantity` int NOT NULL,
  `unit_price` decimal(24,2) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_cart_items_session_id` (`session_id`),
  CONSTRAINT `cart_items_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `chat_sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `categories` (
  `id` bigint unsigned NOT NULL,
  `name` varchar(120) NOT NULL,
  `status` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_sessions` (
  `id` varchar(64) NOT NULL,
  `latitude` decimal(10,7) DEFAULT NULL,
  `longitude` decimal(10,7) DEFAULT NULL,
  `last_shown_json` json DEFAULT NULL,
  `last_referenced_item_id` bigint DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `community` varchar(64) DEFAULT NULL,
  `last_documents_json` json DEFAULT NULL,
  `conversation_mode` varchar(16) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `customers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `phone` varchar(30) DEFAULT NULL,
  `latitude` decimal(10,7) DEFAULT NULL,
  `longitude` decimal(10,7) DEFAULT NULL,
  `address` text,
  `type` varchar(50) DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `job_lines` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `item_id` bigint DEFAULT NULL,
  `job_id` bigint DEFAULT NULL,
  `price` decimal(24,2) NOT NULL,
  `item_details` text,
  `quantity` int NOT NULL,
  `tax_amount` decimal(24,2) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `total_add_on_price` decimal(24,2) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `jobs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `customer_id` int NOT NULL,
  `status` enum('pending','confirmed','scheduled','completed','cancelled') NOT NULL,
  `total_amount` decimal(10,2) NOT NULL,
  `items_json` json DEFAULT NULL,
  `notes` text,
  `appointment_date` date DEFAULT NULL,
  `appointment_time` varchar(20) DEFAULT NULL,
  `access_notes` text,
  `idempotency_key` varchar(64) DEFAULT NULL,
  `payment_method` varchar(20) DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `provider_id` int DEFAULT NULL,
  `provider_service_id` int DEFAULT NULL,
  `currency` varchar(8) DEFAULT 'USD',
  `service_request_id` int DEFAULT NULL,
  `payment_status` varchar(20) NOT NULL DEFAULT 'unpaid',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idempotency_key` (`idempotency_key`),
  KEY `customer_id` (`customer_id`),
  CONSTRAINT `jobs_ibfk_1` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=33 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `parking_passes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `account_id` int NOT NULL,
  `customer_id` int DEFAULT NULL,
  `community` varchar(80) NOT NULL,
  `vehicle_registration` varchar(32) NOT NULL,
  `vehicle_description` varchar(120) DEFAULT NULL,
  `visiting` varchar(120) DEFAULT NULL,
  `token` varchar(64) NOT NULL,
  `status` varchar(20) NOT NULL,
  `issued_at` datetime NOT NULL,
  `expires_at` datetime NOT NULL,
  `exited_at` datetime DEFAULT NULL,
  `notes` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_parking_passes_token` (`token`),
  KEY `ix_parking_passes_community` (`community`),
  KEY `ix_parking_passes_expires_at` (`expires_at`),
  KEY `ix_parking_account_status` (`account_id`,`status`),
  KEY `ix_parking_passes_id` (`id`),
  KEY `ix_parking_passes_customer_id` (`customer_id`),
  KEY `ix_parking_passes_status` (`status`),
  KEY `ix_parking_passes_account_id` (`account_id`),
  CONSTRAINT `parking_passes_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`),
  CONSTRAINT `parking_passes_ibfk_2` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `payments` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `order_id` int NOT NULL,
  `provider` varchar(20) NOT NULL,
  `provider_ref` varchar(255) DEFAULT NULL,
  `provider_event_id` varchar(255) DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `currency` varchar(10) NOT NULL,
  `error_message` text,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_payments_event` (`provider_event_id`),
  KEY `ix_payments_ref` (`provider`,`provider_ref`),
  KEY `ix_payments_order` (`order_id`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `provider_availability` (
  `id` int NOT NULL AUTO_INCREMENT,
  `provider_id` int NOT NULL,
  `weekday` int NOT NULL,
  `opens_at` time NOT NULL,
  `closes_at` time NOT NULL,
  `out_of_hours` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_provider_weekday` (`provider_id`,`weekday`,`opens_at`),
  CONSTRAINT `fk_pa_provider` FOREIGN KEY (`provider_id`) REFERENCES `providers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=47 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `provider_services` (
  `id` int NOT NULL AUTO_INCREMENT,
  `provider_id` int NOT NULL,
  `service_id` int NOT NULL,
  `price` decimal(10,2) DEFAULT NULL,
  `duration_minutes` int DEFAULT NULL,
  `notes` text,
  `active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_provider_service` (`provider_id`,`service_id`),
  KEY `ix_provider_service_service` (`service_id`,`active`),
  CONSTRAINT `fk_ps_provider` FOREIGN KEY (`provider_id`) REFERENCES `providers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=35 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `provider_time_off` (
  `id` int NOT NULL AUTO_INCREMENT,
  `provider_id` int NOT NULL,
  `starts_at` datetime NOT NULL,
  `ends_at` datetime NOT NULL,
  `reason` varchar(200) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_time_off_provider` (`provider_id`,`starts_at`,`ends_at`),
  CONSTRAINT `fk_time_off_provider` FOREIGN KEY (`provider_id`) REFERENCES `providers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `providers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `business_name` varchar(200) NOT NULL,
  `contact_name` varchar(160) DEFAULT NULL,
  `email` varchar(255) NOT NULL,
  `phone` varchar(40) DEFAULT NULL,
  `website` varchar(400) DEFAULT NULL,
  `description` text,
  `address` text,
  `city` varchar(120) DEFAULT NULL,
  `postcode` varchar(20) DEFAULT NULL,
  `latitude` decimal(10,7) DEFAULT NULL,
  `longitude` decimal(10,7) DEFAULT NULL,
  `travel_radius_miles` int DEFAULT '15',
  `status` enum('pending','active','suspended','rejected') NOT NULL DEFAULT 'pending',
  `requires_approval` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  KEY `ix_provider_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `service_phrases` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `service_id` bigint NOT NULL,
  `phrase` varchar(400) NOT NULL,
  `vector` json NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_phrase_service` (`service_id`)
) ENGINE=InnoDB AUTO_INCREMENT=190 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `service_requests` (
  `id` int NOT NULL AUTO_INCREMENT,
  `customer_id` int NOT NULL,
  `description` text NOT NULL,
  `address` text,
  `postcode` varchar(20) DEFAULT NULL,
  `urgency` enum('whenever','this_week','urgent') NOT NULL DEFAULT 'whenever',
  `service_id` int DEFAULT NULL,
  `provider_id` int DEFAULT NULL,
  `job_id` int DEFAULT NULL,
  `status` enum('open','matched','booked','unserved','closed') NOT NULL DEFAULT 'open',
  `outcome_note` text,
  `session_id` varchar(64) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_request_customer` (`customer_id`,`created_at`),
  KEY `ix_request_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=38 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `services` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `description` text,
  `image` varchar(255) DEFAULT NULL,
  `category_id` bigint DEFAULT NULL,
  `price` decimal(24,2) NOT NULL,
  `tax` decimal(24,2) NOT NULL,
  `tax_type` varchar(20) DEFAULT NULL,
  `discount` decimal(24,2) DEFAULT NULL,
  `discount_type` varchar(20) DEFAULT NULL,
  `veg` tinyint(1) DEFAULT NULL,
  `status` tinyint(1) NOT NULL,
  `store_id` bigint DEFAULT NULL,
  `stock` int DEFAULT NULL,
  `unit_id` bigint DEFAULT NULL,
  `slug` varchar(255) DEFAULT NULL,
  `recommended` tinyint(1) DEFAULT NULL,
  `organic` tinyint(1) DEFAULT NULL,
  `order_count` int DEFAULT NULL,
  `avg_rating` decimal(16,14) DEFAULT NULL,
  `rating_count` int DEFAULT NULL,
  `duration_minutes` int DEFAULT NULL,
  `emergency` tinyint(1) DEFAULT NULL,
  `vendor_prod_prod_page_url` varchar(1024) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `item_vector` json DEFAULT NULL,
  `module_id` bigint DEFAULT NULL,
  `is_approved` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=52 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sessions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `account_id` int NOT NULL,
  `token_hash` varchar(64) NOT NULL,
  `expires_at` datetime NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `revoked_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token_hash` (`token_hash`),
  KEY `ix_session_account` (`account_id`),
  KEY `ix_session_expiry` (`expires_at`),
  CONSTRAINT `fk_session_account` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=40 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stores` (
  `id` bigint unsigned NOT NULL,
  `name` varchar(160) NOT NULL,
  `status` tinyint(1) NOT NULL DEFAULT '1',
  `email` varchar(190) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

