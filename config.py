"""
Centralized configuration for the Oasis backend.

All environment variables are read exactly once, here, at import time.
Nothing else in the codebase should call os.getenv() directly -- this
keeps secret handling auditable in one place and makes it possible to
assert required configuration is present at startup instead of failing
deep inside a request handler.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv(override=True)


def _split_origins(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@dataclass
class Settings:
                                                                           
                                                                          
                                      
                 
    environment: str = os.getenv("OASIS_ENV", "development")

                                                                            
                                                                         
                                  
    github_webhook_secret: str | None = os.getenv("GITHUB_WEBHOOK_SECRET")
    github_token: str | None = os.getenv("GITHUB_TOKEN")

                                                                                    
    github_app_id: str | None = os.getenv("GITHUB_APP_ID")
                                                                          
                                                                     
                                        
                                                                                                            
    github_app_private_key: str | None = os.getenv("GITHUB_APP_PRIVATE_KEY")
                                                                                     
    github_app_slug: str | None = os.getenv("GITHUB_APP_SLUG")

                                                                        
                                                                         
    oasis_state_secret: str | None = os.getenv("OASIS_STATE_SECRET")

                                                                          
                                         
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5000")

              
    supabase_url: str | None = os.getenv("SUPABASE_URL")
    supabase_key: str | None = os.getenv("SUPABASE_KEY")

                           
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

                                                                          
                                                                          
                                                              
    cors_origins: list[str] = field(
        default_factory=lambda: _split_origins(os.getenv("OASIS_CORS_ORIGINS"))
        or [
            "http://localhost:3000",
            "http://localhost:5000",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5000",
            "http://127.0.0.1:8080",
        ]
    )

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def missing_required(self) -> list[str]:
        """Returns names of required-for-full-functionality vars that are unset.

        The app is still allowed to boot without these (so /health and /docs
        work even in a half-configured dev box), but routes that depend on
        them will return a clear 503 rather than crashing with an opaque
        AttributeError.
        """
        missing = []
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_key:
            missing.append("SUPABASE_KEY")
        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        if not self.github_webhook_secret:
            missing.append("GITHUB_WEBHOOK_SECRET")
        if not self.github_app_id:
            missing.append("GITHUB_APP_ID")
        if not self.github_app_private_key:
            missing.append("GITHUB_APP_PRIVATE_KEY")
        if not self.github_app_slug:
            missing.append("GITHUB_APP_SLUG")
        if not self.oasis_state_secret:
            missing.append("OASIS_STATE_SECRET")
        return missing

    @property
    def github_app_configured(self) -> bool:
        return bool(self.github_app_id and self.github_app_private_key)


settings = Settings()
