"""
Portia agents for license checking workflow
"""

import os
import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from portia import Config
from portia.builder.plan_builder_v2 import PlanBuilderV2 as Agent
from utils import (
    parse_requirements_txt, parse_package_json, parse_cargo_toml, 
    parse_go_mod, get_license_risk, RISK_COLORS
)

class ScannerAgent(Agent):
    """Agent to scan repositories and extract dependencies"""
    
    def __init__(self, config: Config):
        # Pass both a label and the config to the parent constructor
        super().__init__(label="Scanner Agent")
        self.name = "Scanner Agent"
        
    def scan_dependencies(self, repo_path: str) -> Dict[str, Any]:
        """
        Scan repository for dependency files and extract dependencies
        
        Args:
            repo_path: Path to repository
            
        Returns:
            Dictionary with scan results
        """
        try:
            dependencies = []
            files_found = []
            
            repo_path = Path(repo_path)
            
            # Scan for different dependency files
            scanners = [
                ("requirements.txt", parse_requirements_txt),
                ("package.json", parse_package_json),
                ("Cargo.toml", parse_cargo_toml),
                ("go.mod", parse_go_mod),
            ]
            
            for filename, parser in scanners:
                # Search for files recursively
                for file_path in repo_path.glob(f"**/{filename}"):
                    print(f"📄 Found {file_path.relative_to(repo_path)}")
                    files_found.append(str(file_path.relative_to(repo_path)))
                    try:
                        deps = parser(str(file_path))
                        dependencies.extend(deps)
                        print(f"   └─ Extracted {len(deps)} dependencies")
                    except Exception as e:
                        print(f"   └─ ⚠️  Failed to parse {filename}: {e}")
            
            if not files_found:
                print("⚠️  No dependency files found")
                return {
                    "success": True,
                    "dependencies": [],
                    "files_found": [],
                    "message": "No dependency files found"
                }
            
            # Remove duplicates
            unique_deps = {}
            for dep in dependencies:
                key = f"{dep['name']}-{dep['ecosystem']}"
                if key not in unique_deps:
                    unique_deps[key] = dep
            
            final_deps = list(unique_deps.values())
            
            return {
                "success": True,
                "dependencies": final_deps,
                "files_found": files_found,
                "total_dependencies": len(final_deps)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to scan dependencies: {e}",
                "dependencies": []
            }

class ComplianceAgent(Agent):
    """Agent to check license compliance"""
    
    def __init__(self, config: Config):
        # Pass both a label and the config to the parent constructor
        super().__init__(label="Compliance Agent")
        self.name = "Compliance Agent"
        
    def check_licenses(self, dependencies: List[Dict]) -> Dict[str, Any]:
        """
        Check license compliance for dependencies
        
        Args:
            dependencies: List of dependency dictionaries
            
        Returns:
            Dictionary with compliance results
        """
        try:
            results = {
                "total": len(dependencies),
                "approved": 0,
                "warning": 0,
                "blocked": 0,
                "unknown": 0,
                "dependencies": [],
                "risks": {
                    "high": [],
                    "medium": [],
                    "low": []
                }
            }
            
            for dep in dependencies:
                license_id = dep.get("license", "Unknown")
                risk_level, risk_reason = get_license_risk(license_id)
                
                dep_result = {
                    "name": dep["name"],
                    "version": dep.get("version", "Unknown"),
                    "ecosystem": dep["ecosystem"],
                    "license": license_id,
                    "risk_level": risk_level,
                    "risk_reason": risk_reason
                }
                
                results["dependencies"].append(dep_result)
                
                # Count by risk level
                if risk_level == "approved":
                    results["approved"] += 1
                    results["risks"]["low"].append(dep_result)
                elif risk_level == "warning":
                    results["warning"] += 1
                    results["risks"]["medium"].append(dep_result)
                elif risk_level == "blocked":
                    results["blocked"] += 1
                    results["risks"]["high"].append(dep_result)
                else:  # unknown
                    results["unknown"] += 1
                    results["risks"]["medium"].append(dep_result)
            
            return {
                "success": True,
                "compliance": results
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to check compliance: {e}"
            }

