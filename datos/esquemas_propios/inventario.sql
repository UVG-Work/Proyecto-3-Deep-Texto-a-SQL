-- Esquema inventario: almacenes, artículos, stock, movimientos y órdenes de compra

CREATE TABLE prov (
  cod_prov INT NOT NULL COMMENT 'Código del proveedor',
  nom_prov VARCHAR(80) NOT NULL COMMENT 'Nombre o razón social del proveedor',
  rut_prov VARCHAR(12) NOT NULL COMMENT 'RUT (identificador tributario) del proveedor',
  ciudad VARCHAR(40) NOT NULL COMMENT 'Ciudad donde opera el proveedor',
  tel VARCHAR(20) NULL COMMENT 'Teléfono de contacto',
  email VARCHAR(80) NULL COMMENT 'Correo electrónico de contacto',
  f_alta DATE NOT NULL COMMENT 'Fecha de alta del proveedor en el sistema',
  PRIMARY KEY (cod_prov)
) COMMENT='Proveedores de artículos';

CREATE TABLE cat_art (
  cod_cat INT NOT NULL COMMENT 'Código de la categoría',
  nom_cat VARCHAR(40) NOT NULL COMMENT 'Nombre de la categoría de artículos',
  PRIMARY KEY (cod_cat)
) COMMENT='Categorías de artículos';

CREATE TABLE alm (
  cod_alm INT NOT NULL COMMENT 'Código del almacén',
  nom_alm VARCHAR(60) NOT NULL COMMENT 'Nombre del almacén o bodega',
  ciudad VARCHAR(40) NOT NULL COMMENT 'Ciudad donde se ubica el almacén',
  cap_m3 DECIMAL(8,2) NOT NULL COMMENT 'Capacidad del almacén en metros cúbicos',
  resp VARCHAR(60) NULL COMMENT 'Nombre del responsable del almacén',
  PRIMARY KEY (cod_alm)
) COMMENT='Almacenes (bodegas)';

CREATE TABLE art (
  cod_art VARCHAR(10) NOT NULL COMMENT 'Código del artículo',
  desc_art VARCHAR(80) NOT NULL COMMENT 'Descripción del artículo',
  cod_cat INT NOT NULL COMMENT 'Categoría del artículo',
  cod_prov INT NOT NULL COMMENT 'Proveedor habitual del artículo',
  und_med VARCHAR(4) NOT NULL COMMENT 'Unidad de medida (UN=unidad, CJ=caja, RL=rollo, PQ=paquete, RM=resma, BI=bidón)',
  prec_unit DECIMAL(10,2) NOT NULL COMMENT 'Precio unitario de venta en pesos',
  stk_min INT NOT NULL COMMENT 'Stock mínimo total requerido (suma de todos los almacenes)',
  activo TINYINT(1) NOT NULL DEFAULT 1 COMMENT '1 = artículo activo, 0 = descontinuado',
  PRIMARY KEY (cod_art),
  FOREIGN KEY (cod_cat) REFERENCES cat_art(cod_cat),
  FOREIGN KEY (cod_prov) REFERENCES prov(cod_prov)
) COMMENT='Artículos del catálogo';

CREATE TABLE stk_alm (
  cod_alm INT NOT NULL COMMENT 'Almacén',
  cod_art VARCHAR(10) NOT NULL COMMENT 'Artículo',
  stk_act INT NOT NULL COMMENT 'Stock actual del artículo en el almacén (unidades)',
  f_ult_inv DATE NULL COMMENT 'Fecha del último inventario físico',
  PRIMARY KEY (cod_alm, cod_art),
  FOREIGN KEY (cod_alm) REFERENCES alm(cod_alm),
  FOREIGN KEY (cod_art) REFERENCES art(cod_art)
) COMMENT='Stock actual de cada artículo por almacén';

CREATE TABLE oc (
  num_oc INT NOT NULL COMMENT 'Número de la orden de compra',
  cod_prov INT NOT NULL COMMENT 'Proveedor al que se emite la orden',
  cod_alm INT NOT NULL COMMENT 'Almacén de destino de la mercadería',
  f_emi DATE NOT NULL COMMENT 'Fecha de emisión de la orden',
  f_ent_est DATE NOT NULL COMMENT 'Fecha estimada de entrega',
  f_ent_real DATE NULL COMMENT 'Fecha real de entrega (NULL si no se ha entregado)',
  est_oc VARCHAR(5) NOT NULL COMMENT 'Estado de la orden: PEND=pendiente, RECIB=recibida, ANUL=anulada',
  PRIMARY KEY (num_oc),
  FOREIGN KEY (cod_prov) REFERENCES prov(cod_prov),
  FOREIGN KEY (cod_alm) REFERENCES alm(cod_alm)
) COMMENT='Órdenes de compra a proveedores';

