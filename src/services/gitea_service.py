"""
Gitea API client
Handles issue creation and management
"""

import httpx
from typing import Optional, List, Dict, Any

from src.config import settings
from src.utils.logging import logger


class GiteaService:
    """
    Gitea API client for issue management
    """
    
    def __init__(self):
        """Initialize HTTP client with authentication"""
        self.base_url = settings.gitea_url
        self.token = settings.gitea_token
        self.repo_owner = settings.gitea_repo_owner
        self.repo_name = settings.gitea_repo_name
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"token {self.token}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
    
    async def create_issue(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create new issue in Gitea
        
        Args:
            title: Issue title
            body: Issue description
            labels: List of label names to apply
            
        Returns:
            Created issue data with URL
        """
        logger.info(
            "gitea_create_issue",
            title=title,
            labels=labels or []
        )
        
        url = f"/api/v1/repos/{self.repo_owner}/{self.repo_name}/issues"
        
        payload = {
            "title": title,
            "body": body,
            "labels": [self._get_label_id(label) for label in (labels or [])]
        }
        
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        
        issue_data = response.json()
        
        logger.info(
            "gitea_issue_created",
            issue_id=issue_data.get("number"),
            issue_url=issue_data.get("html_url")
        )
        
        return issue_data
    
    async def add_comment(
        self,
        issue_id: int,
        body: str
    ) -> Dict[str, Any]:
        """
        Add comment to existing issue
        
        Args:
            issue_id: Issue number
            body: Comment text
            
        Returns:
            Created comment data
        """
        logger.info(
            "gitea_add_comment",
            issue_id=issue_id
        )
        
        url = f"/api/v1/repos/{self.repo_owner}/{self.repo_name}/issues/{issue_id}/comments"
        
        payload = {"body": body}
        
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        
        return response.json()
    
    async def list_issues(
        self,
        state: str = "open",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List issues in repository
        
        Args:
            state: Issue state (open, closed, all)
            limit: Max number of issues to return
            
        Returns:
            List of issue data
        """
        url = f"/api/v1/repos/{self.repo_owner}/{self.repo_name}/issues"
        
        params = {
            "state": state,
            "limit": limit
        }
        
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    def _get_label_id(self, label_name: str) -> int:
        """
        Get label ID by name
        
        TODO: Implement label lookup/creation
        For now, returns dummy ID
        """
        # TODO: Cache label IDs
        return 0
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Global service instance
gitea_service = GiteaService()