class AdvisorAgent(Agent):
    """Agent to generate reports and recommendations"""
    
    def __init__(self, config: Config):
        # Pass both a label and the config to the parent constructor
        super().__init__(label="Advisor Agent")
        self.name = "Advisor Agent"
        
    def generate_report(self, dependencies: List[Dict], compliance_result: Dict) -> Dict[str, Any]:
        """
        Generate comprehensive report with recommendations
        
        Args:
            dependencies: Original dependencies list
            compliance_result: Results from compliance check
            
        Returns:
            Dictionary with report data
        """
        try:
            compliance = compliance_result.get("compliance", {})
            
            # Generate summary
            total = compliance.get("total", 0)
            approved = compliance.get("approved", 0)
            warning = compliance.get("warning", 0)
            blocked = compliance.get("blocked", 0)
            unknown = compliance.get("unknown", 0)
            
            # Calculate percentages
            approved_pct = (approved / total * 100) if total > 0 else 0
            warning_pct = (warning / total * 100) if total > 0 else 0
            blocked_pct = (blocked / total * 100) if total > 0 else 0
            
            # Determine overall risk
            if blocked > 0:
                overall_risk = "HIGH"
                risk_color = RISK_COLORS["high"]
            elif warning > 0 or unknown > 0:
                overall_risk = "MEDIUM"
                risk_color = RISK_COLORS["medium"]
            else:
                overall_risk = "LOW"
                risk_color = RISK_COLORS["low"]
            
            # Generate recommendations
            recommendations = self._generate_recommendations(compliance)
            
            # Generate markdown report
            markdown = self._generate_markdown_report(compliance, recommendations, overall_risk)
            
            report = {
                "summary": {
                    "total_dependencies": total,
                    "approved": approved,
                    "warning": warning,
                    "blocked": blocked,
                    "unknown": unknown,
                    "approved_percentage": round(approved_pct, 1),
                    "warning_percentage": round(warning_pct, 1),
                    "blocked_percentage": round(blocked_pct, 1),
                    "overall_risk": overall_risk,
                    "risk_color": risk_color
                },
                "compliance": compliance,
                "recommendations": recommendations,
                "markdown": markdown,
                "generated_at": self._get_timestamp()
            }
            
            return {
                "success": True,
                "report": report
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate report: {e}"
            }
    
    def _generate_recommendations(self, compliance: Dict) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        blocked = compliance.get("blocked", 0)
        unknown = compliance.get("unknown", 0)
        warning = compliance.get("warning", 0)
        
        if blocked > 0:
            recommendations.append(
                f"🚫 CRITICAL: {blocked} blocked license(s) detected. "
                "Replace these dependencies with alternatives having MIT/Apache/BSD licenses."
            )
        
        if unknown > 0:
            recommendations.append(
                f"❓ {unknown} dependencies have unknown licenses. "
                "Manually verify licensing terms before use."
            )
        
        if warning > 0:
            recommendations.append(
                f"⚠️  {warning} dependencies have warning licenses (LGPL/MPL/EPL). "
                "Review copyleft requirements for your use case."
            )
        
        # Get specific blocked packages
        high_risk = compliance.get("risks", {}).get("high", [])
        if high_risk:
            blocked_names = [dep["name"] for dep in high_risk]
            recommendations.append(
                f"📦 Consider replacing: {', '.join(blocked_names[:3])}"
                + ("..." if len(blocked_names) > 3 else "")
            )
        
        if not recommendations:
            recommendations.append("✅ All dependencies have approved licenses. Good to go!")
        
        return recommendations
    
    def _generate_markdown_report(self, compliance: Dict, recommendations: List[str], overall_risk: str) -> str:
        """Generate markdown report"""
        
        total = compliance.get("total", 0)
        approved = compliance.get("approved", 0)
        warning = compliance.get("warning", 0)
        blocked = compliance.get("blocked", 0)
        unknown = compliance.get("unknown", 0)
        
        # Handle division by zero if total is 0
        approved_pct = (approved / total * 100) if total > 0 else 0
        warning_pct = (warning / total * 100) if total > 0 else 0
        blocked_pct = (blocked / total * 100) if total > 0 else 0
        unknown_pct = (unknown / total * 100) if total > 0 else 0
        
        md = f"""# 📊 License Compliance Report

## Summary

- **Total Dependencies**: {total}
- **Overall Risk**: {overall_risk}
- **Approved Licenses**: {approved} ({approved_pct:.1f}%)
- **Warning Licenses**: {warning} ({warning_pct:.1f}%)
- **Blocked Licenses**: {blocked} ({blocked_pct:.1f}%)
- **Unknown Licenses**: {unknown} ({unknown_pct:.1f}%)

## Recommendations

"""
        
        for rec in recommendations:
            md += f"- {rec}\n"
        
        # High risk dependencies
        high_risk = compliance.get("risks", {}).get("high", [])
        if high_risk:
            md += f"\n## 🚨 High Risk Dependencies ({len(high_risk)})\n\n"
            for dep in high_risk:
                md += f"- **{dep['name']}** v{dep.get('version', 'N/A')} - {dep['license']} ({dep['risk_reason']})\n"
        
        # Medium risk dependencies
        medium_risk = compliance.get("risks", {}).get("medium", [])
        if medium_risk:
            md += f"\n## ⚠️ Medium Risk Dependencies ({len(medium_risk)})\n\n"
            for dep in medium_risk[:10]:  # Limit to first 10
                md += f"- **{dep['name']}** v{dep.get('version', 'N/A')} - {dep['license']} ({dep['risk_reason']})\n"
            if len(medium_risk) > 10:
                md += f"- ... and {len(medium_risk) - 10} more\n"
        
        # All dependencies table
        md += f"\n## 📦 All Dependencies ({total})\n\n"
        md += "| Package | Version | License | Risk | Reason |\n"
        md += "|---------|---------|---------|------|--------|\n"
        
        for dep in compliance.get("dependencies", []):
            risk_icon = {"approved": "✅", "warning": "⚠️", "blocked": "🚫", "unknown": "❓"}.get(dep["risk_level"], "❓")
            md += f"| {dep['name']} | {dep.get('version', 'N/A')} | {dep['license']} | {risk_icon} {dep['risk_level'].title()} | {dep['risk_reason']} |\n"
        
        md += f"\n---\n*Report generated at {self._get_timestamp()}*\n"
        
        return md
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
