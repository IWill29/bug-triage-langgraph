"""
Gitea API client
Handles issue creation and management
"""

from __future__ import annotations

import httpx

from src.config import settings
from src.utils.logging import logger


class GiteaService:
    """
    Gitea API client for issue management
    """

    def __init__(self) -> None:
        """Initialize HTTP client with authentication"""
        self.base_url = settings.gitea_url
        self.token = settings.gitea_token
        self.repo_owner = settings.gitea_repo_owner
        self.repo_name = settings.gitea_repo_name
        self._label_id_cache: dict[str, int] = {}

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"token {self.token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"token {self.token}",
            "Content-Type": "application/json",
        }

    def _get_label_id(self, label_name: str) -> int:
        """Resolve label name to Gitea label ID, creating the label if missing."""
        cache_key = label_name.lower()
        if cache_key in self._label_id_cache:
            return self._label_id_cache[cache_key]

        labels_url = f"/api/v1/repos/{self.repo_owner}/{self.repo_name}/labels"

        with httpx.Client(
            base_url=self.base_url,
            headers=self._auth_headers(),
            timeout=45.0,
        ) as client:
            response = client.get(labels_url)
            response.raise_for_status()
            for label in response.json():
                name = str(label.get("name", ""))
                if name.lower() == cache_key:
                    label_id = int(label["id"])
                    self._label_id_cache[cache_key] = label_id
                    return label_id

            create_response = client.post(
                labels_url,
                json={"name": label_name, "color": "#cccccc"},
            )
            create_response.raise_for_status()
            label_id = int(create_response.json()["id"])
            self._label_id_cache[cache_key] = label_id
            logger.info("gitea_label_created", label=label_name, label_id=label_id)
            return label_id
    
    async def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict:
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
        body: str,
    ) -> dict:
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
        limit: int = 100,
    ) -> list[dict]:
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
    
    def create_issue_sync(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict:
        """Synchronous issue creation for LangGraph sync nodes."""
        logger.info(
            "gitea_create_issue_sync",
            title=title,
            labels=labels or [],
        )

        url = f"/api/v1/repos/{self.repo_owner}/{self.repo_name}/issues"
        payload = {
            "title": title,
            "body": body,
            "labels": [self._get_label_id(label) for label in (labels or [])],
        }

        with httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"token {self.token}",
                "Content-Type": "application/json",
            },
            timeout=45.0,
        ) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    def add_comment_sync(self, issue_id: int, body: str) -> dict:
        """Synchronous comment creation for LangGraph sync nodes."""
        logger.info("gitea_add_comment_sync", issue_id=issue_id)

        url = (
            f"/api/v1/repos/{self.repo_owner}/{self.repo_name}"
            f"/issues/{issue_id}/comments"
        )

        with httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"token {self.token}",
                "Content-Type": "application/json",
            },
            timeout=45.0,
        ) as client:
            response = client.post(url, json={"body": body})
            response.raise_for_status()
            return response.json()

    def list_issues_sync(
        self,
        state: str = "open",
        limit: int = 100,
    ) -> list[dict]:
        """Synchronous issue listing for duplicate detection."""
        url = f"/api/v1/repos/{self.repo_owner}/{self.repo_name}/issues"
        params = {"state": state, "limit": limit}

        with httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"token {self.token}",
                "Content-Type": "application/json",
            },
            timeout=45.0,
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def close(self) -> None:
        """Close HTTP client"""
        await self.client.aclose()


# Global service instance
gitea_service = GiteaService()
