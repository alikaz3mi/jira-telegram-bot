"""Check all boards and their types in Jira."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


def check_all_boards():
    """List all boards and their types."""
    LOGGER.info("Checking all boards in Jira")
    
    container = get_container()
    task_manager_repo = container[TaskManagerRepositoryInterface]
    
    # Get all boards
    boards = task_manager_repo.jira.boards()
    
    print("\n" + "="*80)
    print("JIRA BOARDS")
    print("="*80)
    
    scrum_boards = []
    kanban_boards = []
    
    for board in boards:
        board_info = {
            'id': board.id,
            'name': board.name,
            'type': board.type
        }
        
        if board.type.lower() == 'scrum':
            scrum_boards.append(board_info)
        else:
            kanban_boards.append(board_info)
        
        print(f"\nBoard ID: {board.id}")
        print(f"Name: {board.name}")
        print(f"Type: {board.type}")
    
    print("\n" + "="*80)
    print(f"SUMMARY: {len(scrum_boards)} Scrum boards, {len(kanban_boards)} Kanban boards")
    print("="*80)
    
    if scrum_boards:
        print("\n📊 SCRUM BOARDS (have sprints):")
        for board in scrum_boards:
            print(f"  - {board['name']} (ID: {board['id']})")
    
    if kanban_boards:
        print("\n📋 KANBAN BOARDS (no sprints):")
        for board in kanban_boards:
            print(f"  - {board['name']} (ID: {board['id']})")


if __name__ == "__main__":
    try:
        check_all_boards()
    except Exception as e:
        LOGGER.error(f"Error checking boards: {e}", exc_info=True)
        sys.exit(1)
