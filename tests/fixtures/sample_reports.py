"""
Test fixtures and sample data
Includes Set B from sample data
"""

# Set B sample reports for testing
SAMPLE_REPORTS = {
    "B1_clean": {
        "text": """When I upload a profile picture larger than about 5MB, 
        the page shows a spinner forever and the picture never saves. 
        Tried it with a 8MB PNG and a 12MB JPEG, same result. 
        Chrome on Windows. Smaller images work fine.""",
        "expected": {
            "severity": "medium",
            "components": ["frontend", "backend"],
            "has_repro": True
        }
    },
    
    "B2_api_error": {
        "text": """The `/api/v2/orders` endpoint returns a 500 whenever 
        the `status` query param is omitted. Passing `status=open` works. 
        This started today. Reproduced with curl three times.""",
        "expected": {
            "severity": "high",
            "components": ["api", "backend"],
            "has_repro": True
        }
    },
    
    "B3_vague": {
        "text": "the reports thing is broken again pls fix",
        "expected": {
            "confidence_lt": 0.7,
            "needs_human_review": True
        }
    },
    
    "B4_cosmetic_urgent": {
        "text": """CRITICAL!!! URGENT!!! The footer copyright year 
        still says 2024 instead of 2025. This is extremely 
        important and needs to be fixed immediately!!!""",
        "expected": {
            "severity": "low",  # Override URGENT tone
            "components": ["frontend"]
        }
    },
    
    "B5_duplicate": {
        "text": """I can't log in on my iPhone. I open the app in Safari, 
        type my details, tap the login button and literally nothing happens. 
        My colleague has the same problem on her phone.""",
        "expected": {
            "is_duplicate": True,
            "duplicate_of": "EXIST-1"
        }
    },
    
    "B6_feature": {
        "text": """It would be really nice if we could export reports to PDF 
        as well as CSV. A lot of our customers ask for this.""",
        "expected": {
            "is_feature_request": True
        }
    },
    
    "B7_multiple": {
        "text": """A few things: the search bar sometimes returns no results 
        even for exact matches, the date picker lets you select an end date 
        before the start date, and also the mobile menu overlaps the header 
        on small screens.""",
        "expected": {
            "multiple_issues_detected": True,
            "components": ["frontend"]
        }
    },
    
    "B8_noisy": {
        "text": """hey so this happened again, see below, no idea whats going on
        ```
        [2025-06-01 09:14:22] INFO  request received
        [2025-06-01 09:14:22] DEBUG cache miss key=user:8831
        [2025-06-01 09:14:23] ERROR NullReferenceException in OrderService.Calculate() line 214
        [2025-06-01 09:14:23] INFO  returning 500
        ```
        basically checkout dies sometimes""",
        "expected": {
            "has_stacktrace": True,
            "severity": "high",
            "components": ["backend"]
        }
    }
}
