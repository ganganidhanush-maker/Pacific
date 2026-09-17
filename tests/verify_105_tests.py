import os
import sys
import asyncio
import time
from pathlib import Path

root_dir = Path('.').resolve()
sys.path.insert(0, str(root_dir / 'octopus_ai'))
sys.path.insert(0, str(root_dir))

from octopus_ai.agent.orchestrator import MasterOrchestrator

TEST_SCENARIOS = [
    (1, 'Open WhatsApp Web and write a note to myself', 'web'),
    (2, 'Open WhatsApp and send a message to Rahul saying I will call after 6 PM', 'web'),
    (3, 'Open WhatsApp Web and check for unread messages', 'web'),
    (4, 'Send a WhatsApp broadcast to CSE Section A group about tomorrow exam schedule', 'web'),
    (5, 'Search for contact Priya on WhatsApp and send the meeting link', 'web'),
    (6, 'Open WhatsApp Web and send an image from my desktop to Dad', 'web'),
    (7, 'Check WhatsApp for any urgent messages containing assignment', 'web'),
    (8, 'Open WhatsApp and send a voice note greeting to the study group', 'web'),
    (9, 'Enable auto-responder on WhatsApp Web with Telugu slang persona', 'web'),
    (10, 'Open WhatsApp and send lecture notes PDF to the class group', 'web'),
    (11, 'Filter and mark off-topic WhatsApp chats as unread', 'web'),
    (12, 'Open WhatsApp and pin the college announcements group', 'web'),
    (13, 'Check WhatsApp chat history with Ankit from yesterday', 'web'),
    (14, 'Open WhatsApp and send a location reminder for seminar hall', 'web'),
    (15, 'Send a congratulatory message on WhatsApp to Sai with emojis', 'web'),
    (16, 'Mute WhatsApp notifications for sports club group for 8 hours', 'web'),
    (17, 'Open WhatsApp Web and verify active session login status', 'web'),
    (18, 'Send a WhatsApp reminder to project team to submit PRs', 'web'),
    (19, 'Login into Canva app and open the dashboard', 'web'),
    (20, 'Open Canva and create a new presentation on Machine Learning Basics', 'web'),
    (21, 'Search for computer science project presentation templates in Canva', 'web'),
    (22, 'Open Canva and design an Instagram story banner for the tech fest', 'web'),
    (23, 'Create an educational infographic about the solar system in Canva', 'web'),
    (24, 'Open Canva and add a title slide with heading Introduction to Deep Learning', 'web'),
    (25, 'Insert a flowchart diagram into my active Canva presentation', 'web'),
    (26, 'Create a resume template in Canva for a software engineer internship', 'web'),
    (27, 'Open Canva and export the presentation slides as a PDF file', 'web'),
    (28, 'Duplicate slide number 3 in my Canva presentation deck', 'web'),
    (29, 'Change background color of Canva canvas to dark navy blue', 'web'),
    (30, 'Create a YouTube thumbnail in Canva about Python tutorial for beginners', 'web'),
    (31, 'Search Canva for academic certificate templates and edit student name', 'web'),
    (32, 'Open Canva and resize banner design for Twitter header dimensions', 'web'),
    (33, 'Create a workshop flyer in Canva with dates, venue, and QR code', 'web'),
    (34, 'Open Instagram and check my notifications', 'web'),
    (35, 'Search for college robotics club profile on Instagram', 'web'),
    (36, 'Open Instagram DMs and check if there are any new messages', 'web'),
    (37, 'Go to Instagram explore tab and search for python programming tips', 'web'),
    (38, 'View the latest post on the official university Instagram page', 'web'),
    (39, 'Open Instagram and view my saved posts collection', 'web'),
    (40, 'Check Instagram direct messages from student council', 'web'),
    (41, 'Open Instagram and like the recent photo posted by AI research lab', 'web'),
    (42, 'Search Instagram for tech conference hashtags and view top reels', 'web'),
    (43, 'Open Instagram profile settings and check follower count', 'web'),
    (44, 'Navigate to Instagram reels section and scroll through the feed', 'web'),
    (45, 'Open Instagram and reply to the latest message from classmate Karthik', 'web'),
    (46, 'Google search the latest research papers on transformer architectures', 'web'),
    (47, 'Open Wikipedia page on Quantum Computing and read summary', 'web'),
    (48, 'Search Google Scholar for recent publications by Geoffrey Hinton', 'web'),
    (49, 'Navigate to GitHub trending repositories for Python today', 'web'),
    (50, 'Open university portal and check academic calendar', 'web'),
    (51, 'Search for top interview questions on binary trees and summarize', 'web'),
    (52, 'Navigate to ArXiv.org and search for multimodal agent papers', 'web'),
    (53, 'Open browser, go to Python documentation and look up asyncio', 'web'),
    (54, 'Perform a web search for upcoming hackathons in Hyderabad 2026', 'web'),
    (55, 'Take a full page screenshot of the current web page', 'web'),
    (56, 'Search for official documentation on FastAPI dependency injection', 'web'),
    (57, 'Navigate to StackOverflow and search for resolving CUDA memory errors', 'web'),
    (58, 'Find all PDF files on my Desktop matching lecture notes', 'desktop'),
    (59, 'Search for all Python script files in my Documents folder', 'desktop'),
    (60, 'Create a new folder called Final_Year_Project on my Desktop', 'desktop'),
    (61, 'Move all screenshot PNG files from Downloads to Pictures folder', 'desktop'),
    (62, 'Find local files modified in the last 24 hours', 'desktop'),
    (63, 'Create a blank test script named verify_pipeline.py on Desktop', 'desktop'),
    (64, 'Open notes.txt on my Desktop with default text editor', 'desktop'),
    (65, 'Count how many PDF files are in my Downloads folder', 'desktop'),
    (66, 'Organize my Downloads folder by grouping files into categories', 'desktop'),
    (67, 'Search for the file syllabus_2026.docx across my home directory', 'desktop'),
    (68, 'Read the first 50 lines of dataset_summary.csv on my Desktop', 'desktop'),
    (69, 'Check available free disk space on drive C', 'desktop'),
    (70, 'Find all Jupyter notebook ipynb files on my computer', 'desktop'),
    (71, 'Archive old lab reports folder into a zip file on Desktop', 'desktop'),
    (72, 'Launch Windows Calculator application for a quick calculation', 'desktop'),
    (73, 'Research architecture of CNNs and generate 5 slides', 'research'),
    (74, 'Synthesize a 1-page summary of the Turing Test and LLM benchmarks', 'research'),
    (75, 'Generate slide outline on Renewable Energy Sources for 15 min lecture', 'research'),
    (76, 'Create academic lesson plan for teaching Sorting Algorithms', 'research'),
    (77, 'Summarize key differences between TCP and UDP protocols', 'research'),
    (78, 'Outline slide deck on Cybersecurity Fundamentals', 'research'),
    (79, 'Synthesize research on Reinforcement Learning from Human Feedback', 'research'),
    (80, 'Generate comprehensive study guide for Data Structures exam', 'research'),
    (81, 'Create comparison table between SQL and NoSQL databases', 'research'),
    (82, 'Research history of Operating Systems and outline 4 slides', 'research'),
    (83, 'Generate 10 multiple-choice quiz questions on OOP in Python', 'research'),
    (84, 'Outline a 6-slide presentation on Blockchain and Smart Contracts', 'research'),
    (85, 'Summarize Ethical Implications of Autonomous AI Agents', 'research'),
    (86, 'Explain how Python decorators work using a simple analogy', 'chat'),
    (87, 'Walk me step-by-step through solving a calculus derivative', 'chat'),
    (88, 'Debug this Python snippet and explain why it throws IndexError', 'chat'),
    (89, 'Explain working principle of Transformer self-attention in simple terms', 'chat'),
    (90, 'Give me a 5-question practice quiz on Database Normalization', 'chat'),
    (91, 'Explain recursion using Fibonacci sequence as an example', 'chat'),
    (92, 'Review my draft essay paragraph on Climate Change', 'chat'),
    (93, 'Explain Big-O notation and why merge sort is O(N log N)', 'chat'),
    (94, 'Conduct a mock technical interview for junior Python developer', 'chat'),
    (95, 'Explain difference between processes and threads in OS', 'chat'),
    (96, 'Activate avatar speaking state and introduce yourself', 'avatar'),
    (97, 'Synthesize spoken response using neural voice', 'avatar'),
    (98, 'Switch active agent persona from Main Agent to Web Agent', 'avatar'),
    (99, 'Stop avatar speech mid-sentence and return to idle state', 'avatar'),
    (100, 'Adjust speech synthesis rate and switch voice language accent', 'avatar'),
    (101, 'Research Neural Networks, create Canva presentation, and send to WhatsApp', 'multi'),
    (102, 'Find lab report PDF on Desktop and upload to Canva as reference', 'multi'),
    (103, 'Search Google for weather and send WhatsApp update to family', 'multi'),
    (104, 'Research AI trends, create bullet points, and save file to Desktop', 'multi'),
    (105, 'Decompose user query, trigger research agent, and narrate summary', 'multi')
]

async def run():
    orch = MasterOrchestrator()
    passed = 0
    t0 = time.time()
    for idx, prompt, cat in TEST_SCENARIOS:
        try:
            plan = await orch.optimize_and_decompose(prompt)
            passed += 1
        except Exception as e:
            print(f'Test #{idx} failed: {e}')
    elapsed = time.time() - t0
    print(f'TOTAL: {passed}/{len(TEST_SCENARIOS)} PASSED in {elapsed:.2f}s')

asyncio.run(run())
