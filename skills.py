"""
Skills management for the LangGraph agent
Skills are markdown files that provide context and instructions to the agent
"""

import os
from pathlib import Path
from typing import Dict, List


class SkillsManager:
    """Manage skill files for the agent"""

    def __init__(self, skills_dir: str = "."):
        """
        Initialize skills manager

        Args:
            skills_dir: Directory to search for skill files (default: current directory)
        """
        self.skills_dir = Path(skills_dir)
        self.skills_cache: Dict[str, str] = {}
        self.skill_keywords: Dict[str, List[str]] = {}  # Map skill files to keywords

    def discover_skills(self) -> List[str]:
        """
        Discover all skill files in the skills directory
        Looks for *.md files with common skill patterns

        Returns:
            List of skill file names
        """
        if not self.skills_dir.exists():
            return []

        skills = []
        common_skill_names = [
            "CLAUDE.md",
            "AGENT.md",
            "INSTRUCTIONS.md",
            "SKILLS.md",
            "SYSTEM.md",
            "RULES.md"
        ]

        # Check for common skill files
        for skill_name in common_skill_names:
            skill_path = self.skills_dir / skill_name
            if skill_path.exists() and skill_path.is_file():
                skills.append(skill_name)

        # Also look for any .skill.md files
        for file_path in self.skills_dir.glob("*.skill.md"):
            if file_path.is_file():
                skills.append(file_path.name)

        return skills

    def load_skill(self, skill_name: str) -> str:
        """
        Load a skill file

        Args:
            skill_name: Name of the skill file

        Returns:
            Content of the skill file or error message
        """
        # Check cache first
        if skill_name in self.skills_cache:
            return self.skills_cache[skill_name]

        skill_path = self.skills_dir / skill_name

        if not skill_path.exists():
            return f"Skill file '{skill_name}' not found"

        if not skill_path.is_file():
            return f"'{skill_name}' is not a file"

        try:
            content = skill_path.read_text()
            # Cache the content
            self.skills_cache[skill_name] = content
            return content
        except Exception as e:
            return f"Error reading skill file: {str(e)}"

    def load_all_skills(self) -> str:
        """
        Load all discovered skill files and combine them

        Returns:
            Combined content of all skill files
        """
        skills = self.discover_skills()

        if not skills:
            return ""

        combined = []
        for skill_name in skills:
            content = self.load_skill(skill_name)
            if not content.startswith("Error") and not content.startswith("Skill file"):
                combined.append(f"# Skill: {skill_name}\n\n{content}\n")

        return "\n---\n\n".join(combined)

    def get_system_prompt_with_skills(self, base_prompt: str) -> str:
        """
        Combine base system prompt with loaded skills

        Args:
            base_prompt: Base system prompt

        Returns:
            Combined prompt with skills
        """
        skills_content = self.load_all_skills()

        if not skills_content:
            return base_prompt

        return f"""{base_prompt}

# Loaded Skills and Instructions

The following skill files have been loaded to guide your behavior:

{skills_content}

Please follow the guidelines and instructions in the skill files above when assisting the user."""

    def reload_skills(self):
        """Clear cache and reload all skills"""
        self.skills_cache.clear()
