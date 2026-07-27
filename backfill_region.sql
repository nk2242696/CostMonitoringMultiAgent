-- Backfill region column based on resource_group names
UPDATE azure_costs SET region = 
  CASE 
    WHEN LOWER(resource_group) LIKE '%eastus2%' THEN 'eastus2'
    WHEN LOWER(resource_group) LIKE '%eastus%' THEN 'eastus'
    WHEN LOWER(resource_group) LIKE '%westus3%' OR LOWER(resource_group) LIKE '%wus3%' THEN 'westus3'
    WHEN LOWER(resource_group) LIKE '%westus2%' THEN 'westus2'
    WHEN LOWER(resource_group) LIKE '%westus%' THEN 'westus'
    WHEN LOWER(resource_group) LIKE '%centralus%' THEN 'centralus'
    WHEN LOWER(resource_group) LIKE '%northcentralus%' THEN 'northcentralus'
    WHEN LOWER(resource_group) LIKE '%southcentralus%' THEN 'southcentralus'
    WHEN LOWER(resource_group) LIKE '%westcentralus%' THEN 'westcentralus'
    WHEN LOWER(resource_group) LIKE '%europe%' OR LOWER(resource_group) LIKE '%eu%' THEN 'westeurope'
    ELSE 'unknown'
  END
WHERE region IS NULL;

SELECT COUNT(*) as updated_rows FROM azure_costs WHERE region IS NOT NULL;
