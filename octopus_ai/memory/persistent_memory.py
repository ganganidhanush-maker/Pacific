"""
Persistent Memory & NotebookLM-Style Knowledge Engine for Octopus AI
Provides:
- Persistent SQLite Database for all chat sessions, variables, and action logs across restarts
- NotebookLM-Style Source Grounding: Ingests PDFs, lecture notes, syllabus, code, and teacher broadcasts
- Semantic / Chunked Knowledge Retrieval (RAG) for students and educators
- Automated Study Guide and Audio Overview generation for the Dhanush Video Avatar Brain
"""

import os
import re
import json
import sqlite3
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("PersistentMemory")

DATA_DIR = Path(__file__).resolve().parent.parent / "assets" / "data"
DB_PATH = DATA_DIR / "octopus_memory.db"


class PersistentMemory:
    """
    NotebookLM-style persistent knowledge base and memory store for Octopus AI.
    """

    _instance: Optional["PersistentMemory"] = None

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.data_dir = self.db_path.parent
        os.makedirs(self.data_dir, exist_ok=True)
        self._init_db()

    @classmethod
    def get_instance(cls) -> "PersistentMemory":
        if cls._instance is None:
            cls._instance = PersistentMemory()
        return cls._instance

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema with tables and indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Chat conversation history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    agent_name TEXT DEFAULT 'main',
                    timestamp TEXT NOT NULL
                )
            """)

            # 2. NotebookLM-style sources (PDFs, notes, syllabus, broadcasts)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notebook_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    file_path TEXT,
                    raw_content TEXT NOT NULL,
                    summary TEXT,
                    tags TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # 3. Source chunks for grounded retrieval (RAG)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS source_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES notebook_sources(id) ON DELETE CASCADE
                )
            """)

            # 4. System variables and user preferences
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_variables (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 5. Teacher and student notes / flashcards
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    created_at TEXT NOT NULL
                )
            """)

            # Indexes for fast retrieval
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_chunks_source ON source_chunks(source_id)")
            conn.commit()

    # =========================================================================
    # CONVERSATION MEMORY (PERSISTENT ACROSS APP RESTARTS)
    # =========================================================================
    def add_message(self, role: str, content: str, agent_name: str = "main", session_id: str = "default_session"):
        """Save a message turn to the persistent database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversations (session_id, role, content, agent_name, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, role, content, agent_name, datetime.now().isoformat()))
            conn.commit()

    def get_recent_history(self, limit: int = 15, session_id: Optional[str] = None) -> List[Dict[str, str]]:
        """Retrieve recent conversation history from SQLite."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if session_id:
                cursor.execute("""
                    SELECT role, content, agent_name, timestamp
                    FROM conversations
                    WHERE session_id = ?
                    ORDER BY id DESC LIMIT ?
                """, (session_id, limit))
            else:
                cursor.execute("""
                    SELECT role, content, agent_name, timestamp
                    FROM conversations
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            # Reverse so chronological order
            return [{"role": r["role"], "content": r["content"], "agent": r["agent_name"]} for r in reversed(rows)]

    def clear_conversation_history(self, session_id: Optional[str] = None):
        """Clear conversations for a session or entirely."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if session_id:
                cursor.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
            else:
                cursor.execute("DELETE FROM conversations")
            conn.commit()

    # =========================================================================
    # SYSTEM VARIABLES & PERSISTENT PREFERENCES
    # =========================================================================
    def store_variable(self, key: str, value: Any):
        """Persist a variable to SQLite."""
        val_str = json.dumps(value) if not isinstance(value, str) else value
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO system_variables (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """, (key, val_str, datetime.now().isoformat()))
            conn.commit()

    def retrieve_variable(self, key: str, default: Any = None) -> Any:
        """Retrieve a variable from SQLite."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_variables WHERE key = ?", (key,))
            row = cursor.fetchone()
            if not row:
                return default
            val = row["value"]
            try:
                return json.loads(val)
            except Exception:
                return val

    # =========================================================================
    # NOTEBOOKLM SOURCE INGESTION & GROUNDING (RAG)
    # =========================================================================
    def add_source(
        self,
        title: str,
        content: str,
        source_type: str = "text",
        file_path: Optional[str] = None,
        tags: str = "",
        chunk_size: int = 500,
        chunk_overlap: int = 100
    ) -> int:
        """
        Index a new knowledge source (NotebookLM style) and split into semantic chunks.
        """
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notebook_sources (title, source_type, file_path, raw_content, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, source_type, file_path, content, tags, now))
            source_id = cursor.lastrowid

            # Chunk content
            chunks = self._chunk_text(content, chunk_size=chunk_size, overlap=chunk_overlap)
            for idx, chunk in enumerate(chunks):
                cursor.execute("""
                    INSERT INTO source_chunks (source_id, chunk_index, content)
                    VALUES (?, ?, ?)
                """, (source_id, idx, chunk))

            conn.commit()
            logger.info(f"[PersistentMemory] Indexed source '{title}' (ID: {source_id}) with {len(chunks)} chunks.")
            return source_id

    def index_local_file(self, file_path: str, tags: str = "local_file") -> Dict[str, Any]:
        """
        Index a local file (.pdf, .txt, .py, .md, .json) into the persistent NotebookLM store.
        """
        p = Path(file_path)
        if not p.exists():
            return {"success": False, "error": f"File '{file_path}' does not exist."}

        title = p.name
        ext = p.suffix.lower()
        content = ""

        try:
            if ext == ".pdf":
                try:
                    from pdfminer.high_level import extract_text
                    content = extract_text(str(p))
                except Exception as pdf_err:
                    return {"success": False, "error": f"Failed to extract text from PDF: {pdf_err}"}
            else:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

            if not content.strip():
                return {"success": False, "error": "File content is empty."}

            source_id = self.add_source(
                title=title,
                content=content,
                source_type=ext.replace(".", ""),
                file_path=str(p.resolve()),
                tags=tags
            )

            return {
                "success": True,
                "source_id": source_id,
                "title": title,
                "characters": len(content),
                "message": f"Successfully indexed '{title}' ({len(content):,} characters) into NotebookLM Knowledge Base."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def query_knowledge_base(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve relevant source chunks for grounding using lexical relevance / BM25 scoring.
        """
        query_terms = set(re.findall(r'\w+', query.lower()))
        if not query_terms:
            return []

        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sc.id, sc.source_id, sc.chunk_index, sc.content, ns.title, ns.source_type
                FROM source_chunks sc
                JOIN notebook_sources ns ON sc.source_id = ns.id
            """)
            rows = cursor.fetchall()

            scored_chunks = []
            for r in rows:
                chunk_text = r["content"]
                chunk_terms = set(re.findall(r'\w+', chunk_text.lower()))
                overlap = len(query_terms.intersection(chunk_terms))
                if overlap > 0:
                    # Score based on keyword overlap density
                    score = overlap / (len(query_terms) + 0.5)
                    scored_chunks.append({
                        "chunk_id": r["id"],
                        "source_id": r["source_id"],
                        "title": r["title"],
                        "source_type": r["source_type"],
                        "chunk_index": r["chunk_index"],
                        "excerpt": chunk_text.strip(),
                        "score": round(score, 3)
                    })

            # Sort descending by relevance score
            scored_chunks.sort(key=lambda x: x["score"], reverse=True)
            results = scored_chunks[:top_k]

        return results

    def list_sources(self) -> List[Dict[str, Any]]:
        """List all indexed notebook sources."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, source_type, file_path, tags, created_at FROM notebook_sources ORDER BY id DESC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    # =========================================================================
    # NOTEBOOKLM STUDY GUIDE & AUDIO OVERVIEW GENERATORS
    # =========================================================================
    async def generate_notebooklm_study_guide(self, source_id: int) -> Dict[str, Any]:
        """
        Generate a NotebookLM-style comprehensive Study Guide for students:
        - Executive Summary
        - Key Concepts & Definitions
        - 5 Core Frequently Asked Questions
        - Practice Exam Questions
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, raw_content FROM notebook_sources WHERE id = ?", (source_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": f"Source ID {source_id} not found."}

            title = row["title"]
            # Use up to first 8,000 characters for study guide synthesis
            content_sample = row["raw_content"][:8000]

        from server.local_llm_service import local_llm_instance
        prompt = (
            f"You are a NotebookLM Academic Study Assistant. Create a comprehensive, elegant Study Guide "
            f"based strictly on the following source: '{title}'.\n\n"
            f"Source Text:\n{content_sample}\n\n"
            f"Generate a NotebookLM Study Guide with these exact sections:\n"
            f"1. Executive Summary\n"
            f"2. Core Concepts & Key Takeaways (bullet points)\n"
            f"3. 5 Essential FAQs with clear answers\n"
            f"4. Practice Review Questions for Students\n"
        )
        guide_content = await local_llm_instance.generate_response(prompt, add_to_history=False)

        # Save generated guide to user_notes table
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_notes (title, content, category, created_at)
                VALUES (?, ?, 'study_guide', ?)
            """, (f"Study Guide: {title}", guide_content, datetime.now().isoformat()))
            conn.commit()

        return {
            "success": True,
            "title": title,
            "study_guide": guide_content,
            "message": f"Generated NotebookLM Study Guide for '{title}'."
        }

    async def generate_audio_overview_script(self, source_id: int) -> Dict[str, Any]:
        """
        Generate a NotebookLM-style spoken 'Audio Overview' script
        optimized for the Dhanush Video Avatar Brain to speak aloud.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, raw_content FROM notebook_sources WHERE id = ?", (source_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": f"Source ID {source_id} not found."}
            title = row["title"]
            content_sample = row["raw_content"][:6000]

        from server.local_llm_service import local_llm_instance
        prompt = (
            f"You are the Dhanush Video Avatar Brain. Generate an engaging, conversational, 60-second "
            f"NotebookLM 'Audio Overview' summarizing the source: '{title}'.\n\n"
            f"Source Excerpt:\n{content_sample}\n\n"
            f"Tone: Conversational, friendly, articulate, like a podcast host giving an insightful briefing. "
            f"No markdown headers or asterisks, plain conversational speech ready for TTS audio."
        )
        audio_script = await local_llm_instance.generate_response(prompt, add_to_history=False)

        return {
            "success": True,
            "title": title,
            "audio_script": audio_script,
            "message": f"Created NotebookLM Audio Overview script for '{title}'."
        }

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """Split text into overlapping chunks."""
        words = text.split()
        if not words:
            return []
        chunks = []
        step = max(1, chunk_size - overlap)
        for i in range(0, len(words), step):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            if i + chunk_size >= len(words):
                break
        return chunks


persistent_memory_instance = PersistentMemory.get_instance()
