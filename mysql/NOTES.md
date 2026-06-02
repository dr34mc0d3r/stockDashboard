


sudo ufw allow from 192.168.142.0/24 to any port 3306


Client App
brew install --cask dbeaver-community
setup:
Open DBeaver, create a new connection:
Type: MariaDB
Host: 192.168.142.174
Port: 3306
Database: app_db
Username: app_user
Password: E7?n5P;T0MWwrV%KfivU


Security:
GRANT ALL ON app_db.* TO 'app_user'@'192.168.142.0/24' IDENTIFIED BY 'E7?n5P;T0MWwrV%KfivU';
FLUSH PRIVILEGES;

Best Practice:
  Create a limited DB user for the app.

  Rationale: Limits damage from successful injections by restricting DB permissions.

CREATE USER 'api_user'@'localhost' IDENTIFIED BY 'A!8xZs9^bLq3#N4mR0yW';
GRANT SELECT, INSERT, UPDATE, DELETE ON app_db.* TO 'api_user'@'localhost';
FLUSH PRIVILEGES;


CLI Commands:
  Backup
  docker run --rm -v mariadb_data:/data -v $$ (pwd)/backup:/backup ubuntu tar cvf /backup/mariadb_backup_ $$(date +%F).tar /data

  Varify db version
  docker exec mysql_db mysql -V

  Docker EXEC interactive terminal
  docker exec -it mysql_db mysql -uroot -p

Performance:
  Your E5300 server is limited. If slow, reduce innodb_buffer_pool_size to 128M in my.cnf