CREATE TABLE det_oc (
  num_oc INT NOT NULL COMMENT 'Orden de compra',
  lin INT NOT NULL COMMENT 'Número de línea dentro de la orden',
  cod_art VARCHAR(10) NOT NULL COMMENT 'Artículo pedido',
  cant INT NOT NULL COMMENT 'Cantidad pedida',
  prec_unit DECIMAL(10,2) NOT NULL COMMENT 'Precio unitario de compra pactado',
  PRIMARY KEY (num_oc, lin),
  FOREIGN KEY (num_oc) REFERENCES oc(num_oc),
  FOREIGN KEY (cod_art) REFERENCES art(cod_art)
) COMMENT='Detalle (líneas) de las órdenes de compra';

CREATE TABLE mov_inv (
  id_mov INT NOT NULL COMMENT 'Identificador del movimiento',
  f_mov DATETIME NOT NULL COMMENT 'Fecha y hora del movimiento',
  tipo_mov CHAR(1) NOT NULL COMMENT 'Tipo de movimiento: E=entrada, S=salida, A=ajuste',
  cod_art VARCHAR(10) NOT NULL COMMENT 'Artículo movido',
  cod_alm INT NOT NULL COMMENT 'Almacén donde ocurre el movimiento',
  cant INT NOT NULL COMMENT 'Cantidad de unidades (positiva; en ajustes puede ser negativa)',
  num_oc INT NULL COMMENT 'Orden de compra asociada (solo entradas por compra)',
  obs VARCHAR(120) NULL COMMENT 'Observación del movimiento',
  PRIMARY KEY (id_mov),
  FOREIGN KEY (cod_art) REFERENCES art(cod_art),
  FOREIGN KEY (cod_alm) REFERENCES alm(cod_alm),
  FOREIGN KEY (num_oc) REFERENCES oc(num_oc)
) COMMENT='Movimientos de inventario (entradas, salidas y ajustes)';

INSERT INTO prov VALUES
(1,'Distribuidora Andes Ltda','76123456-7','Santiago','+56 2 2345 6789','ventas@andes.cl','2023-01-15'),
(2,'Ferretería Industrial Sur SpA','77234567-8','Concepción','+56 41 223 4455',NULL,'2023-03-02'),
(3,'Plásticos del Pacífico S.A.','96345678-9','Valparaíso',NULL,'contacto@plapac.cl','2023-05-20'),
(4,'Electro Norte Ltda','78456789-0','Antofagasta','+56 55 244 1122','info@electronorte.cl','2023-08-11'),
(5,'Papelera Central S.A.','90567890-1','Santiago','+56 2 2777 8899','pedidos@papcentral.cl','2024-01-09'),
(6,'Químicos Austral SpA','79678901-2','Puerto Montt','+56 65 228 9900',NULL,'2024-04-17'),
(7,'Herramientas Pro Ltda','76789012-3','Santiago','+56 2 2111 2233','ventas@herrpro.cl','2024-07-03'),
(8,'Embalajes Maule SpA','77890123-4','Talca',NULL,NULL,'2025-02-14');

INSERT INTO cat_art VALUES
(1,'Ferretería'),(2,'Electricidad'),(3,'Plásticos'),(4,'Papelería'),(5,'Limpieza'),(6,'Embalaje');

INSERT INTO alm VALUES
(1,'Bodega Central','Santiago',1200.00,'Marcela Rojas'),
(2,'Bodega Norte','Antofagasta',650.00,'Jorge Pizarro'),
(3,'Bodega Sur','Concepción',800.00,NULL),
(4,'Centro Distribución Puerto','Valparaíso',950.50,'Andrea Fuentes'),
(5,'Bodega Temporal Maipú','Santiago',300.00,NULL);

