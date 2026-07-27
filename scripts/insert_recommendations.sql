INSERT INTO ai_recommendations (
    subscription_id, service_name, current_cost, potential_savings, savings_percentage, 
    title, recommendation_text, priority, category, action_items, implementation_effort, source, status
) VALUES
(
    '518f04e9-default', 
    'Microsoft.Sql', 
    913.50, 
    365.40, 
    40.0, 
    'Switch to Azure SQL Reserved Capacity', 
    'Switch to Azure SQL Reserved Capacity for your Microsoft.Sql service and evaluate if scaling down to a lower service tier based on actual usage patterns aligns with your performance requirements. This approach adheres to the Well-Architected Framework Cost Optimization pillar by ensuring you pay only for what you need while maintaining performance',
    'high', 
    'reserved_instances', 
    '["Navigate to Azure portal - Cost Management + Billing - Reservations", "Review Azure Advisor cost recommendations for SQL databases", "Purchase 3-year Reserved Capacity for production databases", "Monitor performance after tier adjustment", "Set up cost alerts for SQL spending"]'::jsonb, 
    '2-4 hours', 
    'azure_openai', 
    'pending'
),
(
    '518f04e9-default', 
    'Microsoft.Compute', 
    491.00, 
    245.50, 
    50.0, 
    'Utilize Reserved VM Instances', 
    'Utilize Reserved VM Instances for consistent workloads in Microsoft.Compute, opting for 3-year reservations to maximize savings. Additionally, consider right-sizing VMs to match actual workload demands, as per Azure Well-Architected Framework principles',
    'high', 
    'reserved_instances', 
    '["Navigate to Azure portal - Virtual Machines - Identify always-on VMs", "Purchase 3-year Reserved VM Instances for production VMs", "Use Azure Advisor to identify right-sizing opportunities", "Implement auto-shutdown for dev/test VMs", "Monitor VM utilization with Azure Monitor"]'::jsonb, 
    '2-3 hours', 
    'azure_openai', 
    'pending'
),
(
    '518f04e9-default', 
    'Microsoft.Web', 
    246.90, 
    98.76, 
    40.0, 
    'Switch to Basic Tier and evaluate App Service Plans', 
    'Switch Microsoft.Web App Service to the Basic tier if using Standard tier and evaluate Azure App Service Reserved Instances for consistent workloads. This aligns with the Azure Well-Architected Framework by optimizing cost without sacrificing essential functionality',
    'medium', 
    'tier_optimization', 
    '["Navigate to Azure portal - App Services - Review current tier", "Evaluate if Basic tier meets requirements", "Purchase App Service Reserved Instances for production apps", "Review Azure Advisor recommendations", "Monitor app performance after changes"]'::jsonb, 
    '1-2 hours', 
    'azure_openai', 
    'pending'
),
(
    '518f04e9-default', 
    'Microsoft.Storage', 
    174.60, 
    43.65, 
    25.0, 
    'Implement lifecycle management policies', 
    'Implement lifecycle management policies to move data to cooler storage tiers. Delete old snapshots and move infrequently accessed data to Cool or Archive tier. Consider Azure Blob Storage lifecycle management to automate these transitions following Well-Architected Framework guidelines',
    'low', 
    'tier_optimization', 
    '["Navigate to Azure portal - Storage Accounts - Lifecycle Management", "Create policies to move old data to Cool tier after 30 days", "Move archival data to Archive tier after 90 days", "Delete old snapshots and unused blobs", "Monitor storage costs with Cost Management"]'::jsonb, 
    '2-4 hours', 
    'azure_openai', 
    'pending'
);
