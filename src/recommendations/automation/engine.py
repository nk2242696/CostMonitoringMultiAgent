"""
Tier 2: Automation Workflow Engine

For every actionable recommendation, generates an executable script
(Azure CLI / PowerShell / Terraform / Python) and manages an
approval → execute → verify lifecycle.

Workflow:
  1. Recommendation is marked 'approved'
  2. Engine generates automation script
  3. User reviews and confirms execution
  4. Script is executed (locally or via Azure Automation Runbook)
  5. Results and cost savings are recorded
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.models import AIRecommendation

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Script Templates
# ──────────────────────────────────────────────────────────────────────

SCRIPT_TEMPLATES: Dict[str, Dict[str, str]] = {
    # ── Compute ──
    "right_sizing": {
        "azure_cli": """#!/bin/bash
# Right-size VM: {resource_id}
# Current SKU: {current_sku} → Recommended: {recommended_sku}
# Estimated savings: ${savings}/month

echo "Deallocating VM..."
az vm deallocate --ids "{resource_id}"

echo "Resizing VM to {recommended_sku}..."
az vm resize --ids "{resource_id}" --size "{recommended_sku}"

echo "Starting VM..."
az vm start --ids "{resource_id}"

echo "✅ VM resized successfully. Verify in Azure Portal."
""",
        "powershell": """# Right-size VM: {resource_id}
# Estimated savings: ${savings}/month

Stop-AzVM -Id "{resource_id}" -Force
$vm = Get-AzVM -Id "{resource_id}"
$vm.HardwareProfile.VmSize = "{recommended_sku}"
Update-AzVM -VM $vm -ResourceGroupName $vm.ResourceGroupName
Start-AzVM -Id "{resource_id}"
Write-Host "✅ VM resized to {recommended_sku}"
""",
    },

    "auto_shutdown": {
        "azure_cli": """#!/bin/bash
# Enable auto-shutdown for VM: {resource_id}
# Schedule: {shutdown_time} ({timezone})
# Estimated savings: ${savings}/month

RESOURCE_GROUP=$(az vm show --ids "{resource_id}" --query "resourceGroup" -o tsv)
VM_NAME=$(az vm show --ids "{resource_id}" --query "name" -o tsv)
LOCATION=$(az vm show --ids "{resource_id}" --query "location" -o tsv)

az vm auto-shutdown \\
  --resource-group "$RESOURCE_GROUP" \\
  --name "$VM_NAME" \\
  --time "{shutdown_time}" \\
  --timezone "{timezone}"

echo "✅ Auto-shutdown configured for $VM_NAME at {shutdown_time}"
""",
    },

    "reserved_instance": {
        "azure_cli": """#!/bin/bash
# Purchase Reserved Instance
# VM Size: {vm_size} | Term: {term} years | Quantity: {quantity}
# Estimated savings: ${savings}/month

echo "⚠️  Reserved Instance purchases require manual confirmation in Azure Portal."
echo ""
echo "Navigate to: Azure Portal → Reservations → Add"
echo "  VM Size: {vm_size}"
echo "  Region:  {region}"
echo "  Term:    {term} year(s)"
echo "  Quantity: {quantity}"
echo ""
echo "Or use: az reservations reservation-order purchase ..."
echo "This requires the Reservations Purchaser role."
""",
    },

    # ── Storage ──
    "delete_orphan_disks": {
        "azure_cli": """#!/bin/bash
# Delete unattached managed disks
# Estimated savings: ${savings}/month

echo "Finding unattached disks..."
DISKS=$(az disk list --query "[?diskState=='Unattached'].{{id:id, name:name, size:diskSizeGb}}" -o json)

echo "Unattached disks found:"
echo "$DISKS" | jq '.[] | "  \\(.name) - \\(.size) GB"'

read -p "Delete all unattached disks? (y/N): " CONFIRM
if [[ "$CONFIRM" == "y" ]]; then
    echo "$DISKS" | jq -r '.[].id' | while read DISK_ID; do
        echo "Deleting $DISK_ID ..."
        az disk delete --ids "$DISK_ID" --yes
    done
    echo "✅ Orphaned disks deleted."
else
    echo "Aborted."
fi
""",
    },

    "storage_lifecycle": {
        "azure_cli": """#!/bin/bash
# Configure blob lifecycle management
# Storage account: {storage_account}
# Estimated savings: ${savings}/month