INSERT INTO art VALUES
('FER-001','Martillo carpintero 16 oz',1,7,'UN',8990.00,20,1),
('FER-002','Destornillador cruz PH2',1,7,'UN',2490.00,30,1),
('FER-003','Caja tornillos 1/2 pulgada x100',1,2,'CJ',3290.00,50,1),
('FER-004','Llave ajustable 10 pulgadas',1,7,'UN',12990.00,15,1),
('FER-005','Cinta métrica 5 m',1,2,'UN',4590.00,25,1),
('ELE-001','Cable eléctrico 2.5 mm rollo 100 m',2,4,'RL',45990.00,10,1),
('ELE-002','Interruptor simple',2,4,'UN',1990.00,40,1),
('ELE-003','Ampolleta LED 9W',2,4,'UN',1590.00,100,1),
('ELE-004','Extensión eléctrica 3 m',2,4,'UN',5990.00,20,1),
('ELE-005','Enchufe triple',2,1,'UN',2290.00,30,0),
('PLA-001','Balde plástico 10 L',3,3,'UN',2990.00,25,1),
('PLA-002','Caja organizadora 30 L',3,3,'UN',7990.00,15,1),
('PLA-003','Bolsa de basura 80x110 x10',3,3,'PQ',1890.00,80,1),
('PLA-004','Tubo PVC 110 mm 3 m',3,2,'UN',9490.00,12,1),
('PAP-001','Resma papel carta 500 hojas',4,5,'RM',4290.00,60,1),
('PAP-002','Archivador de palanca',4,5,'UN',2190.00,40,1),
('PAP-003','Caja lápices pasta azul x50',4,5,'CJ',6990.00,20,1),
('PAP-004','Cuaderno universitario 100 hojas',4,1,'UN',1690.00,50,0),
('LIM-001','Cloro 5 L',5,6,'BI',3490.00,40,1),
('LIM-002','Detergente industrial 20 L',5,6,'BI',18990.00,8,1),
('LIM-003','Guantes de nitrilo caja x100',5,6,'CJ',7490.00,30,1),
('LIM-004','Paño microfibra x5',5,1,'PQ',2990.00,35,1),
('EMB-001','Cinta de embalaje transparente',6,8,'UN',1290.00,120,1),
('EMB-002','Caja de cartón 40x30x30',6,1,'UN',990.00,200,1),
('EMB-003','Film stretch 50 cm',6,3,'RL',8990.00,25,1);

INSERT INTO stk_alm VALUES
(1,'FER-001',45,'2025-06-30'),(1,'FER-002',60,'2025-06-30'),(1,'FER-003',120,'2025-06-30'),
(1,'FER-004',10,'2025-06-30'),(1,'ELE-001',8,'2025-03-31'),(1,'ELE-003',250,'2025-03-31'),
(1,'PAP-001',150,'2025-06-30'),(1,'PAP-002',35,NULL),(1,'LIM-001',70,'2024-12-31'),
(1,'LIM-003',25,'2024-12-31'),(1,'EMB-001',300,'2025-06-30'),(1,'EMB-002',500,'2025-06-30'),
(1,'PLA-003',90,NULL),
(2,'FER-001',12,'2025-01-15'),(2,'FER-005',30,'2025-04-30'),(2,'ELE-001',15,'2025-01-15'),
(2,'ELE-002',55,'2025-01-15'),(2,'ELE-004',18,'2025-05-31'),(2,'LIM-002',5,'2025-01-15'),
(2,'EMB-003',10,NULL),
(3,'FER-003',40,'2024-09-30'),(3,'FER-004',8,'2024-09-30'),(3,'PLA-001',30,NULL),
(3,'PLA-004',6,'2024-10-31'),(3,'LIM-001',20,'2025-06-30'),(3,'LIM-004',40,NULL),
(3,'PAP-003',15,'2024-09-30'),
(4,'PLA-001',22,'2025-02-28'),(4,'PLA-002',18,'2025-02-28'),(4,'PLA-003',60,'2025-03-31'),
(4,'EMB-001',80,'2025-05-31'),(4,'EMB-002',150,'2025-05-31'),(4,'EMB-003',30,'2025-02-28'),
(4,'ELE-003',70,NULL),(4,'PAP-001',45,'2025-06-30'),
(5,'FER-002',5,NULL),(5,'LIM-002',3,'2025-01-31'),(5,'PAP-002',12,'2024-06-30');

