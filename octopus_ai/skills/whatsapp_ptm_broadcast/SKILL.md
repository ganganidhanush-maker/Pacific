# Skill: WhatsApp PTM Broadcast & Intelligent Auto-Responder

## Description
Automates Parent-Teacher Meeting (PTM) and academic announcements across WhatsApp groups for teachers and administrators, acting strictly in the teacher's persona and contextually handling responses.

## Target Persona
- **Role**: Teacher / Professor (e.g. Saiteja)
- **Recipients**: Parents Group, Students Group

## Workflow Steps
1. **Compose & Optimize Announcement**:
   - The Teacher gives raw instructions: "Tell parents about tomorrow's PTM at 10 AM, discuss term exams and attendance."
   - The Main Agent (Avatar) optimizes the prompt into a formal, polite academic announcement.
2. **Web Agent Dispatch**:
   - Web Agent connects to WhatsApp Web via Selenium session.
   - Searches for target groups: `"Parents Group"`, `"Students Group"`.
   - Sends the formatted broadcast message.
3. **Context-Confined Auto-Responder**:
   - Web Agent monitors incoming messages for 30 minutes.
   - **On-Topic Inquiries** (e.g. "Can I join online?", "What time is roll 24?"):
     - Responds politely in teacher persona (`Saiteja`).
   - **Unrelated Inquiries** (e.g. general chit-chat, other subjects):
     - Leaves chat marked as **unread** so the teacher can address it manually without notification spam.
4. **Main Agent Spoken Debrief**:
   - Avatar speaks aloud: "PTM announcement has been broadcast to Parents and Students groups. Active auto-responder is monitoring inquiries."
