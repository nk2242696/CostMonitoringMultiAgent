-- ============================================================
-- Alert Testing SQL Commands
-- Run these to verify alert conditions and test thresholds
-- ============================================================

-- 1. CHECK BUDGET ALERT STATUS
-- Current threshold: >105% triggers CRITICAL alert
-- ============================================================
SELECT 
    (SUM(cost) / 120000.0 * 100) as utilization_percent,
    SUM(cost) as current_month_spend,
    120000.0 as monthly_budget,
    CASE 
        WHEN (SUM(cost) / 120000.0 * 100) > 105 THEN '🚨 ALERT WILL FIRE'
        WHEN (SUM(cost) / 120000.0 * 100) > 100 THEN '⚠️  Over budget (close to alert)'
        ELSE '✅ Within budget'
    END as status
FROM cost_records
WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
  AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
  AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160';

-- 2. CHECK SERVICE COST SPIKE ALERT
-- Current threshold: >50% increase triggers WARNING alert
-- ============================================================
WITH current_month AS (
    SELECT service_name, SUM(cost) as current_cost
    FROM cost_records
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY service_name
),
previous_month AS (
    SELECT service_name, SUM(cost) as previous_cost
    FROM cost_records
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
      AND date < DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY service_name
)
SELECT 
    c.service_name,
    ROUND(c.current_cost::numeric, 2) as current_month,
    ROUND(p.previous_cost::numeric, 2) as previous_month,
    ROUND(((c.current_cost - p.previous_cost) / p.previous_cost * 100)::numeric, 2) as percent_change,
    CASE 
        WHEN ((c.current_cost - p.previous_cost) / p.previous_cost * 100) > 50 THEN '🚨 ALERT WILL FIRE'
        WHEN ((c.current_cost - p.previous_cost) / p.previous_cost * 100) > 30 THEN '⚠️  High increase (close to alert)'
        WHEN ((c.current_cost - p.previous_cost) / p.previous_cost * 100) > 0 THEN '📈 Increased'
        ELSE '📉 Decreased'
    END as status
FROM current_month c
JOIN previous_month p ON c.service_name = p.service_name
WHERE p.previous_cost > 0
ORDER BY percent_change DESC
LIMIT 10;

-- 3. CHECK MONTH-OVER-MONTH ALERT
-- Current threshold: >15% increase triggers WARNING alert
-- ============================================================
WITH current_month AS (
    SELECT SUM(cost) as total
    FROM cost_records
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
      AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'
),
previous_month AS (
    SELECT SUM(cost) as total
    FROM cost_records
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
      AND date < DATE_TRUNC('month', CURRENT_DATE)
      AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'
)
SELECT 
    ROUND(c.total::numeric, 2) as current_month_cost,
    ROUND(p.total::numeric, 2) as previous_month_cost,
    ROUND(((c.total - p.total) / p.total * 100)::numeric, 2) as mom_change_percent,
    CASE 
        WHEN ((c.total - p.total) / p.total * 100) > 15 THEN '🚨 ALERT WILL FIRE'
        WHEN ((c.total - p.total) / p.total * 100) > 10 THEN '⚠️  Significant increase'
        WHEN ((c.total - p.total) / p.total * 100) > 0 THEN '📈 Increased'
        ELSE '📉 Decreased'
    END as status
FROM current_month c, previous_month p;

-- 4. SUMMARY OF ALL ALERT CONDITIONS
-- ============================================================
WITH budget_check AS (
    SELECT (SUM(cost) / 120000.0 * 100) as value
    FROM cost_records
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
      AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'
),
service_spike AS (
    SELECT MAX(((c.current_cost - p.previous_cost) / p.previous_cost * 100)) as value
    FROM (
        SELECT service_name, SUM(cost) as current_cost
        FROM cost_records
        WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
        GROUP BY service_name
    ) c
    JOIN (
        SELECT service_name, SUM(cost) as previous_cost
        FROM cost_records
        WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
          AND date < DATE_TRUNC('month', CURRENT_DATE)
        GROUP BY service_name
    ) p ON c.service_name = p.service_name
    WHERE p.previous_cost > 0
),
mom_check AS (
    SELECT ((c.total - p.total) / p.total * 100) as value
    FROM (
        SELECT SUM(cost) as total
        FROM cost_records
        WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
          AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'
    ) c,
    (
        SELECT SUM(cost) as total
        FROM cost_records
        WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
          AND date < DATE_TRUNC('month', CURRENT_DATE)
          AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'
    ) p
)
SELECT 
    'Budget Exceeded' as alert_name,
    'Critical' as severity,
    ROUND(b.value::numeric, 2) || '%' as current_value,
    '>105%' as threshold,
    CASE WHEN b.value > 105 THEN '🚨 FIRING' ELSE '✅ OK' END as status
FROM budget_check b
UNION ALL
SELECT 
    'Service Cost Spike' as alert_name,
    'Warning' as severity,
    ROUND(s.value::numeric, 2) || '%' as current_value,
    '>50%' as threshold,
    CASE WHEN s.value > 50 THEN '🚨 FIRING' ELSE '✅ OK' END as status
FROM service_spike s
UNION ALL
SELECT 
    'MoM Cost Increase' as alert_name,
    'Warning' as severity,
    ROUND(m.value::numeric, 2) || '%' as current_value,
    '>15%' as threshold,
    CASE WHEN m.value > 15 THEN '🚨 FIRING' ELSE '✅ OK' END as status
FROM mom_check m;

-- ============================================================
-- TO TEST ALERTS - TEMPORARILY ADJUST THRESHOLDS
-- ============================================================
-- Note: To test alerts firing, you can:
-- 1. Lower budget threshold from 105% to 100% (current: 103.79%)
-- 2. Lower service spike threshold from 50% to 40% (Load Balancer: 45.58%)
-- 3. Add test data to simulate higher costs

-- Example: Add test cost data to trigger budget alert
-- INSERT INTO cost_records (date, subscription_id, service_name, cost, region)
-- VALUES (CURRENT_DATE, '518f04e9-2b37-457e-b852-8f058cb3f160', 'Test Service', 5000.00, 'eastus');
