# Skill: Academic Study Deck & Lecture Synthesis

## Description
Extracts core concepts, exam questions, and revision summaries from textbooks, lecture notes, or syllabi for students, generating concise study decks.

## Target Persona
- **Role**: Student / Self-learner
- **Inputs**: PDF slides, lecture notes, research topics

## Workflow Steps
1. **Document Discovery**:
   - Desktop Agent locates textbook/notes via `find_local_files(extensions=['.pdf', '.txt', '.docx'])`.
2. **256K Context Reading (Kimi K3 / Kiwi Engine)**:
   - Uses Kimi K3's massive 256k-1M context window to ingest full chapters or multi-week lecture transcripts in a single pass.
3. **Synthesis & Deck Generation**:
   - Research Agent structures content into:
     - 5 Core Takeaways
     - 10 Flashcard Q&As
     - Common Exam Pitfalls
4. **Local Delivery**:
   - Desktop Agent writes `revision_deck.md` to user's `Desktop` and opens it in Notepad/Notion.
5. **Main Agent Spoken Summary**:
   - Avatar speaks aloud: "I've synthesized your lecture materials into a study deck and placed it on your Desktop."
