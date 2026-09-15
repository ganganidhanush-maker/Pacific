# Skill: Interactive Python Code Tutor & Sandbox

## Description
Interactive programming companion for computer science students. Delivers coding challenges, executes code in a safe local sandbox, and provides instant line-by-line feedback.

## Target Persona
- **Role**: Computer Science / STEM Student
- **Activities**: Lab assignments, algorithm practice, bug diagnosis

## Workflow Steps
1. **Assignment Generation**:
   - Desktop Agent generates structured assignments with built-in assertion tests (e.g. `python_assignment.py`) on the user's Desktop.
2. **Local Sandbox Execution (Open Interpreter Blueprint)**:
   - When student requests verification, Desktop Agent runs `execute_code(code)` in isolated subprocess.
3. **Execution Diagnostics**:
   - If tests pass: Main Agent congratulates student and increments difficulty level.
   - If runtime/syntax error: Kimi K3 / Local LLM explains the exact traceback and hints at the fix without spoiling the answer.
4. **Main Agent Spoken Feedback**:
   - Avatar explains the execution result in spoken natural language.