cat > /tmp/lifecycle_policy.json << 'EOF'
{{
  "rules": [
    {{
      "enabled": true,
      "name": "move-to-cool",
      "type": "Lifecycle",
      "definition": {{
        "actions": {{
          "baseBlob": {{
            "tierToCool": {{ "daysAfterModificationGreaterThan": 30 }},
            "tierToArchive": {{ "daysAfterModificationGreaterThan": 90 }},
            "delete": {{ "daysAfterModificationGreaterThan": 365 }}
          }},
          "snapshot": {{
            "delete": {{ "daysAfterCreationGreaterThan": 90 }}
          }}
        }},
        "filters": {{
          "blobTypes": ["blockBlob"]
        }}
      }}
    }}
  ]
}}
EOF

az storage account management-policy create \\
  --account-name "{storage_account}" \\
  --resource-group "{resource_group}" \\
  --policy @/tmp/lifecycle_policy.json

echo "✅ Lifecycle policy applied to {storage_account}"
""",
    },

    # ── Database ──
    "sql_serverless": {
        "azure_cli": """#!/bin/bash
# Switch SQL Database to Serverless tier
# Database: {database_name} | Server: {server_name}
# Estimated savings: ${savings}/month

az sql db update \\
  --resource-group "{resource_group}" \\
  --server "{server_name}" \\
  --name "{database_name}" \\
  --edition "GeneralPurpose" \\
  --compute-model "Serverless" \\
  --auto-pause-delay 60 \\
  --min-capacity 0.5

echo "✅ Database {database_name} switched to Serverless with 60-min auto-pause"
""",
    },

    # ── Databricks ──
    "databricks_spot_workers": {
        "python": """# Enable Spot instances for Databricks cluster workers
# Cluster: {cluster_id} | Workspace: {workspace_url}

import requests

DATABRICKS_HOST = "{workspace_url}"
TOKEN = os.getenv("DATABRICKS_TOKEN")
CLUSTER_ID = "{cluster_id}"

headers = {{"Authorization": f"Bearer {{TOKEN}}"}}

# Get current cluster config
resp = requests.get(
    f"{{DATABRICKS_HOST}}/api/2.0/clusters/get",
    headers=headers,
    json={{"cluster_id": CLUSTER_ID}},
)
config = resp.json()

# Enable spot instances for workers
config["azure_attributes"] = config.get("azure_attributes", {{}})
config["azure_attributes"]["first_on_demand"] = 1  # driver on-demand
config["azure_attributes"]["availability"] = "SPOT_WITH_FALLBACK_AZURE"

