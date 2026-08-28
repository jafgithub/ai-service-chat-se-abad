-- ---------------------------------------------------------------------------
-- Local -> remote (GoDaddy) sync for the Service Assistant: plumbing + triggers.
--
-- Lifted from the grocery product's sync_setup.sql, which has run since
-- 5 August. Same reasoning, restated because it is the reasoning that matters:
--
-- Why an outbox rather than triggers that write to the client's server
-- directly: MySQL triggers cannot reach another server, and the only engine
-- that would let them (FEDERATED) reports support=NO on this box. Even if it
-- were enabled the write would be synchronous, so a slow or unreachable GoDaddy
-- server would fail a resident's booking. The triggers do one instant local
-- INSERT; sync_to_remote.py does the network hop out of band, with retries.
--
-- WHAT IS NOT SYNCED, AND WHY
--   sessions        login token hashes. A security liability off this box, and
--                   useless to the client's systems.
--   chat_sessions   transient conversation state, hundreds of writes an hour,
--                   and meaningless outside the assistant.
--   cart_items      the same, for a basket that has not become a booking.
--   service_phrases derived from the catalogue and rebuildable in a command.
--
-- Re-runnable. Apply as root:  sudo mysql <dbname> < sync_setup.sql
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sync_outbox (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  table_name      VARCHAR(32)  NOT NULL,
  local_id        BIGINT       NOT NULL,
  op              VARCHAR(8)   NOT NULL DEFAULT 'insert',   -- insert | update
  status          VARCHAR(12)  NOT NULL DEFAULT 'pending',  -- pending | done | failed
  attempts        INT          NOT NULL DEFAULT 0,
  last_error      TEXT         NULL,
  next_attempt_at DATETIME     NULL,
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  synced_at       DATETIME     NULL,
  KEY idx_pending (status, next_attempt_at, id)
) ENGINE=InnoDB;

-- Local ids are never reused as remote ids: both sides auto-increment
-- independently, so verbatim ids would collide. Every synced row records the id
-- the remote gave it here instead, and every foreign key is translated through
-- this table on the way out.
CREATE TABLE IF NOT EXISTS sync_id_map (
  table_name VARCHAR(32) NOT NULL,
  local_id   BIGINT      NOT NULL,
  remote_id  BIGINT      NOT NULL,
  created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (table_name, local_id)
) ENGINE=InnoDB;

-- The outbox records only (table, id). The worker re-reads the live row, so a
-- row edited twice before it syncs pushes its current state, not a stale one.

DROP TRIGGER IF EXISTS trg_accounts_sync_ai;
DROP TRIGGER IF EXISTS trg_accounts_sync_au;
DROP TRIGGER IF EXISTS trg_categories_sync_ai;
DROP TRIGGER IF EXISTS trg_categories_sync_au;
DROP TRIGGER IF EXISTS trg_stores_sync_ai;
DROP TRIGGER IF EXISTS trg_stores_sync_au;
DROP TRIGGER IF EXISTS trg_customers_sync_ai;
DROP TRIGGER IF EXISTS trg_customers_sync_au;
DROP TRIGGER IF EXISTS trg_providers_sync_ai;
DROP TRIGGER IF EXISTS trg_providers_sync_au;
DROP TRIGGER IF EXISTS trg_services_sync_ai;
DROP TRIGGER IF EXISTS trg_services_sync_au;
DROP TRIGGER IF EXISTS trg_provider_availability_sync_ai;
DROP TRIGGER IF EXISTS trg_provider_availability_sync_au;
DROP TRIGGER IF EXISTS trg_provider_services_sync_ai;
DROP TRIGGER IF EXISTS trg_provider_services_sync_au;
DROP TRIGGER IF EXISTS trg_provider_time_off_sync_ai;
DROP TRIGGER IF EXISTS trg_provider_time_off_sync_au;
DROP TRIGGER IF EXISTS trg_service_requests_sync_ai;
DROP TRIGGER IF EXISTS trg_service_requests_sync_au;
DROP TRIGGER IF EXISTS trg_jobs_sync_ai;
DROP TRIGGER IF EXISTS trg_jobs_sync_au;
DROP TRIGGER IF EXISTS trg_job_lines_sync_ai;
DROP TRIGGER IF EXISTS trg_job_lines_sync_au;
DROP TRIGGER IF EXISTS trg_appointments_sync_ai;
DROP TRIGGER IF EXISTS trg_appointments_sync_au;
DROP TRIGGER IF EXISTS trg_payments_sync_ai;
DROP TRIGGER IF EXISTS trg_payments_sync_au;
DROP TRIGGER IF EXISTS trg_parking_passes_sync_ai;
DROP TRIGGER IF EXISTS trg_parking_passes_sync_au;

