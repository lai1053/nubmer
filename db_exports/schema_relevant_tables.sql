/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pks_history` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `draw_date` date NOT NULL COMMENT '开奖日期(按请求日期标注)',
  `pre_draw_time` datetime NOT NULL COMMENT '官方给出的开奖时间',
  `pre_draw_issue` bigint NOT NULL COMMENT '期号(官方)',
  `pre_draw_code` varchar(64) NOT NULL COMMENT '开奖号码，逗号分隔',
  `sum_fs` int DEFAULT NULL COMMENT '和值(字段名 sumFS)',
  `sum_big_small` tinyint DEFAULT NULL COMMENT '大小(0小1大等，按接口)',
  `sum_single_double` tinyint DEFAULT NULL COMMENT '单双(0双1单等，按接口)',
  `first_dt` tinyint DEFAULT NULL,
  `second_dt` tinyint DEFAULT NULL,
  `third_dt` tinyint DEFAULT NULL,
  `fourth_dt` tinyint DEFAULT NULL,
  `fifth_dt` tinyint DEFAULT NULL,
  `group_code` int DEFAULT NULL,
  `raw_json` text COMMENT '原始行 JSON 备份',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_issue` (`pre_draw_issue`),
  KEY `idx_draw_date` (`draw_date`),
  KEY `idx_time` (`pre_draw_time`)
) ENGINE=InnoDB AUTO_INCREMENT=2679895 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='PKS 历史开奖明细';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pk10_runtime_state` (
  `state_key` varchar(64) NOT NULL,
  `state_json` json NOT NULL,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`state_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pk10_broadcast_log` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `server_time` datetime DEFAULT NULL,
  `draw_date` date DEFAULT NULL,
  `pre_draw_issue` bigint DEFAULT NULL,
  `draw_issue` bigint DEFAULT NULL,
  `latest_slot` int DEFAULT NULL,
  `line_name` varchar(32) NOT NULL,
  `actionable` tinyint(1) NOT NULL DEFAULT '0',
  `payload_json` json NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_issue_line` (`pre_draw_issue`,`line_name`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=2713 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pk10_bet_log` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `draw_date` date NOT NULL,
  `pre_draw_issue` bigint DEFAULT NULL,
  `slot_1based` int NOT NULL,
  `line_name` varchar(32) NOT NULL,
  `status` varchar(16) NOT NULL,
  `selection_json` json NOT NULL,
  `odds_display` varchar(255) NOT NULL,
  `stake` decimal(12,2) NOT NULL,
  `multiplier_value` int NOT NULL,
  `ticket_count` int NOT NULL,
  `total_cost` decimal(12,2) NOT NULL,
  `hit_count` int DEFAULT NULL,
  `outcome_label` varchar(255) DEFAULT NULL,
  `pnl` decimal(12,4) DEFAULT NULL,
  `meta_json` json DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_line_issue_slot` (`draw_date`,`line_name`,`slot_1based`),
  KEY `idx_draw_date` (`draw_date`),
  KEY `idx_issue` (`pre_draw_issue`)
) ENGINE=InnoDB AUTO_INCREMENT=1838303 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pk10_daily_equity` (
  `draw_date` date NOT NULL,
  `settled_bankroll` decimal(18,4) NOT NULL,
  `total_real_pnl` decimal(18,4) NOT NULL,
  `face_real_pnl` decimal(18,4) NOT NULL,
  `sum_real_pnl` decimal(18,4) NOT NULL,
  `exact_real_pnl` decimal(18,4) NOT NULL,
  `drawdown_from_peak` decimal(18,4) NOT NULL,
  `payload_json` json NOT NULL,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`draw_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
