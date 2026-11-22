# Ansible Provisioning

1. get you SSH key installed on the target VMs
2. add hostname and hostvars (see [below](#configuration--credentials))
3. run the playbook

## Configuration / Credentials

Create two files

`.ansible/hosts`, listing the hostname(s) (FQDN) of the target server(s):

```txt
[db_fhnw]
xyz.fhnw.ch
```

`host_vars/<hostname>.yml`, supply credentials and configuration for the db:

```yml
postgres_super_user: postgres
postgres_super_password: ***

mitwelten_databases:
  - mitwelten_data:
    postgres_database_name: mitwelten
    postgres_database_schema: public

    postgres_admin_user: mitwelten_admin
    postgres_admin_password: ***
    postgres_admin_network_source:
      - samehost

    postgres_users:
      - username: mitwelten_internal # all access to tables
        password: ***
      - username: mitwelten_rest     # write acccess to some
        password: ***
      - username: mitwelten_public   # read only
        password: ***

  - mitwelten_auth:
    postgres_database_name: mitwelten_auth
    ...etc

```

## Setup

```bash
brew install ansible
```

With your SSH key installed on the FHNW VM:

```bash
ansible-playbook -i .ansible/hosts mitwelten-db.yml
```

## Maintenance

Check for package updates

```bash
ansible-playbook -i .ansible/hosts mitwelten-db.yml --tags maintenance
```

## PostgreSQL major upgrade

The role installs `postgres_version` (see `roles/postgres/defaults/main.yml`),
but it does not migrate data between major versions. Installing a new major
version creates an empty cluster on port 5433 next to the old one on 5432.
The configure tasks refuse to run until the new cluster is the one on 5432.

Steps for 14 -> 17 on Debian 13 (trixie), as root on the host unless noted.

TimescaleDB versions need to match on the old and the new cluster for `pg_upgrade`!
Install a corresponding version as a bridge during the upgrade procedure.

1. Stop all services that write to the database, then take a backup:
  `su postgres -c database-backup`

2. Bring TimescaleDB in the old cluster to the most recent version (in this case 2.19.3),
   in each database that has it (`mitwelten`, `mitwelten_cache`).

   ```bash
   su postgres -c "psql -X -d mitwelten -c 'ALTER EXTENSION timescaledb UPDATE'"
   su postgres -c "psql -X -d mitwelten_cache -c 'ALTER EXTENSION timescaledb UPDATE'"
   ```

3. Install PG17 and TimescaleDB for it (from your machine):

   ```bash
   ansible-playbook -i .ansible/hosts mitwelten-db.yml --tags install --skip-tags docker
   ```

4. Install the matching bridge version of TimescaleDB for PG17 from the bookworm repository, then
   remove that repository again:

   ```bash
   echo "deb [signed-by=/etc/apt/keyrings/timescaledb.asc] https://packagecloud.io/timescale/timescaledb/debian/ bookworm main" > /etc/apt/sources.list.d/timescaledb-bridge.list
   apt update && apt install timescaledb-2-2.19.3-postgresql-17
   rm /etc/apt/sources.list.d/timescaledb-bridge.list && apt update
   ```

5. Replace the empty 17 cluster with the upgraded 14 cluster.
   `pg_upgradecluster` copies `postgresql.conf` and `pg_hba.conf`,
   moves the old cluster to 5433 and the new one to 5432.

   Without `--link` the data is copied.
   (old cluster stays usable as fallback; needs free space! `du -sh /var/lib/postgresql/14/main`).

   ```bash
   pg_dropcluster 17 main --stop
   pg_upgradecluster -m upgrade -v 17 14 main
   pg_lsclusters
   ```

6. Update TimescaleDB in the new cluster to the current version,
   then refresh the planner statistics:

   ```bash
   su postgres -c "psql -X -d mitwelten -c 'ALTER EXTENSION timescaledb UPDATE'"
   su postgres -c "psql -X -d mitwelten_cache -c 'ALTER EXTENSION timescaledb UPDATE'"
   su postgres -c "vacuumdb --all --analyze-in-stages"
   ```

7. Run the full playbook.

   ```bash
   ansible-playbook -i .ansible/hosts mitwelten-db.yml --skip-tags docker
   ```

8. Start the services and check them.
   Once everything works, remove the old cluster and packages:

   ```bash
   pg_dropcluster 14 main
   apt purge postgresql-14 postgresql-client-14 postgresql-server-dev-14 timescaledb-2-postgresql-14 timescaledb-2-loader-postgresql-14 timescaledb-toolkit-postgresql-14 timescaledb-2-2.19.3-postgresql-17
   ```
