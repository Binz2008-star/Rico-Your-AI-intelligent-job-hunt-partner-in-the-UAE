"""
Unified Application Documents Module

Combines resume optimization and cover letter generation into a single interface
for comprehensive application document preparation.

Version: 2.0.0
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load environment variables
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

from resume_optimizer import ResumeOptimizer, JobRequirements
from cover_letter_writer import CoverLetterIdentity, generate_cover_letter_with_identity

logger = logging.getLogger("application_documents")


class ApplicationDocumentsError(Exception):
    """Custom exception class for application document operations."""
    pass


@dataclass(frozen=True)
class ApplicationDocuments:
    """Complete application documents package (Immutable Data Structure)."""
    optimized_cv: str
    cover_letter: str
    match_score: float
    changes_made: List[str] = field(default_factory=list)
    ai_enhanced: bool = True


class ApplicationDocumentsGenerator:
    """Unified generator for all application documents with dependency injection support."""

    def __init__(self, ai_provider: Optional[str] = None, optimizer: Optional[ResumeOptimizer] = None):
        """
        Initialize the generator with dependency injection.

        Args:
            ai_provider: AI provider to use (deepseek, openai, etc.)
            optimizer: Optional injected instance of ResumeOptimizer for testability.
        """
        self._ai_provider = ai_provider or "default"
        self._resume_optimizer = optimizer or ResumeOptimizer()
        logger.info("application_documents_generator_initialized provider=%s", self._ai_provider)

    def generate_complete_package(
        self,
        cv_content: str,
        job_description: str,
        job_title: str,
        job_company: str,
        job_location: str,
        user_name: str,
        user_location: str,
        user_title: Optional[str] = None,
        user_company: Optional[str] = None,
        user_years_experience: Optional[float] = None,
        user_strengths: Optional[List[str]] = None,
        ai_enabled: bool = True
    ) -> ApplicationDocuments:
        """Generate complete application documents package.

        Args:
            cv_content: Current CV/resume text
            job_description: Job posting description
            job_title: Job title
            job_company: Company name
            job_location: Job location
            user_name: User's name
            user_location: User's location
            user_title: User's current title
            user_company: User's current company
            user_years_experience: Years of experience
            user_strengths: List of verified strengths
            ai_enabled: Enable AI enhancement

        Returns:
            ApplicationDocuments package with CV, cover letter, and metadata

        Raises:
            ApplicationDocumentsError: If generation fails at any pipeline step
        """
        if not cv_content or not job_description:
            raise ApplicationDocumentsError("CV content and Job Description cannot be empty.")

        logger.info("generating_application_documents_package job=%s company=%s", job_title, job_company)

        try:
            # Generate optimized CV
            logger.info("step_1_optimizing_resume")
            cv_result = self._resume_optimizer.optimize_for_job(
                cv_content=cv_content,
                job_description=job_description,
                job_title=job_title
            )

            # Generate cover letter
            logger.info("step_2_generating_cover_letter")
            job_data = {
                "title": job_title,
                "company": job_company,
                "location": job_location,
                "description": job_description
            }

            identity = CoverLetterIdentity(
                name=user_name,
                location=user_location,
                title=user_title,
                company=user_company,
                years_experience=user_years_experience,
                verified_strengths=user_strengths or [],
                ai_enabled=ai_enabled
            )

            cover_letter = generate_cover_letter_with_identity(job_data, identity)

            # Compile package
            logger.info("step_3_compiling_package")
            package = ApplicationDocuments(
                optimized_cv=cv_result.get("optimized_cv", cv_content),
                cover_letter=cover_letter,
                match_score=cv_result.get("match_score", 0.0),
                changes_made=cv_result.get("changes_made", []),
                ai_enhanced=ai_enabled
            )

            logger.info("application_documents_package_complete score=%.2f", package.match_score)
            return package

        except Exception as e:
            logger.error("application_documents_generation_failed error=%s", str(e), exc_info=True)
            raise ApplicationDocumentsError(f"Document production pipeline failed: {str(e)}")

    def generate_resume_only(
        self,
        cv_content: str,
        job_description: str,
        job_title: str
    ) -> Dict[str, Any]:
        """Generate only optimized resume.

        Args:
            cv_content: Current CV/resume text
            job_description: Job posting description
            job_title: Job title

        Returns:
            Dictionary with optimized CV and metadata
        """
        logger.info("generating_resume_only job=%s", job_title)
        return self._resume_optimizer.optimize_for_job(
            cv_content=cv_content,
            job_description=job_description,
            job_title=job_title
        )

    def generate_cover_letter_only(
        self,
        job_description: str,
        job_title: str,
        job_company: str,
        job_location: str,
        user_name: str,
        user_location: str,
        user_title: Optional[str] = None,
        user_company: Optional[str] = None,
        user_years_experience: Optional[float] = None,
        user_strengths: Optional[List[str]] = None,
        ai_enabled: bool = True
    ) -> str:
        """Generate only cover letter.

        Args:
            job_description: Job posting description
            job_title: Job title
            job_company: Company name
            job_location: Job location
            user_name: User's name
            user_location: User's location
            user_title: User's current title
            user_company: User's current company
            user_years_experience: Years of experience
            user_strengths: List of verified strengths
            ai_enabled: Enable AI enhancement

        Returns:
            Generated cover letter text
        """
        logger.info("generating_cover_letter_only job=%s company=%s", job_title, job_company)

        job_data = {
            "title": job_title,
            "company": job_company,
            "location": job_location,
            "description": job_description
        }

        identity = CoverLetterIdentity(
            name=user_name,
            location=user_location,
            title=user_title,
            company=user_company,
            years_experience=user_years_experience,
            verified_strengths=user_strengths or [],
            ai_enabled=ai_enabled
        )

        return generate_cover_letter_with_identity(job_data, identity)


# Test/Demo Section
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 70)
    print("APPLICATION DOCUMENTS GENERATOR - TEST")
    print("=" * 70)

    # Sample data
    sample_cv = """Professional Summary
