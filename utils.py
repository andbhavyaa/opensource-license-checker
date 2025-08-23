"""
Utility functions for license checking
"""

import os
import json
import re
import tempfile
import shutil
import zipfile
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import git
import yaml
import requests

# Configure logging
def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

# License compliance rules
LICENSE_RULES = {
    # Approved licenses (low risk)
    "approved": [
        "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
        "Apache", "BSD", "MIT License", "Apache License", "BSD License"
    ],
    
    # Warning licenses (medium risk - copyleft but not viral)
    "warning": [
        "LGPL-2.1", "LGPL-3.0", "MPL-2.0", "EPL-1.0", "EPL-2.0",
        "LGPL", "MPL", "EPL", "Mozilla Public License"
    ],
    
    # Blocked licenses (high risk - strong copyleft)
    "blocked": [
        "GPL-2.0", "GPL-3.0", "AGPL-3.0", "GPL", "AGPL",
        "GNU General Public License", "GNU Affero General Public License"
    ]
}

# Risk level colors for UI
RISK_COLORS = {
    "high": "#dc2626",      # Red
    "medium": "#ea580c",    # Orange  
    "low": "#16a34a",       # Green
    "unknown": "#6b7280"    # Gray
}

def get_license_risk(license_id: str) -> Tuple[str, str]:
    """
    Determine risk level for a license
    
    Args:
        license_id: License identifier
        
    Returns:
        Tuple of (risk_level, reason)
    """
    if not license_id or license_id.lower() in ["unknown", "none", ""]:
        return "unknown", "License not detected"
    
    # Normalize license for comparison
    license_norm = license_id.strip()
    
    # Check against rules
    for level, licenses in LICENSE_RULES.items():
        for rule_license in licenses:
            if rule_license.lower() in license_norm.lower():
                reasons = {
                    "approved": "Permissive license, commercial use allowed",
                    "warning": "Copyleft license, may require source disclosure", 
                    "blocked": "Strong copyleft, incompatible with proprietary use"
                }
                return level, reasons[level]
    
    return "unknown", "License not recognized, manual review required"

def parse_requirements_txt(file_path: str) -> List[Dict]:
    """Parse Python requirements.txt file"""
    dependencies = []
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            # Handle various formats: package==1.0, package>=1.0, package, etc.
            match = re.match(r'^([a-zA-Z0-9\-_.]+)([>=<~!]+.*)?$', line)
            if match:
                name = match.group(1)
                version = match.group(2).strip('>=<~!=') if match.group(2) else "Unknown"
                
                dependencies.append({
                    "name": name,
                    "version": version,
                    "ecosystem": "Python/pip",
                    "license": get_package_license(name, "pypi")
                })
    
    except Exception as e:
        print(f"Error parsing requirements.txt: {e}")
    
    return dependencies

def parse_package_json(file_path: str) -> List[Dict]:
    """Parse Node.js package.json file"""
    dependencies = []
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Get dependencies and devDependencies
        all_deps = {}
        all_deps.update(data.get("dependencies", {}))
        all_deps.update(data.get("devDependencies", {}))
        
        for name, version in all_deps.items():
            dependencies.append({
                "name": name,
                "version": version.lstrip('^~>=<'),
                "ecosystem": "Node.js/npm",
                "license": get_package_license(name, "npm")
            })
    
    except Exception as e:
        print(f"Error parsing package.json: {e}")
    
    return dependencies

def parse_cargo_toml(file_path: str) -> List[Dict]:
    """Parse Rust Cargo.toml file"""
    dependencies = []
    
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)  # TOML is similar enough for basic parsing
        
        deps = data.get("dependencies", {})
        for name, version_info in deps.items():
            if isinstance(version_info, str):
                version = version_info
            elif isinstance(version_info, dict):
                version = version_info.get("version", "Unknown")
            else:
                version = "Unknown"
            
            dependencies.append({
                "name": name,
                "version": version.lstrip('^~>=<'),
                "ecosystem": "Rust/cargo",
                "license": get_package_license(name, "crates")
            })
    
    except Exception as e:
        print(f"Error parsing Cargo.toml: {e}")
    
    return dependencies

def parse_go_mod(file_path: str) -> List[Dict]:
    """Parse Go go.mod file"""
    dependencies = []
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        in_require_block = False
        for line in lines:
            line = line.strip()
            
            if line.startswith("require ("):
                in_require_block = True
                continue
            elif line == ")":
                in_require_block = False
                continue
            
            if in_require_block or line.startswith("require "):
                # Remove "require " prefix if present
                if line.startswith("require "):
                    line = line[8:]
                
                # Parse module and version
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    version = parts[1].lstrip('v')
                    
                    dependencies.append({
                        "name": name,
                        "version": version,
                        "ecosystem": "Go/modules",
                        "license": get_package_license(name, "go")
                    })
    
    except Exception as e:
        print(f"Error parsing go.mod: {e}")
    
    return dependencies

def get_package_license(package_name: str, ecosystem: str) -> str:
    """
    Attempt to get license for a package (simplified heuristic)
    In a real implementation, this would query package registries
    """
    # Common packages with known licenses (for demo purposes)
    known_licenses = {
        # Python packages
        "requests": "Apache-2.0",
        "flask": "BSD-3-Clause", 
        "django": "BSD-3-Clause",
        "numpy": "BSD-3-Clause",
        "pandas": "BSD-3-Clause",
        "fastapi": "MIT",
        "click": "BSD-3-Clause",
        "jinja2": "BSD-3-Clause",
        "pyyaml": "MIT",
        "pytest": "MIT",
        
        # Node.js packages  
        "express": "MIT",
        "react": "MIT",
        "lodash": "MIT",
        "axios": "MIT",
        "webpack": "MIT",
        "eslint": "MIT",
        
        # Go packages
        "github.com/gin-gonic/gin": "MIT",
        "github.com/gorilla/mux": "BSD-3-Clause",
        
        # Rust packages
        "serde": "MIT",
        "tokio": "MIT",
        "clap": "MIT"
    }
    
    return known_licenses.get(package_name, "Unknown")

def download_github_repo(github_url: str, temp_dir: str) -> str:
    """Download GitHub repository to temporary directory"""
    try:
        # Extract owner/repo from URL
        match = re.match(r'https://github\.com/([^/]+)/([^/]+)', github_url)
        if not match:
            raise ValueError("Invalid GitHub URL format")
        
        owner, repo = match.groups()
        repo = repo.replace('.git', '')  # Remove .git suffix if present
        
        # Clone repository
        repo_path = os.path.join(temp_dir, f"{owner}-{repo}")
        git.Repo.clone_from(github_url, repo_path, depth=1)
        
        return repo_path
        
    except Exception as e:
        raise Exception(f"Failed to download repository: {e}")

def extract_zip(zip_path: str, temp_dir: str) -> str:
    """Extract ZIP file to temporary directory"""
    try:
        extract_path = os.path.join(temp_dir, "extracted")
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        
        # Find the root directory (usually the first subdirectory)
        items = os.listdir(extract_path)
        if len(items) == 1 and os.path.isdir(os.path.join(extract_path, items[0])):
            return os.path.join(extract_path, items[0])
        else:
            return extract_path
            
    except Exception as e:
        raise Exception(f"Failed to extract ZIP file: {e}")

