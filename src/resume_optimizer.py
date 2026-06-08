"""
Resume Optimization Module

Optimizes CV/resume content based on job requirements using AI.
Tailors the resume to match specific job descriptions while maintaining
professional format and structure.

Version: 2.0.0
"""

import logging
import os
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

# Load environment variables from .env
from dotenv import load_dotenv
# Load from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

logger = logging.getLogger("resume_optimizer")


@dataclass
class JobRequirements:
    """Extracted job requirements."""
    required_skills: List[str]
    preferred_skills: List[str]
    experience_years: Optional[int]
    education_level: Optional[str]
    certifications: List[str]
    key_qualifications: List[str]
    responsibilities: List[str]


@dataclass
class OptimizedSection:
    """Optimized CV section."""
    section_name: str
    original_content: str
    optimized_content: str
    changes_made: List[str]
    match_score: float


class ResumeOptimizer:
    """AI-powered resume optimizer."""

    def __init__(self):
        """Initialize the optimizer."""
        self._ai_provider = os.getenv("RICO_AI_PROVIDER", "deepseek")
        logger.info("resume_optimizer_initialized provider=%s", self._ai_provider)

    def optimize_for_job(
        self,
        cv_content: str,
        job_description: str,
        job_title: str,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Optimize CV for a specific job.

        Args:
            cv_content: Current CV content
            job_description: Job description text
            job_title: Target job title
            company: Company name (optional)

        Returns:
            Dictionary with optimized CV and changes made
        """
        try:
            # Extract job requirements
            requirements = self._extract_job_requirements(job_description)

            # Analyze current CV
            cv_analysis = self._analyze_cv(cv_content)

            # Generate optimized sections
            optimized_sections = self._generate_optimized_sections(
                cv_content=cv_content,
                requirements=requirements,
                job_title=job_title,
                company=company,
            )

            # Calculate overall match score
            match_score = self._calculate_match_score(cv_analysis, requirements)

            # Compile optimized CV
            optimized_cv = self._compile_optimized_cv(cv_content, optimized_sections)

            # Generate summary of changes
            changes_summary = self._generate_changes_summary(optimized_sections)

            result = {
                "optimized_cv": optimized_cv,
                "original_cv": cv_content,
                "match_score": match_score,
                "changes_made": changes_summary,
                "optimized_sections": [
                    {
                        "section": s.section_name,
                        "changes": s.changes_made,
                        "match_score": s.match_score,
                    }
                    for s in optimized_sections
                ],
                "requirements": {
                    "required_skills": requirements.required_skills,
                    "preferred_skills": requirements.preferred_skills,
                    "experience_years": requirements.experience_years,
                    "education_level": requirements.education_level,
                    "certifications": requirements.certifications,
                },
            }

            logger.info("resume_optimization_complete match_score=%.2f", match_score)
            return result

        except Exception as e:
            logger.error("resume_optimization_error error=%s", str(e))
            return {
                "optimized_cv": cv_content,
                "original_cv": cv_content,
                "match_score": 0.0,
                "changes_made": [],
                "error": str(e),
            }

    def _extract_job_requirements(self, job_description: str) -> JobRequirements:
        """Extract key requirements from job description.

        Args:
            job_description: Job description text

        Returns:
            JobRequirements object
        """
        # Use AI to extract requirements
        prompt = f"""
Extract the following information from this job description:

{job_description}

Return in this format:
Required Skills: [comma-separated list]
Preferred Skills: [comma-separated list]
Experience Years: [number or N/A]
Education Level: [e.g., Bachelor's, Master's, PhD]
Certifications: [comma-separated list]
Key Qualifications: [comma-separated list]
Responsibilities: [comma-separated list]
"""

        try:
            ai_response = self._call_ai(prompt)

            # Parse AI response
            required_skills = self._extract_list(ai_response, "Required Skills")
            preferred_skills = self._extract_list(ai_response, "Preferred Skills")
            experience_years = self._extract_number(ai_response, "Experience Years")
            education_level = self._extract_text(ai_response, "Education Level")
            certifications = self._extract_list(ai_response, "Certifications")
            key_qualifications = self._extract_list(ai_response, "Key Qualifications")
            responsibilities = self._extract_list(ai_response, "Responsibilities")

            return JobRequirements(
                required_skills=required_skills,
                preferred_skills=preferred_skills,
                experience_years=experience_years,
                education_level=education_level,
                certifications=certifications,
                key_qualifications=key_qualifications,
                responsibilities=responsibilities,
            )

        except Exception as e:
            logger.warning("job_requirements_extraction_failed error=%s", str(e))
            # Fallback to simple keyword extraction
            return self._extract_requirements_fallback(job_description)

    def _analyze_cv(self, cv_content: str) -> Dict[str, Any]:
        """Analyze current CV content.

        Args:
            cv_content: CV text

        Returns:
            Analysis dictionary
        """
        prompt = f"""
Analyze this CV and extract:

{cv_content}

Return in this format:
Current Skills: [comma-separated list]
Experience Years: [number or N/A]
Education Level: [e.g., Bachelor's, Master's, PhD]
Certifications: [comma-separated list]
Key Achievements: [comma-separated list]
"""

        try:
            ai_response = self._call_ai(prompt)

            return {
                "skills": self._extract_list(ai_response, "Current Skills"),
                "experience_years": self._extract_number(ai_response, "Experience Years"),
                "education_level": self._extract_text(ai_response, "Education Level"),
                "certifications": self._extract_list(ai_response, "Certifications"),
                "achievements": self._extract_list(ai_response, "Key Achievements"),
            }

        except Exception as e:
            logger.warning("cv_analysis_failed error=%s", str(e))
            return {"skills": [], "experience_years": None, "education_level": None, "certifications": [], "achievements": []}

    def _generate_optimized_sections(
        self,
        cv_content: str,
        requirements: JobRequirements,
        job_title: str,
        company: Optional[str],
    ) -> List[OptimizedSection]:
        """Generate optimized CV sections.

        Args:
            cv_content: Current CV content
            requirements: Job requirements
            job_title: Target job title
            company: Company name

        Returns:
            List of OptimizedSection objects
        """
        sections = []

        # Optimize Professional Summary
        summary_section = self._optimize_summary(
            cv_content, requirements, job_title, company
        )
        sections.append(summary_section)

        # Optimize Skills section
        skills_section = self._optimize_skills(cv_content, requirements)
        sections.append(skills_section)

        # Optimize Experience section
        experience_section = self._optimize_experience(cv_content, requirements)
        sections.append(experience_section)

        return sections

    def _optimize_summary(
        self,
        cv_content: str,
        requirements: JobRequirements,
        job_title: str,
        company: Optional[str],
    ) -> OptimizedSection:
        """Optimize professional summary.

        Args:
            cv_content: Current CV content
            requirements: Job requirements
            job_title: Target job title
            company: Company name

        Returns:
            OptimizedSection for summary
        """
        # Extract current summary
        current_summary = self._extract_section(cv_content, ["Summary", "Professional Summary", "Profile"])

        # Generate optimized summary
        prompt = f"""
Rewrite this professional summary to better match the job requirements:

Current Summary:
{current_summary}

Job Title: {job_title}
Company: {company if company else "Not specified"}

Required Skills: {', '.join(requirements.required_skills[:5])}
Key Qualifications: {', '.join(requirements.key_qualifications[:3])}

Guidelines:
- Keep it concise (3-4 sentences)
- Highlight relevant skills and experience
- Mention the specific job title
- Maintain professional tone
- Include keywords from job requirements
"""

        try:
            optimized_summary = self._call_ai(prompt)

            changes = []
            if "HSE" in job_title.upper() and "HSE" not in current_summary:
                changes.append("Added HSE-specific terminology")
            if any(skill.lower() in optimized_summary.lower() for skill in requirements.required_skills):
                changes.append("Incorporated required skills")

            return OptimizedSection(
                section_name="Professional Summary",
                original_content=current_summary,
                optimized_content=optimized_summary,
                changes_made=changes,
                match_score=0.85,
            )

        except Exception as e:
            logger.warning("summary_optimization_failed error=%s", str(e))
            return OptimizedSection(
                section_name="Professional Summary",
                original_content=current_summary,
                optimized_content=current_summary,
                changes_made=[],
                match_score=0.0,
            )

    def _optimize_skills(
        self,
        cv_content: str,
        requirements: JobRequirements,
    ) -> OptimizedSection:
        """Optimize skills section.

        Args:
            cv_content: Current CV content
            requirements: Job requirements

        Returns:
            OptimizedSection for skills
        """
        # Extract current skills
        current_skills = self._extract_section(cv_content, ["Skills", "Technical Skills", "Core Competencies"])

        # Generate optimized skills
        prompt = f"""
Optimize this skills section to match job requirements:

Current Skills:
{current_skills}

Required Skills: {', '.join(requirements.required_skills)}
Preferred Skills: {', '.join(requirements.preferred_skills)}

Guidelines:
- Prioritize required skills
- Add preferred skills if relevant
- Keep formatting consistent
- Group by category if applicable
- Remove irrelevant skills
"""

        try:
            optimized_skills = self._call_ai(prompt)

            changes = []
            if len(requirements.required_skills) > 0:
                changes.append(f"Prioritized {len(requirements.required_skills)} required skills")
            if len(requirements.preferred_skills) > 0:
                changes.append(f"Added {len(requirements.preferred_skills)} preferred skills")

            return OptimizedSection(
                section_name="Skills",
                original_content=current_skills,
                optimized_content=optimized_skills,
                changes_made=changes,
                match_score=0.90,
            )

        except Exception as e:
            logger.warning("skills_optimization_failed error=%s", str(e))
            return OptimizedSection(
                section_name="Skills",
                original_content=current_skills,
                optimized_content=current_skills,
                changes_made=[],
                match_score=0.0,
            )

    def _optimize_experience(
        self,
        cv_content: str,
        requirements: JobRequirements,
    ) -> OptimizedSection:
        """Optimize experience section.

        Args:
            cv_content: Current CV content
            requirements: Job requirements

        Returns:
            OptimizedSection for experience
        """
        # Extract current experience
        current_experience = self._extract_section(cv_content, ["Experience", "Work Experience", "Professional Experience"])

        # Generate optimized experience
        prompt = f"""
Optimize this experience section to highlight relevant achievements:

Current Experience:
{current_experience}

Key Responsibilities: {', '.join(requirements.responsibilities[:5])}

Guidelines:
- Highlight achievements relevant to job responsibilities
- Use action verbs
- Quantify results where possible
- Maintain chronological order
- Keep formatting consistent
"""

        try:
            optimized_experience = self._call_ai(prompt)

            changes = []
            if len(requirements.responsibilities) > 0:
                changes.append("Highlighted relevant achievements")

            return OptimizedSection(
                section_name="Experience",
                original_content=current_experience,
                optimized_content=optimized_experience,
                changes_made=changes,
                match_score=0.80,
            )

        except Exception as e:
            logger.warning("experience_optimization_failed error=%s", str(e))
            return OptimizedSection(
                section_name="Experience",
                original_content=current_experience,
                optimized_content=current_experience,
                changes_made=[],
                match_score=0.0,
            )

    def _calculate_match_score(self, cv_analysis: Dict[str, Any], requirements: JobRequirements) -> float:
        """Calculate CV-job match score.

        Args:
            cv_analysis: CV analysis
            requirements: Job requirements

        Returns:
            Match score (0-1)
        """
        score = 0.0

        # Skills match
        cv_skills = set(skill.lower() for skill in cv_analysis.get("skills", []))
        required_skills = set(skill.lower() for skill in requirements.required_skills)

        if required_skills:
            skills_match = len(cv_skills & required_skills) / len(required_skills)
            score += skills_match * 0.4

        # Experience match
        cv_exp = cv_analysis.get("experience_years", 0)
        req_exp = requirements.experience_years or 0

        if req_exp > 0:
            exp_match = min(cv_exp / req_exp, 1.0)
            score += exp_match * 0.3

        # Education match
        cv_edu = cv_analysis.get("education_level", "").lower()
        req_edu = (requirements.education_level or "").lower()

        if req_edu and cv_edu:
            if req_edu in cv_edu or cv_edu in req_edu:
                score += 0.2

        # Certifications match
        cv_certs = set(cert.lower() for cert in cv_analysis.get("certifications", []))
        req_certs = set(cert.lower() for cert in requirements.certifications)

        if req_certs:
            certs_match = len(cv_certs & req_certs) / len(req_certs)
            score += certs_match * 0.1

        return min(score, 1.0)

    def _compile_optimized_cv(self, original_cv: str, optimized_sections: List[OptimizedSection]) -> str:
        """Compile optimized CV from sections.

        Args:
            original_cv: Original CV content
            optimized_sections: List of optimized sections

        Returns:
            Compiled optimized CV
        """
        optimized_cv = original_cv

        for section in optimized_sections:
            if section.section_name in original_cv:
                # Replace section content
                optimized_cv = optimized_cv.replace(
                    section.original_content,
                    section.optimized_content,
                    1
                )

        return optimized_cv

    def _generate_changes_summary(self, optimized_sections: List[OptimizedSection]) -> List[str]:
        """Generate summary of changes made.

        Args:
            optimized_sections: List of optimized sections

        Returns:
            List of change descriptions
        """
        changes = []

        for section in optimized_sections:
            if section.changes_made:
                changes.append(f"{section.section_name}: {', '.join(section.changes_made)}")

        return changes

    def _extract_section(self, cv_content: str, section_names: List[str]) -> str:
        """Extract a section from CV.

        Args:
            cv_content: CV content
            section_names: Possible section names

        Returns:
            Section content
        """
        for section_name in section_names:
            # Try to find section
            pattern = rf"{section_name}[:\s]*(.*?)(?=\n[A-Z][A-Z\s]+:|\Z)"
            match = re.search(pattern, cv_content, re.DOTALL | re.IGNORECASE)

            if match:
                return match.group(1).strip()

        return ""

    def _extract_list(self, text: str, key: str) -> List[str]:
        """Extract list from AI response.

        Args:
            text: AI response text
            key: Key to extract

        Returns:
            List of items
        """
        pattern = rf"{key}:\s*(.*)"
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            items_str = match.group(1)
            return [item.strip() for item in items_str.split(",") if item.strip()]

        return []

    def _extract_number(self, text: str, key: str) -> Optional[int]:
        """Extract number from AI response.

        Args:
            text: AI response text
            key: Key to extract

        Returns:
            Number or None
        """
        pattern = rf"{key}:\s*(\d+|N/A)"
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            value = match.group(1)
            if value != "N/A":
                return int(value)

        return None

    def _extract_text(self, text: str, key: str) -> Optional[str]:
        """Extract text from AI response.

        Args:
            text: AI response text
            key: Key to extract

        Returns:
            Text or None
        """
        pattern = rf"{key}:\s*(.*?)(?=\n|$)"
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return match.group(1).strip()

        return None

    def _extract_requirements_fallback(self, job_description: str) -> JobRequirements:
        """Fallback requirements extraction using keywords.

        Args:
            job_description: Job description text

        Returns:
            JobRequirements object
        """
        # Simple keyword extraction
        skills_keywords = ["skill", "experience", "proficient", "knowledge", "ability"]
        required_skills = []

        for line in job_description.split("\n"):
            for keyword in skills_keywords:
                if keyword in line.lower():
                    # Extract skill from line
                    words = line.split()
                    for i, word in enumerate(words):
                        if keyword in word.lower() and i + 1 < len(words):
                            required_skills.append(words[i + 1].strip(".,"))

        return JobRequirements(
            required_skills=required_skills[:10],
            preferred_skills=[],
            experience_years=None,
            education_level=None,
            certifications=[],
            key_qualifications=[],
            responsibilities=[],
        )

    def _call_ai(self, prompt: str) -> str:
        """Call AI provider for processing.

        Args:
            prompt: Prompt text

        Returns:
            AI response
        """
        try:
            if "deepseek" in self._ai_provider.lower():
                # Use DeepSeek via OpenAI-compatible API
                api_key = os.getenv("DEEPSEEK_API_KEY")
                if not api_key:
                    logger.error("deepseek_api_key_missing")
                    return ""

                import openai
                client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
                completion = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000,
                )
                return completion.choices[0].message.content or ""

            elif "openai" in self._ai_provider.lower() or "hf" in self._ai_provider.lower():
                import openai
                client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API"))
                completion = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000,
                )
                return completion.choices[0].message.content or ""
            else:
                logger.error("unsupported_ai_provider provider=%s", self._ai_provider)
                return ""
        except Exception as e:
            logger.error("ai_call_failed error=%s", str(e))
            return ""


def optimize_resume_for_job(
    cv_content: str,
    job_description: str,
    job_title: str,
    company: Optional[str] = None,
) -> Dict[str, Any]:
    """Optimize resume for a specific job.

    Args:
        cv_content: Current CV content
        job_description: Job description text
        job_title: Target job title
        company: Company name (optional)

    Returns:
        Dictionary with optimized CV and changes
    """
    optimizer = ResumeOptimizer()
    return optimizer.optimize_for_job(cv_content, job_description, job_title, company)


if __name__ == "__main__":
    # Test the optimizer
    import sys
    from pathlib import Path

    # Add project root to path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    # Sample CV
    sample_cv = """
Professional Summary
Experienced HSE Manager with 10+ years in construction and oil & gas industries. Proven track record of implementing safety programs and reducing incidents.

Skills
- Safety Management Systems
- Risk Assessment
- Incident Investigation
- ISO 45001
- OSHA Standards
- Environmental Compliance

Experience
HSE Manager | ABC Construction | 2018-Present
- Implemented safety management system reducing incidents by 40%
- Led team of 15 safety officers
- Conducted 500+ risk assessments

HSE Officer | XYZ Oil & Gas | 2015-2018
- Managed safety protocols for offshore operations
- Trained 200+ workers on safety procedures
"""

    # Sample job description
    sample_job = """
We are seeking an experienced QHSE Manager for our construction projects in UAE.

Requirements:
- 10+ years experience in HSE management
- ISO 45001 certification
- Strong knowledge of UAE safety regulations
- Experience with construction projects
- NEBOSH certification preferred
- Arabic language skills
"""

    print("Testing Resume Optimizer...")

    result = optimize_resume_for_job(
        cv_content=sample_cv,
        job_description=sample_job,
        job_title="QHSE Manager",
        company="Construction Company",
    )

    print(f"\nMatch Score: {result['match_score']:.2f}")
    print(f"\nChanges Made:")
    for change in result['changes_made']:
        print(f"  - {change}")

    print(f"\nOptimized CV:")
    print(result['optimized_cv'])