CREATE TRIGGER trg_accounts_sync_ai AFTER INSERT ON `accounts`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('accounts', NEW.id, 'insert');

CREATE TRIGGER trg_accounts_sync_au AFTER UPDATE ON `accounts`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('accounts', NEW.id, 'update');

CREATE TRIGGER trg_categories_sync_ai AFTER INSERT ON `categories`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('categories', NEW.id, 'insert');

CREATE TRIGGER trg_categories_sync_au AFTER UPDATE ON `categories`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('categories', NEW.id, 'update');

CREATE TRIGGER trg_stores_sync_ai AFTER INSERT ON `stores`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('stores', NEW.id, 'insert');

CREATE TRIGGER trg_stores_sync_au AFTER UPDATE ON `stores`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('stores', NEW.id, 'update');

CREATE TRIGGER trg_customers_sync_ai AFTER INSERT ON `customers`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('customers', NEW.id, 'insert');

CREATE TRIGGER trg_customers_sync_au AFTER UPDATE ON `customers`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('customers', NEW.id, 'update');

CREATE TRIGGER trg_providers_sync_ai AFTER INSERT ON `providers`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('providers', NEW.id, 'insert');

CREATE TRIGGER trg_providers_sync_au AFTER UPDATE ON `providers`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('providers', NEW.id, 'update');

CREATE TRIGGER trg_services_sync_ai AFTER INSERT ON `services`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('services', NEW.id, 'insert');

CREATE TRIGGER trg_services_sync_au AFTER UPDATE ON `services`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('services', NEW.id, 'update');

CREATE TRIGGER trg_provider_availability_sync_ai AFTER INSERT ON `provider_availability`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('provider_availability', NEW.id, 'insert');

CREATE TRIGGER trg_provider_availability_sync_au AFTER UPDATE ON `provider_availability`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('provider_availability', NEW.id, 'update');

CREATE TRIGGER trg_provider_services_sync_ai AFTER INSERT ON `provider_services`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('provider_services', NEW.id, 'insert');

CREATE TRIGGER trg_provider_services_sync_au AFTER UPDATE ON `provider_services`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('provider_services', NEW.id, 'update');

CREATE TRIGGER trg_provider_time_off_sync_ai AFTER INSERT ON `provider_time_off`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('provider_time_off', NEW.id, 'insert');

CREATE TRIGGER trg_provider_time_off_sync_au AFTER UPDATE ON `provider_time_off`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('provider_time_off', NEW.id, 'update');

CREATE TRIGGER trg_service_requests_sync_ai AFTER INSERT ON `service_requests`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('service_requests', NEW.id, 'insert');

CREATE TRIGGER trg_service_requests_sync_au AFTER UPDATE ON `service_requests`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('service_requests', NEW.id, 'update');

CREATE TRIGGER trg_jobs_sync_ai AFTER INSERT ON `jobs`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('jobs', NEW.id, 'insert');

CREATE TRIGGER trg_jobs_sync_au AFTER UPDATE ON `jobs`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('jobs', NEW.id, 'update');

CREATE TRIGGER trg_job_lines_sync_ai AFTER INSERT ON `job_lines`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('job_lines', NEW.id, 'insert');

CREATE TRIGGER trg_job_lines_sync_au AFTER UPDATE ON `job_lines`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('job_lines', NEW.id, 'update');

CREATE TRIGGER trg_appointments_sync_ai AFTER INSERT ON `appointments`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('appointments', NEW.id, 'insert');

CREATE TRIGGER trg_appointments_sync_au AFTER UPDATE ON `appointments`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('appointments', NEW.id, 'update');

CREATE TRIGGER trg_payments_sync_ai AFTER INSERT ON `payments`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('payments', NEW.id, 'insert');

CREATE TRIGGER trg_payments_sync_au AFTER UPDATE ON `payments`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('payments', NEW.id, 'update');

CREATE TRIGGER trg_parking_passes_sync_ai AFTER INSERT ON `parking_passes`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('parking_passes', NEW.id, 'insert');

CREATE TRIGGER trg_parking_passes_sync_au AFTER UPDATE ON `parking_passes`
FOR EACH ROW
  INSERT INTO sync_outbox (table_name, local_id, op) VALUES ('parking_passes', NEW.id, 'update');

