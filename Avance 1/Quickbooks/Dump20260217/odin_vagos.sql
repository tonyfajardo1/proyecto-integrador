-- MySQL dump 10.13  Distrib 8.0.31, for Win64 (x86_64)
--
-- Host: localhost    Database: odin
-- ------------------------------------------------------
-- Server version	8.0.31

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `vagos`
--

DROP TABLE IF EXISTS `vagos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `vagos` (
  `idvagos` int NOT NULL AUTO_INCREMENT,
  `ruc` varchar(13) DEFAULT NULL,
  `vago` varchar(45) DEFAULT NULL,
  `infor` json DEFAULT NULL,
  `nick` varchar(5) DEFAULT '',
  PRIMARY KEY (`idvagos`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `vagos`
--

LOCK TABLES `vagos` WRITE;
/*!40000 ALTER TABLE `vagos` DISABLE KEYS */;
INSERT INTO `vagos` VALUES (1,'1792474752001','Admin','{\"ruc\": \"1792474752001\", \"nick\": \"ADM\", \"vago\": \"Admin\", \"clave\": \"1\", \"nivel\": \"Admin\"}',''),(2,'1792474752001','Viviana','{\"ruc\": \"1792474752001\", \"nick\": \"VVS\", \"vago\": \"Viviana\", \"clave\": \"1\", \"nivel\": \"Operador\"}',''),(3,'1792474752001','Rosa Lopez','{\"ruc\": \"1792474752001\", \"nick\": \"RL\", \"vago\": \"Rosa Lopez\", \"clave\": \"1\", \"nivel\": \"Supervisor\"}',''),(4,'1792474752001','Carlos','{\"ruc\": \"1792474752001\", \"nick\": \"CAR\", \"vago\": \"Carlos\", \"clave\": \"12\", \"nivel\": \"Operador\"}','');
/*!40000 ALTER TABLE `vagos` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-02-17 20:23:31
