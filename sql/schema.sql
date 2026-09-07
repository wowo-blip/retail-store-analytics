CREATE TABLE IF NOT EXISTS dataset_imports (
    source_sha256 CHAR(64) PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    row_count INT NOT NULL,
    total_sales DECIMAL(16,4) NOT NULL,
    imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    quality_report JSON NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS fact_sales (
    invoice_id VARCHAR(32) PRIMARY KEY,
    branch CHAR(1) NOT NULL,
    city VARCHAR(64) NOT NULL,
    customer_type VARCHAR(32) NOT NULL,
    gender VARCHAR(16) NOT NULL,
    product_line VARCHAR(64) NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL,
    quantity INT NOT NULL,
    tax_amount DECIMAL(14,4) NOT NULL,
    total DECIMAL(14,4) NOT NULL,
    sale_date DATE NOT NULL,
    sale_time TIME NOT NULL,
    payment VARCHAR(32) NOT NULL,
    cogs DECIMAL(14,4) NOT NULL,
    gross_margin_percentage DECIMAL(12,8) NOT NULL,
    gross_income DECIMAL(14,4) NOT NULL,
    rating DECIMAL(3,1) NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    FOREIGN KEY (source_sha256) REFERENCES dataset_imports(source_sha256),
    CHECK (quantity > 0),
    CHECK (unit_price >= 0 AND total >= 0 AND tax_amount >= 0),
    CHECK (rating BETWEEN 0 AND 10),
    INDEX idx_sales_date_city (sale_date, city),
    INDEX idx_sales_category (product_line, sale_date)
) ENGINE=InnoDB;
