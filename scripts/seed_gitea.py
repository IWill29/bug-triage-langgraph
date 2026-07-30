#!/usr/bin/env python3
"""
Seed Gitea with Set A issues
Loads existing issues for duplicate detection testing
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.gitea_service import GiteaService
from src.config import settings
from src.utils.logging import setup_logging, logger


# Set A issues to preload
SET_A_ISSUES = [
    {
        "title": "Login button unresponsive on mobile Safari",
        "body": """Multiple users report that on iOS Safari the "Log in" button does nothing when tapped.
Works fine on desktop Chrome. Started after the 3.4 release.

**Steps to reproduce:**
1. Open app in iOS Safari
2. Enter credentials
3. Tap login button
4. Nothing happens

**Expected:** User should be logged in
**Actual:** Button click has no effect""",
        "labels": ["frontend", "auth", "high"],
        "id": "EXIST-1"
    },
    {
        "title": "CSV export times out for large datasets",
        "body": """Exporting a report with more than ~50k rows spins for a while and then returns a 504.
Smaller exports are fine.

**Steps to reproduce:**
1. Navigate to Reports > Export
2. Select dataset with 50k+ rows
3. Click "Export as CSV"
4. Wait

**Expected:** CSV download starts
**Actual:** 504 Gateway Timeout after ~60 seconds""",
        "labels": ["backend", "medium"],
        "id": "EXIST-2"
    },
    {
        "title": "Password reset email never arrives",
        "body": """Requesting a password reset shows a success message but no email is ever delivered.
Checked spam. Happens for at least three different users.

**Steps to reproduce:**
1. Go to login page
2. Click "Forgot password"
3. Enter email address
4. Submit

**Expected:** Reset email delivered within minutes
**Actual:** No email received (checked spam folder)""",
        "labels": ["backend", "auth", "high"],
        "id": "EXIST-3"
    },
    {
        "title": "Dashboard charts render blank on first load",
        "body": """On first page load the dashboard charts are empty. A manual refresh fixes it.
Seems like a race with the data fetch.

**Steps to reproduce:**
1. Navigate to /dashboard
2. Observe empty charts
3. Refresh page
4. Charts now display correctly

**Expected:** Charts load with data on first visit
**Actual:** Charts are blank until manual refresh""",
        "labels": ["frontend", "medium"],
        "id": "EXIST-4"
    }
]


async def seed_gitea():
    """
    Seed Gitea with Set A issues
    """
    setup_logging()
    
    logger.info(
        "seed_gitea_start",
        gitea_url=settings.gitea_url,
        repo=f"{settings.gitea_repo_owner}/{settings.gitea_repo_name}"
    )
    
    gitea = GiteaService()
    
    try:
        # Check if issues already exist
        existing_issues = await gitea.list_issues(state="all")
        
        if len(existing_issues) >= len(SET_A_ISSUES):
            logger.info(
                "seed_gitea_skip",
                reason="Issues already exist",
                count=len(existing_issues)
            )
            return
        
        # Create issues
        created_count = 0
        for issue_data in SET_A_ISSUES:
            logger.info(
                "creating_issue",
                id=issue_data["id"],
                title=issue_data["title"]
            )
            
            try:
                result = await gitea.create_issue(
                    title=issue_data["title"],
                    body=issue_data["body"],
                    labels=issue_data["labels"]
                )
                
                created_count += 1
                
                logger.info(
                    "issue_created",
                    id=issue_data["id"],
                    issue_number=result.get("number"),
                    url=result.get("html_url")
                )
                
            except Exception as e:
                logger.error(
                    "issue_creation_failed",
                    id=issue_data["id"],
                    error=str(e)
                )
        
        logger.info(
            "seed_gitea_complete",
            created_count=created_count,
            total=len(SET_A_ISSUES)
        )
        
    except Exception as e:
        logger.error(
            "seed_gitea_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise
    
    finally:
        await gitea.close()


if __name__ == "__main__":
    asyncio.run(seed_gitea())
