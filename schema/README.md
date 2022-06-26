# Mitwelten Database Schema

The schema is functionally described in [mitwelten_v2.sql](./mitwelten_v2.sql). It was developped on the previous schema ([mitwelten_v1.sql](./mitwelten_v1.sql)) and the schema built for the _ingest process_ of the project [mitwelten-ml-backend](https://github.com/mitwelten/mitwelten-ml-backend). For details see [NOTES.md](./NOTES.md).

![schema_v2.pgerd](./assets/schema_v2.pgerd.png)

_Source: [mitwelten_v2.pgerd](./mitwelten_v2.pgerd). Note: Schema name in ERD is `dev`, in production `public` will be used._

## Entities

### node

Device (hardware), mostly used to collect data.

#### Attributes

- (unique) _node label_ of the format `1234-5678`
- unique identifier (_serial number_[^node_labels_sn] or _eui_)
- _type_ (`Optical`, `Audio`, `HumiTempMoisture`, `Access Point` etc.)
- _platform_ (`Audiomoth`, `FeatherM4Express` etc.)
- _connectivity_ describing the mode of data exchange
- _power_ source (`230V`, `LiPo`, etc.)
- _hardware-_, _software-_ and _firmware version_
- _description_
- timestamps for change tracking (_created\_at_, _updated\_at_)

[^node_labels_sn]: Previously, some of the _node labels_ were used with multiple devices: The _node labels_ for Audiomoths are printed on SD-cards, a few of the were used in multiple devices. The _serial numbers_ of those devices identify the node in that case and are stored in the `files_audio` records, not in the `node` records.

### location

A "pin" on the map: A _fixed location_ of an appliance, node, event or other entity.

- Has a _location_ in the format WGS84: ° (latitude, longitude), currently implemented as `point(latitude, longitude)`[^postgis_ext]
- Has a _unique name_ (like "Villa, 60cm above ground")
- Has a _description_

[^postgis_ext]: For geographic calculations the PostGIS extension could be added to the db in the future.

### deployment

The _time period_ in which a _node_ has been or is installed at a specific _location_.

- Has foreign keys to _nodes_ and _locations_
- Has a time _period_

The combination of node and period is constrained to be unique and non-overlapping.

### sensordata

Several types of sensordata, currently environmental and pax. Records are assigned to `location` and `node` and must have a _timestamp_.

### files

Several types of files, currently audio and images.

- are assigned to `location` and `node`
- must have a _timestamp_
- must have a unique _object name_ by which the file is identified in S3 storage
- must have unique content, identifyed by `sha256`

There is a separate relation for files uploaded by this _viz-dashboard_, that does not
have attributes for location and node.

### entry

- Has a _name_
- Has a _description_
- Has a foreign key to a _location_
- Has a type
- Can have multiple _tags_
- Can have multiple _files_
- Has timestamps for change tracking (_created\_at_, _updated\_at_)

### tag

Has a unique _name_

### BirdNET pipeline

- __tasks__: queue table, mapping files to inference configurations, tracking the state of tasks
- __configs__: inference configuration
- __results__: identified species
- __species occurrence__: manually maintained list of species expected to be spotted at project location
