CREATE TABLE "envsensordata" (
  "node_id" varchar,
  "voltage" double precision,
  "temperature" double precision,
  "humidity" double precision,
  "moisture" double precision,
  "time" timestamptz
);

CREATE TABLE "paxsensordata" (
  "node_id" varchar,
  "voltage" double precision,
  "pax" integer,
  "time" timestamptz
);

CREATE TABLE "node" (
  "node_id" varchar PRIMARY KEY,
  "location_id" integer,
  "type" varchar,
  "description" text
);

CREATE TABLE "idmapping" (
  "node_id" varchar,
  "deveui" varchar
);

ALTER TABLE "envsensordata" ADD FOREIGN KEY ("node_id") REFERENCES "node" ("node_id");

ALTER TABLE "paxsensordata" ADD FOREIGN KEY ("node_id") REFERENCES "node" ("node_id");



insert into idmapping (node_id, deveui) values
('8676-2428','eui-70b3d57ed0043d2d'),
('9260-1607','eui-70b3d57ed0043d54'),
('7071-0496','eui-70b3d57ed0043d5c'),
('1238-5580','eui-70b3d57ed0043d68'),
('0781-0858','eui-70b3d57ed0043d6a'),
('1955-8871','eui-70b3d57ed0043d70'),
('7353-5703','eui-70b3d57ed0043d73'),
('3369-4484','eui-70b3d57ed0043d76'),
('9565-3553','eui-70b3d57ed0043d7b'),
('5735-6956','eui-70b3d57ed0043d7f'),
('8626-2032','eui-70b3d57ed0043d84'),
('2734-7381','eui-70b3d57ed0043d85'),
('3726-6652','eui-70b3d57ed0043d86'),
('3760-9036','eui-70b3d57ed0043d8a'),
('8987-4856','eui-70b3d57ed0043d8d'),
('4835-8701','eui-3c6105498c70feff'),
('0694-6129','eui-3c61054b0e74feff'),
('4496-3521','eui-3c61054b0f5cfeff'),
('3426-5375','eui-c4dd579cd520feff'),
('9975-8297','eui-c4dd579ebfa0feff');


insert into node (node_id, location_id,type)
values
('8676-2428',1,'env'),
('9260-1607',2,'env'),
('7071-0496',3,'env'),
('1238-5580',4,'env'),
('0781-0858',5,'env'),
('1955-8871',6,'env'),
('7353-5703',7,'env'),
('3369-4484',8,'env'),
('9565-3553',9,'env'),
('5735-6956',10,'env'),
('8626-2032',11,'env'),
('2734-7381',12,'env'),
('3726-6652',13,'env'),
('3760-9036',14,'env'),
('8987-4856',15,'env'),

('4835-8701',16,'pax'),
('0694-6129',17,'pax'),
('4496-3521',18,'pax'),
('3426-5375',19,'pax'),
('9975-8297',20,'pax');

ALTER TABLE "idmapping" ADD FOREIGN KEY ("node_id") REFERENCES "node" ("node_id");


-- to insert data, use idmapping:
-- INSERT INTO paxsensordata (node_id,voltage,pax,time) VALUES ((SELECT node_id from idmapping where deveui = $deveui),$voltage,$pax,$time);
