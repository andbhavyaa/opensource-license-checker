#!/usr/bin/env python3
"""
OpenSource License & IP Checker
Main application with CLI and FastAPI web interface
"""

import os
import sys
import json
import tempfile
import zipfile
import argparse
import logging
import shutil
from pathlib import Path
from typing import Optional

import git
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from portia import Config
from portia.builder.plan_builder_v2 import PlanBuilderV2

from agents import ScannerAgent, ComplianceAgent, AdvisorAgent
from utils import setup_logging, download_github_repo, extract_zip

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="License Checker", description="OpenSource License & IP Checker")

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Portia configuration
def get_portia_config():
    """Initialize Portia config with API keys from environment"""
    try:
        # Try Google Gemini first (FREE tier available!)
        if os.getenv("GOOGLE_API_KEY"):
            logger.info("Using Google Gemini API (Free tier)")
            return Config.from_default(llm_provider="google")
        else:
            logger.error("No API key found. Set one of: GOOGLE_API_KEY (FREE)")
            logger.error("Get free Google API key at: https://makersuite.google.com/app/apikey")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to initialize Portia config: {e}")
        sys.exit(1)

def run_license_check(repo_path: str, output_dir: str = "out") -> dict:
    """
    Run the complete license checking workflow
    """
    config = get_portia_config()
    Path(output_dir).mkdir(exist_ok=True)

    try:
        # Initialize agents
        scanner = ScannerAgent(config)
        compliance = ComplianceAgent(config)
        advisor = AdvisorAgent(config)

        logger.info(f"🔍 Scanning repository: {repo_path}")

        # Step 1: Scan for dependencies
        scan_result = scanner.scan_dependencies(repo_path)
        if not scan_result.get("success"):
            raise Exception(f"Scan failed: {scan_result.get('error')}")

        dependencies = scan_result.get("dependencies", [])
        logger.info(f"📦 Found {len(dependencies)} dependencies")

        # Step 2: Check compliance
        compliance_result = compliance.check_licenses(dependencies)
        if not compliance_result.get("success"):
            raise Exception(f"Compliance check failed: {compliance_result.get('error')}")

        # Step 3: Generate advice and reports
        advice_result = advisor.generate_report(dependencies, compliance_result)
        if not advice_result.get("success"):
            raise Exception(f"Report generation failed: {advice_result.get('error')}")

        # ✅ Now save reports
        report_data = advice_result.get("report", {})

        json_path = Path(output_dir) / "report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        md_path = Path(output_dir) / "report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report_data.get("markdown", ""))

        logger.info(f"✅ Reports saved to {output_dir}/")
        logger.info(f"📄 JSON: {json_path}")
        logger.info(f"📝 Markdown: {md_path}")

        return {
            "success": True,
            "report": report_data,
            "output_dir": str(output_dir),
            "json_path": str(json_path),
            "md_path": str(md_path)
        }

    except Exception as e:
        logger.error(f"❌ License check failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# CLI Interface
def main_cli():
    """CLI interface for license checking"""
    parser = argparse.ArgumentParser(description="OpenSource License & IP Checker")
    parser.add_argument("command", choices=["run"], help="Command to execute")
    parser.add_argument("--repo", required=True, help="Repository path or GitHub URL")
    parser.add_argument("--output", default="out", help="Output directory for reports")
    
    args = parser.parse_args()
    
    if args.command == "run":
        repo_input = args.repo
        temp_dir = None
        
        try:
            # Handle the GitHub URLs
            if repo_input.startswith("https://github.com"):
                print(f"📥 Downloading repository: {repo_input}")
                temp_dir = tempfile.mkdtemp()
                repo_path = download_github_repo(repo_input, temp_dir)
            else:
                repo_path = repo_input
            
            # Check if path exists
            if not os.path.exists(repo_path):
                print(f"❌ Repository path not found: {repo_path}")
                sys.exit(1)
            
            # Run the analysis
            result = run_license_check(repo_path, args.output)
            
            if result["success"]:
                print(f"\n🎉 Analysis complete!")
                print(f"📊 View report: {result['md_path']}")
            else:
                print(f"❌ Analysis failed: {result['error']}")
                sys.exit(1)
                
        except KeyboardInterrupt:
            print("\n⚠️ Analysis interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)
        finally:
            # Cleanup temp directory
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

# Routing
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with upload form"""
    return templates.TemplateResponse("report.html", {
        "request": request,
        "show_form": True
    })

@app.post("/analyze")
async def analyze_repository(
    request: Request,
    github_url: Optional[str] = Form(None),
    zip_file: Optional[UploadFile] = File(None)
):
    """Analyze repository from GitHub URL or uploaded ZIP"""
    
    if not github_url and not zip_file:
        raise HTTPException(status_code=400, detail="Provide either GitHub URL or ZIP file")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Handle input
        if github_url:
            if not github_url.startswith("https://github.com"):
                raise HTTPException(status_code=400, detail="Invalid GitHub URL")
            repo_path = download_github_repo(github_url, temp_dir)
            source = github_url
        else:
            # Handle ZIP file
            zip_path = os.path.join(temp_dir, "repo.zip")
            with open(zip_path, "wb") as f:
                content = await zip_file.read()
                f.write(content)
            repo_path = extract_zip(zip_path, temp_dir)
            source = zip_file.filename
        
        # Run analysis
        result = run_license_check(repo_path, temp_dir)
        
        if result["success"]:
            report = result["report"]
            return templates.TemplateResponse("report.html", {
                "request": request,
                "show_form": False,
                "report": report,
                "source": source,
                "success": True
            })
        else:
            return templates.TemplateResponse("report.html", {
                "request": request,
                "show_form": True,
                "error": result["error"],
                "success": False
            })
            
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return templates.TemplateResponse("report.html", {
            "request": request,
            "show_form": True,
            "error": str(e),
            "success": False
        })
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "license-checker"}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # CLI mode
        main_cli()
    else:
        # Web server mode
        print("🚀 Starting License Checker Web Server")
        print("📝 Open http://localhost:8000 in your browser")
        uvicorn.run(app, host="0.0.0.0", port=8000)
