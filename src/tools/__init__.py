# -*- coding: utf-8 -*-
"""
IRIS - Tools Module
Ferramentas disponíveis para a IRIS executar
"""

from .web import fn_web_search, fn_web_news, fn_reddit
from .email_tool import fn_read_emails
from .github import (
    fn_github_list_repos, fn_github_repo_info,
    fn_github_list_issues, fn_github_create_issue,
    fn_github_get_file, fn_github_create_or_update_file,
    fn_github_list_commits, fn_github_list_prs, fn_github_activity
)
from .image import fn_generate_image
from .code import (
    fn_create_file, fn_read_file, fn_list_workspace,
    fn_run_python, fn_run_bash
)
from .files import fn_list_received_files, fn_read_received_file, fn_get_file_path
from .productivity import (
    fn_add_task, fn_list_tasks, fn_complete_task,
    fn_add_goal, fn_list_goals,
    fn_add_journal, fn_view_journal,
    fn_log_exercise, fn_log_mood,
    fn_dashboard, fn_briefing, fn_weekly_review
)

__all__ = [
    # Web
    'fn_web_search',
    'fn_web_news', 
    'fn_reddit',
    # Email
    'fn_read_emails',
    # GitHub
    'fn_github_list_repos',
    'fn_github_repo_info',
    'fn_github_list_issues',
    'fn_github_create_issue',
    'fn_github_get_file',
    'fn_github_create_or_update_file',
    'fn_github_list_commits',
    'fn_github_list_prs',
    'fn_github_activity',
    # Image
    'fn_generate_image',
    # Code
    'fn_create_file',
    'fn_read_file',
    'fn_list_workspace',
    'fn_run_python',
    'fn_run_bash',
    # Files
    'fn_list_received_files',
    'fn_read_received_file',
    'fn_get_file_path',
    # Productivity
    'fn_add_task',
    'fn_list_tasks',
    'fn_complete_task',
    'fn_add_goal',
    'fn_list_goals',
    'fn_add_journal',
    'fn_view_journal',
    'fn_log_exercise',
    'fn_log_mood',
    'fn_dashboard',
    'fn_briefing',
    'fn_weekly_review',
]
