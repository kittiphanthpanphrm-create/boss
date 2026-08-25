-- 1. Materialized View สำหรับสรุปสต็อกและสินค้า (คงเดิม)
CREATE MATERIALIZED VIEW IF NOT EXISTS v_product_lifecycle_summary AS
SELECT 
    p.m_product_id AS item_code,
    p.value AS barcode,
    p.name AS product_name,
    l.value AS zone_name,
    COALESCE(SUM(s.qtyonhand), 0) AS qty_on_hand,
    CASE 
        WHEN p.isactive = 'Y' THEN 'พร้อมขาย'
        ELSE 'เลิกขาย'
    END AS status
FROM m_product p
LEFT JOIN m_storageonhand s ON p.m_product_id = s.m_product_id
LEFT JOIN m_locator l ON s.m_locator_id = l.m_locator_id
GROUP BY p.m_product_id, p.value, p.name, l.value, p.isactive;

-- Index สำหรับค้นหาด่วนตามโซนและสต็อก
CREATE INDEX IF NOT EXISTS idx_v_product_zone_qty 
ON v_product_lifecycle_summary (zone_name, qty_on_hand);
