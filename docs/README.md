# ClinExtract v1.0.0 — Documentation Index

Welcome to the comprehensive documentation suite for **ClinExtract v1.0.0**, an AI-Assisted Clinical Document Extraction and Human-in-the-Loop Validation Platform.

## 📖 Handbooks & Guides
- [Technical Documentation](ClinExtract_Technical_Documentation.md): 50-80 page deep-dive into the entire architecture, from React to FastAPI, Celery, and Gemini.
- [Architecture Decisions (ADRs)](ClinExtract_Architecture_Decisions.md): Detailed records of every major architectural choice (e.g., PostgreSQL, RabbitMQ, Gemini vs Rules).
- [File Explanation Guide](ClinExtract_File_Explanation_Guide.md): An "Explain Any File" guide for the core codebase, designed for quick orientation.
- [Troubleshooting Handbook](ClinExtract_Troubleshooting_Handbook.md): 22 real-world failure scenarios with exact commands and fixes.
- [Interview Handbook](ClinExtract_Interview_Handbook.md): Questions and detailed answers grouped by backend, AI, database, security, and more.

## 💾 System Reference
- [API Reference](ClinExtract_API_Reference.md): Exhaustive documentation of all REST API endpoints.
- [Database Deep Dive](ClinExtract_Database_Deep_Dive.md): Complete schema reference, relationship logic, and ER diagrams.
- [Development Chronicle](ClinExtract_Development_Chronicle.md): Phase-by-phase history of how the v1.0.0 system was built.

## 📊 Architecture Diagrams
All Mermaid (`.mmd`) diagrams are located in the `diagrams/` folder.
- [01 System Architecture](diagrams/01_system_architecture.mmd)
- [02 Document Processing Pipeline](diagrams/02_document_processing_pipeline.mmd)
- [03 Database ERD](diagrams/03_database_erd.mmd)
- [04 Authentication Flow](diagrams/04_authentication_flow.mmd)
- [05 Upload Flow](diagrams/05_upload_flow.mmd)
- [06 Celery Processing Flow](diagrams/06_celery_processing_flow.mmd)
- [07 Extraction Pipeline](diagrams/07_extraction_pipeline.mmd)
- [08 Validation Flow](diagrams/08_validation_flow.mmd)
- [09 Human Review Flow](diagrams/09_human_review_flow.mmd)
- [10 Gemini Provider Flow](diagrams/10_gemini_provider_flow.mmd)

## 🎤 Presentation & Project Story
- [Project Presentation (Markdown)](ClinExtract_Project_Presentation.md)
- **Project Presentation (PPTX)**: `ClinExtract_Project_Presentation.pptx` (Generated via python-pptx)
- [Project Story](ClinExtract_Project_Story.md): 1st-person narrative of the project journey.
- [Demo Script](ClinExtract_Demo_Script.md): 10-minute end-to-end demonstration guide.
- [Resume Bullets](ClinExtract_Resume_Bullets.md): Scaled bullet points for resumes, LinkedIn, and ATS systems.