INSERT INTO oc VALUES
(1001,7,1,'2023-02-10','2023-02-20','2023-02-19','RECIB'),
(1002,4,2,'2023-03-05','2023-03-20','2023-03-25','RECIB'),
(1003,3,4,'2023-04-12','2023-04-22','2023-04-22','RECIB'),
(1004,5,1,'2023-06-01','2023-06-08','2023-06-12','RECIB'),
(1005,2,3,'2023-07-18','2023-07-30',NULL,'ANUL'),
(1006,6,2,'2023-09-09','2023-09-25','2023-09-24','RECIB'),
(1007,1,1,'2023-11-20','2023-12-01','2023-12-05','RECIB'),
(1008,4,4,'2024-01-15','2024-01-30','2024-01-29','RECIB'),
(1009,7,3,'2024-02-22','2024-03-05','2024-03-11','RECIB'),
(1010,3,4,'2024-04-03','2024-04-15','2024-04-15','RECIB'),
(1011,5,5,'2024-05-27','2024-06-05','2024-06-04','RECIB'),
(1012,6,1,'2024-07-14','2024-07-28','2024-08-02','RECIB'),
(1013,2,3,'2024-09-02','2024-09-15','2024-09-14','RECIB'),
(1014,1,2,'2024-10-21','2024-11-04',NULL,'ANUL'),
(1015,4,1,'2024-12-05','2024-12-18','2024-12-20','RECIB'),
(1016,3,4,'2025-02-11','2025-02-25','2025-02-24','RECIB'),
(1017,7,1,'2025-04-08','2025-04-20',NULL,'PEND'),
(1018,6,3,'2025-05-30','2025-06-12',NULL,'PEND'),
(1019,5,1,'2025-06-16','2025-06-25',NULL,'PEND'),
(1020,2,2,'2025-03-03','2025-03-14','2025-03-20','RECIB');

INSERT INTO det_oc VALUES
(1001,1,'FER-001',50,8200.00),(1001,2,'FER-002',80,2200.00),(1001,3,'FER-004',20,11800.00),
(1002,1,'ELE-001',20,42000.00),(1002,2,'ELE-002',60,1750.00),
(1003,1,'PLA-001',40,2600.00),(1003,2,'PLA-003',100,1650.00),(1003,3,'EMB-003',30,8100.00),
(1004,1,'PAP-001',200,3900.00),(1004,2,'PAP-002',50,1950.00),
(1005,1,'FER-003',100,2950.00),
(1006,1,'LIM-002',10,17200.00),(1006,2,'LIM-001',40,3100.00),
(1007,1,'EMB-002',400,850.00),(1007,2,'LIM-004',50,2600.00),
(1008,1,'ELE-003',150,1380.00),(1008,2,'ELE-004',25,5300.00),
(1009,1,'FER-004',15,12100.00),(1009,2,'FER-001',30,8300.00),
(1010,1,'PLA-002',25,7100.00),(1010,2,'PLA-001',30,2650.00),
(1011,1,'PAP-002',20,1980.00),(1011,2,'PAP-003',15,6400.00),
(1012,1,'LIM-003',40,6900.00),(1012,2,'LIM-001',60,3150.00),
(1013,1,'FER-003',60,3000.00),(1013,2,'PLA-004',10,8700.00),(1013,3,'FER-005',20,4100.00),
(1014,1,'EMB-002',200,880.00),
(1015,1,'ELE-001',15,43500.00),(1015,2,'ELE-003',200,1400.00),(1015,3,'ELE-002',40,1800.00),
(1016,1,'EMB-003',25,8300.00),(1016,2,'PLA-003',80,1700.00),
(1017,1,'FER-002',60,2300.00),(1017,2,'FER-001',40,8400.00),
(1018,1,'LIM-002',8,17800.00),
(1019,1,'PAP-001',150,4000.00),(1019,2,'PAP-003',10,6500.00),
(1020,1,'FER-005',30,4200.00),(1020,2,'FER-003',50,3050.00);