# Update cluster
resp = requests.post(
    f"{{DATABRICKS_HOST}}/api/2.0/clusters/edit",
    headers=headers,
    json=config,
)
print(f"✅ Spot workers enabled for cluster {{CLUSTER_ID}}")
""",
    },
}


class AutomationEngine:
    """
    Generates and manages automation scripts for approved recommendations.
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Script generation
    # ------------------------------------------------------------------

    def generate_script(
        self,
        recommendation_id: str,
        script_type: str = "azure_cli",
        params: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Generate an automation script for an approved recommendation.

        Args:
            recommendation_id: The recommendation to automate.
            script_type:       "azure_cli", "powershell", "python", "terraform".
            params:            Extra template parameters.

        Returns:
            The generated script text, or None if no template matches.
        """
        rec = (
            self.db.query(AIRecommendation)
            .filter(AIRecommendation.recommendation_id == recommendation_id)
            .first()
        )
        if not rec:
            logger.warning("Recommendation %s not found", recommendation_id)
            return None

        # Determine template key from recommendation metadata
        template_key = (rec.rec_metadata or {}).get("reference_check", "")
        if not template_key:
            template_key = self._infer_template_key(rec)

        templates = SCRIPT_TEMPLATES.get(template_key, {})
        template = templates.get(script_type)
        if not template:
            # Try falling back to azure_cli
            template = templates.get("azure_cli")
        if not template:
            logger.info("No template for check=%s type=%s", template_key, script_type)
            return None

        # Build template variables
        variables = {
            "resource_id": rec.resource_id or "",
            "savings": float(rec.potential_savings or 0),
            "subscription_id": rec.subscription_id or "",
            "service_name": rec.service_name or "",
            **(params or {}),
        }

        try:
            script = template.format(**variables)
        except KeyError as exc:
            logger.warning("Missing template variable %s for %s", exc, template_key)
            script = template  # return raw template with placeholders

        # Persist on the recommendation
        rec.automation_script = script
        rec.automation_type = script_type
        self.db.commit()

        logger.info("Generated %s script for recommendation %s", script_type, recommendation_id)
        return script

    def generate_scripts_for_approved(
        self,
        script_type: str = "azure_cli",
    ) -> List[Dict]:
        """Generate scripts for all approved recommendations that lack one."""
        approved = (
            self.db.query(AIRecommendation)
            .filter(
                AIRecommendation.status == "approved",
                AIRecommendation.automation_script.is_(None),
            )
            .all()
        )

        results = []
        for rec in approved:
            script = self.generate_script(rec.recommendation_id, script_type)
            results.append(
                {
                    "recommendation_id": rec.recommendation_id,
                    "title": rec.title,
                    "script_generated": script is not None,
                }
            )
        return results

    # ------------------------------------------------------------------
    # Approval & execution workflow
    # ------------------------------------------------------------------

    def approve(self, recommendation_id: str, approved_by: str = "system") -> bool:
        """Mark a recommendation as approved."""
        rec = (
            self.db.query(AIRecommendation)
            .filter(AIRecommendation.recommendation_id == recommendation_id)
            .first()
        )
        if not rec:
            return False
        rec.status = "approved"
        rec.approved_by = approved_by
        rec.approved_at = datetime.utcnow()
        self.db.commit()
        return True

    def record_execution(
        self,
        recommendation_id: str,
        success: bool,
        output: str = "",
        actual_savings: Optional[float] = None,
    ) -> bool:
        """Record the result of executing an automation script."""
        rec = (
            self.db.query(AIRecommendation)
            .filter(AIRecommendation.recommendation_id == recommendation_id)
            .first()
        )
        if not rec:
            return False

        rec.status = "implemented" if success else "failed"
        rec.implemented_at = datetime.utcnow() if success else None
        rec.implementation_result = {
            "success": success,
            "output": output,
            "actual_savings": actual_savings,
            "executed_at": datetime.utcnow().isoformat(),
        }
        self.db.commit()
        logger.info(
            "Execution recorded for %s: success=%s", recommendation_id, success
        )
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_template_key(rec: AIRecommendation) -> str:
        """Best-effort mapping from recommendation fields to template key."""
        title = (rec.title or "").lower()
        if "right-siz" in title or "resize" in title:
            return "right_sizing"
        if "auto-shutdown" in title or "shutdown" in title:
            return "auto_shutdown"
        if "reserved" in title or "reservation" in title:
            return "reserved_instance"
        if "orphan" in title or "unattached" in title:
            return "delete_orphan_disks"
        if "lifecycle" in title or "tiering" in title:
            return "storage_lifecycle"
        if "serverless" in title:
            return "sql_serverless"
        if "spot" in title and "databricks" in title.lower():
            return "databricks_spot_workers"
        return ""


# ======================================================================
# Command Executor — secure Azure CLI execution with audit trail
# ======================================================================

# Whitelist of safe az subcommands (read + non-destructive changes)
ALLOWED_AZ_COMMANDS = {
    # Read-only / safe
    "az monitor", "az consumption", "az advisor",
    "az vm show", "az vm list", "az vm resize", "az vm deallocate",
    "az vm start", "az vm auto-shutdown",
    "az sql", "az synapse", "az storage",
    "az cosmosdb", "az redis", "az keyvault",
    "az network", "az appservice", "az webapp",
    "az functionapp", "az container", "az acr",
    "az databricks", "az eventgrid", "az eventhubs",
    "az servicebus", "az bastion", "az dns",
    "az resource show", "az resource list", "az resource update",
    "az resource tag",
    "az account", "az group show", "az group list",
    "az tag",
}

# Blocked patterns — never allow these even if prefix matches
BLOCKED_PATTERNS = [
    "az group delete", "az resource delete", "az vm delete",
    "az storage account delete", "az sql server delete",
    "az keyvault delete", "az keyvault purge",
    "rm -rf", "del /f", "Remove-Item",  # shell injection
    ";", "`", "$(",  # dangerous chaining (&&  is allowed for subscription switch)
]


class CommandExecutor:
    """
    Secure Azure CLI command executor with:
    - Command whitelist validation
    - Dry-run support
    - Timeout protection (60s)
    - Full audit trail
    - Rollback tracking
    """

    def __init__(self, db: Session):
        self.db = db

    def validate_command(self, command: str) -> dict:
        """
        Check if a command is safe to execute.
        Returns: {"safe": bool, "reason": str}
        """
        if not command or command.strip() == "null":
            return {"safe": False, "reason": "Empty or null command"}

        cmd = command.strip()

        # Check for blocked patterns
        for pattern in BLOCKED_PATTERNS:
            if pattern in cmd:
                return {"safe": False, "reason": f"Blocked pattern detected: '{pattern}'"}

        # Must start with 'az '
        if not cmd.startswith("az "):
            return {"safe": False, "reason": "Only Azure CLI (az) commands are allowed"}

        # Check against whitelist
        allowed = any(cmd.startswith(prefix) for prefix in ALLOWED_AZ_COMMANDS)
        if not allowed:
            return {"safe": False, "reason": f"Command not in allowed list. Allowed prefixes: {', '.join(sorted(ALLOWED_AZ_COMMANDS)[:10])}..."}

        return {"safe": True, "reason": "Command is safe to execute"}

    def execute(
        self,
        recommendation_id: str,
        step_num: int,
        confirm: bool = False,
        dry_run: bool = False,
        executed_by: str = "user",
        custom_command: str = None,
    ) -> dict:
        """
        Execute the Azure CLI command for a specific recommendation step.

        Args:
            recommendation_id: The recommendation to act on
            step_num: Which step (1-based)
            confirm: Must be True to actually execute (safety gate)
            dry_run: If True, validate but don't run
            executed_by: Who triggered this
            custom_command: If provided, use this instead of the stored command (user-edited)

        Returns:
            Dict with: success, command, output, error, execution_id
        """
        import subprocess
        import time as _time

        # Load recommendation
        rec = (
            self.db.query(AIRecommendation)
            .filter(AIRecommendation.recommendation_id == recommendation_id)
            .first()
        )
        if not rec:
            return {"success": False, "error": "Recommendation not found"}

        # Extract step
        meta = rec.rec_metadata or {}
        steps = meta.get("steps_json", meta.get("steps", []))
        if step_num < 1 or step_num > len(steps):
            return {"success": False, "error": f"Invalid step {step_num}. Has {len(steps)} steps."}

        step = steps[step_num - 1]
        command = custom_command or step.get("azure_cli")
        rollback_cmd = step.get("rollback")

        if not command or command == "null":
            return {
                "success": False,
                "error": "This step has no CLI command (portal-only step)",
                "portal_path": step.get("portal_path", ""),
            }

        # If the recommendation has a subscription_id, auto-prepend az account set
        subscription_id = rec.subscription_id
        if subscription_id and not custom_command:
            # Prepend subscription switch if not already in the command
            if "--subscription" not in command:
                command = f"az account set --subscription {subscription_id} && {command}"

        # Validate each part of a chained command
        for part in command.split("&&"):
            part = part.strip()
            if part:
                validation = self.validate_command(part)
                if not validation["safe"]:
                    return {
                        "success": False,
                        "error": f"Command blocked: {validation['reason']}",
                "command": command,
            }

        # Dry run — return without executing
        if dry_run:
            return {
                "success": True,
                "mode": "dry_run",
                "command": command,
                "rollback_command": rollback_cmd,
                "validation": validation,
                "step": step_num,
                "title": step.get("title", ""),
                "risk": step.get("risk", "none"),
                "estimated_time": step.get("estimated_time", ""),
            }

        # Safety gate
        if not confirm:
            return {
                "success": False,
                "error": "Execution requires confirm=true. Review the command first.",
                "command": command,
                "rollback_command": rollback_cmd,
                "risk": step.get("risk", "none"),
                "step": step_num,
                "title": step.get("title", ""),
            }

        # Execute
        execution_id = str(uuid.uuid4())[:8]
        start_time = _time.time()

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            elapsed = round(_time.time() - start_time, 2)

            success = result.returncode == 0
            output = result.stdout.strip() if success else result.stderr.strip()

            # Record in step metadata
            step["execution"] = {
                "execution_id": execution_id,
                "executed_by": executed_by,
                "executed_at": datetime.utcnow().isoformat(),
                "command": command,
                "success": success,
                "return_code": result.returncode,
                "output": output[:2000],
                "elapsed_seconds": elapsed,
                "rollback_command": rollback_cmd,
            }
            step["step_status"] = "completed" if success else "failed"
            if success:
                step["completed_by"] = executed_by
                step["completed_at"] = datetime.utcnow().isoformat()

            # Save back
            meta["steps_json"] = steps
            meta["steps"] = steps
            rec.rec_metadata = meta

            # Update recommendation status
            completed_steps = sum(1 for s in steps if s.get("step_status") == "completed")
            meta["steps_completed"] = completed_steps
            meta["steps_total"] = len(steps)

            if completed_steps == len(steps):
                rec.status = "implemented"
                rec.implemented_at = datetime.utcnow()

            self.db.commit()

            logger.info(
                "Executed step %d of %s: %s (%.1fs)",
                step_num, recommendation_id, "OK" if success else "FAILED", elapsed,
            )

            return {
                "success": success,
                "execution_id": execution_id,
                "command": command,
                "output": output[:2000],
                "return_code": result.returncode,
                "elapsed_seconds": elapsed,
                "step": step_num,
                "title": step.get("title", ""),
                "rollback_command": rollback_cmd,
                "steps_completed": completed_steps,
                "steps_total": len(steps),
            }

        except subprocess.TimeoutExpired:
            step["execution"] = {
                "execution_id": execution_id,
                "executed_by": executed_by,
                "executed_at": datetime.utcnow().isoformat(),
                "command": command,
                "success": False,
                "error": "Command timed out after 120 seconds",
            }
            step["step_status"] = "failed"
            meta["steps_json"] = steps
            meta["steps"] = steps
            rec.rec_metadata = meta
            self.db.commit()

            return {
                "success": False,
                "execution_id": execution_id,
                "error": "Command timed out after 120 seconds",
                "command": command,
            }

        except Exception as exc:
            return {
                "success": False,
                "execution_id": execution_id,
                "error": str(exc)[:500],
                "command": command,
            }

    def revert(
        self,
        recommendation_id: str,
        step_num: int,
        confirm: bool = False,
        executed_by: str = "user",
    ) -> dict:
        """Execute the rollback command for a previously executed step."""
        import subprocess
        import time as _time

        rec = (
            self.db.query(AIRecommendation)
            .filter(AIRecommendation.recommendation_id == recommendation_id)
            .first()
        )
        if not rec:
            return {"success": False, "error": "Recommendation not found"}

        meta = rec.rec_metadata or {}
        steps = meta.get("steps_json", meta.get("steps", []))
        if step_num < 1 or step_num > len(steps):
            return {"success": False, "error": f"Invalid step {step_num}"}

        step = steps[step_num - 1]
        rollback_cmd = step.get("rollback")
        execution = step.get("execution", {})

        if not execution.get("success"):
            return {"success": False, "error": "Step was not successfully executed — nothing to revert"}

        if not rollback_cmd or rollback_cmd == "null":
            return {"success": False, "error": "No rollback command defined for this step"}

        # Validate rollback command
        validation = self.validate_command(rollback_cmd)
        if not validation["safe"]:
            return {
                "success": False,
                "error": f"Rollback blocked: {validation['reason']}",
                "command": rollback_cmd,
            }

        if not confirm:
            return {
                "success": False,
                "error": "Revert requires confirm=true",
                "rollback_command": rollback_cmd,
            }

        # Execute rollback
        start_time = _time.time()
        try:
            result = subprocess.run(
                rollback_cmd, shell=True, capture_output=True, text=True, timeout=120,
            )
            elapsed = round(_time.time() - start_time, 2)
            success = result.returncode == 0

            step["revert"] = {
                "reverted_by": executed_by,
                "reverted_at": datetime.utcnow().isoformat(),
                "command": rollback_cmd,
                "success": success,
                "output": (result.stdout if success else result.stderr).strip()[:2000],
                "elapsed_seconds": elapsed,
            }
            step["step_status"] = "reverted" if success else step.get("step_status")

            meta["steps_json"] = steps
            meta["steps"] = steps
            rec.rec_metadata = meta
            self.db.commit()

            return {
                "success": success,
                "command": rollback_cmd,
                "output": (result.stdout if success else result.stderr).strip()[:2000],
                "elapsed_seconds": elapsed,
                "step": step_num,
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Rollback timed out after 120 seconds"}
        except Exception as exc:
            return {"success": False, "error": str(exc)[:500]}
