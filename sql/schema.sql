CREATE TABLE IF NOT EXISTS dataset_imports (
    source_sha256 CHAR(64) PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    row_count INT NOT NULL,
    total_sales DECIMAL(18,4) NOT NULL,
    imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    quality_report JSON NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS fact_retail_lines (
    line_id BIGINT PRIMARY KEY,
    source_sheet VARCHAR(32) NOT NULL,
    source_row INT NOT NULL,
    invoice_id VARCHAR(32) NOT NULL,
    stock_code VARCHAR(32) NOT NULL,
    description VARCHAR(255) NULL,
    quantity INT NOT NULL,
    invoice_at DATETIME NOT NULL,
    unit_price DECIMAL(14,4) NOT NULL,
    customer_id INT NULL,
    country VARCHAR(64) NOT NULL,
    line_amount DECIMAL(18,4) NOT NULL,
    is_duplicate BOOLEAN NOT NULL,
    is_cancellation BOOLEAN NOT NULL,
    is_service_line BOOLEAN NOT NULL,
    transaction_type VARCHAR(16) NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    FOREIGN KEY (source_sha256) REFERENCES dataset_imports(source_sha256),
    CHECK (transaction_type IN ('sale','return','excluded')),
    INDEX idx_retail_date_country (invoice_at, country),
    INDEX idx_retail_invoice (invoice_id),
    INDEX idx_retail_customer_date (customer_id, invoice_at),
    INDEX idx_retail_product_date (stock_code, invoice_at),
    INDEX idx_retail_type_date (transaction_type, invoice_at)
) ENGINE=InnoDB;
