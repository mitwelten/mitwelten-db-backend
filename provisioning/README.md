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
postgres_database_name: mitwelten
postgres_database_schema: public

postgres_database_user: postgres
postgres_database_password: ***

postgres_admin_user: mitwelten_admin
postgres_admin_password: ***

postgres_users:
  - username: mitwelten_internal # all access to tables
    password: ***
  - username: mitwelten_upload   # write acccess to some
    password: ***
  - username: mitwelten_public   # read only
    password: ***
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
