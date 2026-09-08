CREATE USER IF NOT EXISTS 'retail_etl'@'%' IDENTIFIED BY 'local-etl-password';
CREATE USER IF NOT EXISTS 'retail_reader'@'%' IDENTIFIED BY 'local-reader-password';

GRANT SELECT, INSERT, CREATE, REFERENCES, INDEX
ON retail_analytics.* TO 'retail_etl'@'%';

GRANT SELECT
ON retail_analytics.* TO 'retail_reader'@'%';