INSERT INTO mov_inv VALUES
(1,'2023-02-19 09:15:00','E','FER-001',1,50,1001,NULL),
(2,'2023-02-19 09:20:00','E','FER-002',1,80,1001,NULL),
(3,'2023-02-19 09:25:00','E','FER-004',1,20,1001,NULL),
(4,'2023-03-02 15:40:00','S','FER-001',1,12,NULL,'Despacho a obra Las Condes'),
(5,'2023-03-25 11:00:00','E','ELE-001',2,20,1002,NULL),
(6,'2023-03-25 11:10:00','E','ELE-002',2,60,1002,NULL),
(7,'2023-04-22 10:30:00','E','PLA-001',4,40,1003,NULL),
(8,'2023-04-22 10:35:00','E','PLA-003',4,100,1003,NULL),
(9,'2023-04-22 10:40:00','E','EMB-003',4,30,1003,NULL),
(10,'2023-05-10 16:20:00','S','ELE-002',2,15,NULL,NULL),
(11,'2023-06-12 08:50:00','E','PAP-001',1,200,1004,NULL),
(12,'2023-06-12 08:55:00','E','PAP-002',1,50,1004,NULL),
(13,'2023-07-03 14:00:00','S','PAP-001',1,40,NULL,'Pedido cliente corporativo'),
(14,'2023-08-21 12:30:00','A','FER-002',1,-3,NULL,'Diferencia en inventario físico'),
(15,'2023-09-24 09:00:00','E','LIM-002',2,10,1006,NULL),
(16,'2023-09-24 09:05:00','E','LIM-001',2,40,1006,NULL),
(17,'2023-10-15 17:45:00','S','LIM-001',2,40,NULL,'Traspaso a Bodega Sur'),
(18,'2023-12-05 10:10:00','E','EMB-002',1,400,1007,NULL),
(19,'2023-12-05 10:15:00','E','LIM-004',1,50,1007,NULL),
(20,'2023-12-18 11:30:00','S','EMB-002',1,120,NULL,NULL),
(21,'2024-01-29 09:40:00','E','ELE-003',4,150,1008,NULL),
(22,'2024-01-29 09:45:00','E','ELE-004',4,25,1008,NULL),
(23,'2024-02-14 13:20:00','S','ELE-003',4,80,NULL,NULL),
(24,'2024-03-11 08:30:00','E','FER-004',3,15,1009,NULL),
(25,'2024-03-11 08:35:00','E','FER-001',3,30,1009,NULL),
(26,'2024-03-28 16:00:00','S','FER-001',3,18,NULL,NULL),
(27,'2024-04-15 10:00:00','E','PLA-002',4,25,1010,NULL),
(28,'2024-04-15 10:05:00','E','PLA-001',4,30,1010,NULL),
(29,'2024-05-06 15:15:00','S','PLA-001',4,48,NULL,'Venta mayorista'),
(30,'2024-06-04 09:20:00','E','PAP-002',5,20,1011,NULL),
(31,'2024-06-04 09:25:00','E','PAP-003',5,15,1011,NULL),
(32,'2024-06-20 12:00:00','A','PAP-003',5,-2,NULL,'Producto dañado'),
(33,'2024-08-02 11:45:00','E','LIM-003',1,40,1012,NULL),
(34,'2024-08-02 11:50:00','E','LIM-001',1,60,1012,NULL),
(35,'2024-08-19 14:30:00','S','LIM-003',1,15,NULL,NULL),
(36,'2024-09-14 10:20:00','E','FER-003',3,60,1013,NULL),
(37,'2024-09-14 10:25:00','E','PLA-004',3,10,1013,NULL),
(38,'2024-09-14 10:30:00','E','FER-005',3,20,1013,NULL),
(39,'2024-10-01 17:10:00','S','PLA-004',3,4,NULL,NULL),
(40,'2024-11-12 09:00:00','S','EMB-001',1,150,NULL,'Campaña fin de año'),
(41,'2024-12-20 08:40:00','E','ELE-001',1,15,1015,NULL),
(42,'2024-12-20 08:45:00','E','ELE-003',1,200,1015,NULL),
(43,'2024-12-20 08:50:00','E','ELE-002',1,40,1015,NULL),
(44,'2024-12-27 15:30:00','S','ELE-003',1,60,NULL,NULL),
(45,'2025-01-09 10:00:00','A','LIM-002',2,-1,NULL,'Envase roto'),
(46,'2025-01-22 11:20:00','S','FER-003',1,35,NULL,NULL),
(47,'2025-02-24 09:10:00','E','EMB-003',4,25,1016,NULL),
(48,'2025-02-24 09:15:00','E','PLA-003',4,80,1016,NULL),
(49,'2025-03-12 16:40:00','S','PLA-003',4,70,NULL,NULL),
(50,'2025-03-20 10:30:00','E','FER-005',2,30,1020,NULL),
(51,'2025-03-20 10:35:00','E','FER-003',2,50,1020,NULL),
(52,'2025-04-15 13:00:00','S','FER-005',2,12,NULL,NULL),
(53,'2025-05-05 08:30:00','A','EMB-002',4,5,NULL,'Conteo cíclico: sobrante'),
(54,'2025-05-21 17:00:00','S','ELE-004',2,7,NULL,NULL),
(55,'2025-06-10 12:15:00','S','PAP-001',4,25,NULL,NULL),
(56,'2025-06-30 14:45:00','S','LIM-001',3,18,NULL,NULL),
(57,'2025-07-08 09:50:00','S','EMB-002',1,90,NULL,NULL),
(58,'2025-08-14 11:05:00','A','ELE-001',1,-2,NULL,'Merma');