Experienced HSE Manager with 10+ years in construction and oil & gas industries.

Skills
- Safety Management Systems
- Risk Assessment
- Incident Investigation
- ISO 45001
- OSHA Standards

Experience
HSE Manager | ABC Construction | 2018-Present
- Implemented safety management system
- Led team of 15 safety officers
- Conducted 500+ risk assessments

HSE Officer | XYZ Oil & Gas | 2015-2018
- Managed safety protocols for offshore operations
- Trained 200+ workers on safety procedures
"""

    sample_job = {
        "description": "We are looking for an experienced QHSE Manager to lead our safety and environmental compliance programs. The ideal candidate will have 10+ years of experience in construction, ISO 45001 certification, and strong leadership skills. Experience with UAE regulations and environmental compliance is preferred.",
        "title": "QHSE Manager",
        "company": "ABC Construction",
        "location": "Dubai, UAE"
    }

    print(f"\nTest Configuration:")
    print(f"  Job: {sample_job['title']} at {sample_job['company']}")
    print(f"  Location: {sample_job['location']}")

    print("\n" + "=" * 70)
    print("GENERATING COMPLETE PACKAGE")
    print("=" * 70)

    try:
        generator = ApplicationDocumentsGenerator()

        package = generator.generate_complete_package(
            cv_content=sample_cv,
            job_description=sample_job["description"],
            job_title=sample_job["title"],
            job_company=sample_job["company"],
            job_location=sample_job["location"],
            user_name="Ahmed Al-Rashid",
            user_location="Dubai, UAE",
            user_title="HSE Manager",
            user_company="XYZ Environmental Services",
            user_years_experience=12,
            user_strengths=[
                "ISO 45001 implementation",
                "Environmental compliance management",
                "Team leadership",
                "Risk assessment",
                "Safety audit preparation"
            ],
            ai_enabled=True
        )

        print("\n" + "=" * 70)
        print("PACKAGE RESULTS")
        print("=" * 70)
        print(f"Match Score: {package.match_score:.2%}")
        print(f"AI Enhanced: {package.ai_enhanced}")
        print(f"Changes Made: {', '.join(package.changes_made)}")

        print("\n" + "=" * 70)
        print("OPTIMIZED CV")
        print("=" * 70)
        print(package.optimized_cv)

        print("\n" + "=" * 70)
        print("COVER LETTER")
        print("=" * 70)
        print(package.cover_letter)

        print("\n" + "=" * 70)
        print("TEST COMPLETE")
        print("=" * 70)
        print("✅ Application documents package generated successfully!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
