"""
Tools for the LangGraph agent with approval system and skills support
"""

import os
from pathlib import Path
from langchain_core.tools import tool
from skills import SkillsManager


SKILL_PATH = "./skills"


@tool
def write_file(file_path: str, content: str) -> str:
    """
    Write content to a file. Creates the file if it doesn't exist, overwrites if it does.
    REQUIRES USER APPROVAL before execution.

    Args:
        file_path: The path to the file to write (relative or absolute)
        content: The content to write to the file

    Returns:
        A message indicating success or failure
    """
    try:
        # Convert to Path object
        path = Path(file_path)

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        path.write_text(content)

        return f"Successfully wrote {len(content)} characters to {file_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool
def read_file(file_path: str) -> str:
    """
    Read the contents of a file.

    Args:
        file_path: The path to the file to read (relative or absolute)

    Returns:
        The contents of the file or an error message
    """
    try:
        path = Path(file_path)

        if not path.exists():
            return f"Error: File {file_path} does not exist"

        if not path.is_file():
            return f"Error: {file_path} is not a file"

        content = path.read_text()
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def list_files(directory: str = ".") -> str:
    """
    List files in a directory.

    Args:
        directory: The directory to list (defaults to current directory)

    Returns:
        A formatted list of files and directories
    """
    try:
        path = Path(directory)

        if not path.exists():
            return f"Error: Directory {directory} does not exist"

        if not path.is_dir():
            return f"Error: {directory} is not a directory"

        items = []
        for item in sorted(path.iterdir()):
            if item.is_dir():
                items.append(f"📁 {item.name}/")
            else:
                size = item.stat().st_size
                items.append(f"📄 {item.name} ({size} bytes)")

        if not items:
            return f"Directory {directory} is empty"

        return f"Contents of {directory}:\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool
def list_skills() -> str:
    """
    List all available skill files in the current directory.
    Skill files provide instructions and context to the agent.

    Returns:
        A list of available skill files
    """
    try:
        manager = SkillsManager(SKILL_PATH)
        skills = manager.discover_skills()

        if not skills:
            return "No skill files found. You can create skill files like CLAUDE.md, AGENT.md, or *.skill.md"

        return "Available skill files:\n" + "\n".join(f"  - {skill}" for skill in skills)
    except Exception as e:
        return f"Error listing skills: {str(e)}"


@tool
def load_skill(skill_name: str) -> str:
    """
    Load and display the contents of a specific skill file.

    Args:
        skill_name: Name of the skill file to load (e.g., "CLAUDE.md")

    Returns:
        The contents of the skill file
    """
    try:
        manager = SkillsManager(SKILL_PATH)
        content = manager.load_skill(skill_name)
        return content
    except Exception as e:
        return f"Error loading skill: {str(e)}"


@tool
def patch_file(file_path: str, search_string: str, replace_string: str, replace_all: bool = False) -> str:
    """
    Apply a search-and-replace patch to a file. Finds exact matches of search_string
    and replaces them with replace_string. Useful for making targeted edits without
    rewriting entire files. REQUIRES USER APPROVAL before execution.

    Args:
        file_path: The path to the file to patch (relative or absolute)
        search_string: The exact text to search for in the file
        replace_string: The text to replace the search_string with
        replace_all: If True, replace all occurrences. If False (default), replace only the first.

    Returns:
        A message indicating success or failure, with details about the change
    """
    try:
        path = Path(file_path)

        if not path.exists():
            return f"Error: File {file_path} does not exist"

        if not path.is_file():
            return f"Error: {file_path} is not a file"

        content = path.read_text()

        if search_string not in content:
            return (
                f"Error: Could not find the specified text in {file_path}. "
                f"The search string was not found in the file content."
            )

        count = content.count(search_string)

        if count > 1 and not replace_all:
            return (
                f"Error: Found {count} occurrences of the search string in {file_path}. "
                f"Set replace_all=True to replace all, or provide more context in the search string "
                f"to uniquely identify the target location."
            )

        if replace_all:
            new_content = content.replace(search_string, replace_string)
        else:
            new_content = content.replace(search_string, replace_string, 1)

        path.write_text(new_content)

        return (
            f"Successfully patched {file_path}: "
            f"replaced {count if replace_all else 1} occurrence(s) "
            f"({len(search_string)} chars -> {len(replace_string)} chars)"
        )
    except Exception as e:
        return f"Error patching file: {str(e)}"


# Tools that require approval
APPROVAL_REQUIRED_TOOLS = ["write_file", "patch_file"]

# Export all tools
all_tools = [write_file, read_file, list_files, list_skills, load_skill, patch_file]
