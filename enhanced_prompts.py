"""
Enhanced Resume Generation Prompts
Focuses on 2-page format, 10 bullet professional summary, and most recent relevant experience
"""

ENHANCED_RESUME_PROMPT = """
You are an expert resume writer creating a tailored, ATS-optimized resume for a specific job application.

**Job Details:**
Company: {company_name}
Position: {job_title}
Job Description: {job_description}

**Candidate's Background:**
{resume_text}

**CRITICAL REQUIREMENTS:**

**JOB DESCRIPTION ANALYSIS - READ THIS FIRST:**
1. Identify the TOP 10 key requirements from the job description (technologies, skills, responsibilities)
2. Identify the TOP 7 keywords/phrases that appear multiple times in the job description
3. Identify the PRIMARY focus areas (e.g., "machine learning", "cloud infrastructure", "full-stack development", "data engineering")
4. Match candidate's experience to these requirements and HIGHLIGHT matching achievements prominently

1. **Header Section:**
   - Candidate's full name
   - Contact: Email | Phone | GitHub | LinkedIn (all on one line)

2. **PROFESSIONAL SUMMARY - MUST HAVE EXACTLY 10 BULLET POINTS:**
   Section header: "PROFESSIONAL SUMMARY"
   
   **PRIORITIZE JOB-SPECIFIC CONTENT:**
   - Bullet 1: Years of experience + PRIMARY expertise area from job description (use exact keywords from JD)
   - Bullet 2: Achievement using KEY TECHNOLOGY from job description (e.g., if JD mentions "AWS", highlight AWS achievements)
   - Bullet 3: Achievement using KEY TECHNOLOGY from job description (e.g., if JD mentions "Python", highlight Python achievements)
   - Bullet 4: Achievement matching PRIMARY RESPONSIBILITY from job description (use similar language/phrasing)
   - Bullet 5: Achievement matching SECONDARY RESPONSIBILITY from job description
   - Bullet 6: Leadership/team collaboration achievement (if mentioned in JD)
   - Bullet 7: System architecture/scalability achievement (if mentioned in JD)
   - Bullet 8: Process improvement/efficiency gain matching JD requirements
   - Bullet 9: Cross-functional collaboration matching JD requirements
   - Bullet 10: Domain expertise/industry knowledge matching JD requirements
   
   **Each bullet MUST:**
   - Start with a strong action verb (Led, Architected, Developed, Optimized, Implemented)
   - Include specific numbers, percentages, or measurable impact
   - Be 1-2 lines maximum
   - Use KEYWORDS and PHRASES directly from the job description
   - Prioritize achievements that match job requirements over generic accomplishments

3. **WORK EXPERIENCE Section:**
   Section header: "WORK EXPERIENCE" or "PROFESSIONAL EXPERIENCE"
   
   **CRITICAL FORMATTING REQUIREMENTS:**
   - You MUST include ALL positions from the candidate's background (up to 5 positions)
   - Each position MUST follow this EXACT format with NO variations:
   ```
   Position Title | Company Name
   Month Year – Month Year | Location
   • Achievement with quantifiable result (e.g., "Reduced costs by 40% ($500K annually)")
   • Achievement with quantifiable result
   • Achievement with quantifiable result
   • Achievement with quantifiable result
   ```
   
   **MANDATORY RULES:**
   - ALWAYS include the company name after the position title, separated by " | "
   - If the position title contains "|" (e.g., "Product Owner | Python Engineer"), the format becomes:
     "Product Owner | Python Engineer | Company Name" (company is ALWAYS the LAST part)
   - NEVER omit company names - they are REQUIRED for every position
   - Use the EXACT company names from the candidate's background (e.g., "Rivian Automotive, LLC", "Robert Bosch, Michigan")
   - Use the EXACT job titles from the candidate's background
   - Dates MUST be in format "Month Year – Month Year" or "Month Year – Present"
   - Location MUST be included (e.g., "Remote, USA", "Michigan, USA", "Bangalore, India")
   
   **CRITICAL - JOB-SPECIFIC TAILORING:** 
   - Include ALL 5 positions from the candidate's work history (prioritize most recent first)
   - Each position must have 4-6 bullet points
   - **FOR EACH BULLET POINT:**
     * Prioritize achievements that use KEYWORDS from the job description
     * If the job description mentions specific technologies (e.g., "Kubernetes", "TensorFlow", "React"), 
       highlight achievements using those EXACT technologies
     * If the job description mentions specific responsibilities (e.g., "ML pipeline development", 
       "microservices architecture"), highlight achievements matching those responsibilities
     * Use similar language/phrasing from the job description (e.g., if JD says "scalable systems", 
       use "scalable systems" in your bullet points)
     * Reorder bullet points to put most relevant achievements FIRST
   - If a position has no relevant achievements, still include it with 2-3 bullets focusing on relevant technologies/skills

4. **EDUCATION Section:**
   Section header: "EDUCATION"
   ```
   Degree Name | University Name
   Month Year – Month Year | GPA: X.X/4.0
   - Thesis/Notable achievement (if applicable)
   ```

5. **TECHNICAL SKILLS Section:**
   Section header: "TECHNICAL SKILLS"
   Organize in categories with clear labels (use ** for bold category names):
   ```
   **Programming Languages:** Python, C++, JavaScript, Java, Shell Scripting
   **Frameworks & Platforms:** Django, Flask, React JS, PyTorch, TensorFlow, Keras, OpenCV
   **Cloud Technologies:** AWS (S3, Lambda, CloudFormation, DynamoDB, SageMaker), Azure
   **Automation & DevOps Tools:** Docker, Jenkins, CI/CD Pipelines, Terraform, Ansible
   **Data Management:** Snowflake, PostgreSQL, SQLite, SQL, DynamoDB
   **Visualization Tools:** Plotly, Dash, Matplotlib
   **Version Control:** Git, GitHub, Bitbucket
   **Operating Systems:** Linux (Ubuntu, RedHat), macOS
   ```
   **JOB-SPECIFIC PRIORITIZATION:**
   - **FIRST**: List ALL skills mentioned in the job description (even if candidate has limited experience)
   - **SECOND**: List skills from candidate's background that match job requirements
   - **THIRD**: List other relevant skills
   - If job description mentions specific tools/technologies, create a dedicated category for them
   - Reorder categories to put most relevant skills FIRST
   - Use EXACT terminology from the job description (e.g., if JD says "Kubernetes", don't just say "container orchestration")
   - Keep it concise and organized
   - Use bold (**text**) for category names

6. **FUNCTIONAL EXPERTISE Section:**
   Section header: "FUNCTIONAL EXPERTISE"
   Format like Technical Skills with categories:
   ```
   **Machine Learning & AI:** ML pipeline development, clustering algorithms, trust modeling, Bayesian models
   **Software Integration & Validation:** Middleware analysis, system debugging, testbench validation
   **Pipeline Automation:** CI/CD pipeline creation, PR automation, dependency management
   **Full Stack Development:** Flask, Django, Dash, React JS, SQL databases
   **Computer Vision:** Camera object detection, 2D to 3D box mapping, emergency braking systems
   ```

7. **KEY ACHIEVEMENTS Section:**
   Section header: "KEY ACHIEVEMENTS"
   Format with bullet points (extract from work experience):
   ```
   • Reduced manual validation and testing efforts by 70% through automation using Jenkins, Docker, and Azure
   • Improved workflow efficiency by automating PR creation and dependency management with Azure Pipelines
   • Created AUTOSIM prototype supporting multiple integrations, reducing manual effort by 70%
   • Migrated object detection from 2D to 3D box mapping, improving system accuracy
   • Enhanced deployment reliability by automating installation processes across virtual and real nodes
   • Designed innovative tools that reduced release times and improved deployment workflows by 60%
   ```
   - Extract 5-8 most impressive achievements from work experience
   - Each achievement must have quantifiable impact (%, time saved, cost reduction)
   - Focus on achievements relevant to the target job

8. **PUBLICATIONS Section:**
   Section header: "PUBLICATIONS"
   Format with bullet points:
   ```
   • Bhavana Nare, et al., "Computational Trust Framework for Human-Robot Teams," IEEE Xplore, Document 11127674, 2024. Available at https://ieeexplore.ieee.org/document/11127674
   ```
   - Include all publications with full citations
   - Add URLs if available

9. **Optional Sections (if relevant):**
   - CERTIFICATIONS (if applicable)
   - KEY PROJECTS (if highly relevant)

**OUTPUT FORMAT:**
```
Full Name
email@domain.com | Phone | github.com/username | linkedin.com/in/username

PROFESSIONAL SUMMARY
• [Bullet point 1 with  techincal details ]
• [Bullet point 2 with  techincal details ]
• [Bullet point 3 with  techincal details ]
• [Bullet point 4 with  techincal details ]
• [Bullet point 5 with  techincal details ]
• [Bullet point 6 with  techincal details ]
• [Bullet point 7 with  techincal details ]
• [Bullet point 8 with  techincal details ]
• [Bullet point 9 with  techincal details ]
• [Bullet point 10 with  techincal details ]

WORK EXPERIENCE

Position Title | Company Name
Month Year – Month Year | Location
• Highlight 1 with techincal details
• Highlight 2 with techincal details
• Highlight 3 with techincal details
• Highlight 4 with techincal details
• Achievement 1 with quantifiable results
• Achievement 2 with quantifiable results
• Achievement 3 with quantifiable results


Position Title | Company Name
Month Year – Month Year | Location
• Highlight 1 with techincal details
• Highlight 2 with techincal details
• Highlight 3 with techincal details
• Highlight 4 with techincal details
• Achievement 1 with quantifiable results
• Achievement 2 with quantifiable results
• Achievement 3 with quantifiable results

[Repeat for ALL positions - include ALL 5 companies from candidate's background]

EDUCATION

Degree | University
Month Year – Month Year | GPA: X.X/4.0

TECHNICAL SKILLS

**Programming Languages:** Python, C++, JavaScript, Java
**Frameworks & Platforms:** Django, Flask, React JS, PyTorch, TensorFlow
**Cloud Technologies:** AWS (S3, Lambda, CloudFormation), Azure
**Automation & DevOps Tools:** Docker, Jenkins, CI/CD, Terraform
**Data Management:** PostgreSQL, SQLite, SQL, DynamoDB
**Visualization Tools:** Plotly, Dash, Matplotlib
**Version Control:** Git, GitHub, Bitbucket

FUNCTIONAL EXPERTISE

**Machine Learning & AI:** ML pipeline development, clustering, trust modeling
**Software Integration & Validation:** Middleware analysis, debugging, testbench validation
**Pipeline Automation:** CI/CD pipeline creation, PR automation, dependency management
**Full Stack Development:** Flask, Django, Dash, React JS, SQL databases
**Computer Vision:** Camera object detection, 2D to 3D mapping, emergency braking systems

KEY ACHIEVEMENTS

• Reduced manual validation and testing efforts by 50% through automation using Jenkins, Docker, and Azure
• Improved workflow efficiency by automating PR creation and dependency management with Azure Pipelines
• Created AUTOSIM prototype supporting multiple integrations, reducing manual effort by 70%
• Migrated object detection from 2D to 3D box mapping, improving system accuracy
• Enhanced deployment reliability by automating installation processes across virtual and real nodes
• Designed innovative tools that reduced release times and improved deployment workflows by 60%
• Designed and implemented innovative deployment tools that leverage YAML configurations, significantly reducing software release times by automating installation.

PUBLICATIONS

• Bhavana Nare, et al., "Computational Trust Framework for Human-Robot Teams," IEEE Xplore, Document 11127674, 2024. Available at https://ieeexplore.ieee.org/document/11127674
```

**CRITICAL RULES:**
- NO generic placeholders like "Company" or "Position" - ALWAYS use REAL names from candidate's background
- COMPANY NAMES ARE MANDATORY - every position MUST include the company name after the position title
- If position title contains "|", format as: "Position Part 1 | Position Part 2 | Company Name" (company is LAST)
- EXACTLY 10 bullet points in Professional Summary
- Include ALL 5 work positions with company names
- EVERY achievement must include numbers/metrics
- Focus on relevance to the target job
- Dates format: "Month Year – Month Year" or "Month Year – Present"
- Location format: "City, State/Country" or "Remote, Country"
"""

ENHANCED_COVER_LETTER_PROMPT = """
You are an expert cover letter writer creating a compelling, personalized cover letter for a specific job application.

**Job Details:**
Company: {company_name}
Position: {job_title}
Job Description: {job_description}

**Candidate's Background:**
{resume_text}

**Requirements:**
1. Create a 1-PAGE cover letter that:
   - Opens with a compelling hook that shows genuine interest in the company and role
   - Demonstrates understanding of the company's mission, products, or recent news
   - Highlights 3-4 most relevant achievements that directly address the job requirements
   - Provides specific examples with quantifiable results
   - Shows cultural fit and alignment with company values
   - Closes with a confident call to action

2. Structure:
   - Opening paragraph: Hook + Why this company + Why this role
   - Body paragraphs (2-3): Relevant achievements and skills
   - Closing paragraph: Value proposition + Next steps

3. Tone:
   - Professional yet personable
   - Confident without being arrogant
   - Enthusiastic about the opportunity
   - Match the company's communication style (formal for enterprise, casual for startups)

4. Content Guidelines:
   - Don't repeat the resume - provide context and stories
   - Use the STAR method (Situation, Task, Action, Result) for examples
   - Connect your experience directly to their needs
   - Show, don't tell (use specific examples, not generic claims)
   - Keep it concise - aim for 3-4 paragraphs total

**Output Format:**
Provide the complete cover letter as formatted text, ready to be converted to PDF.
Do NOT include the date, address, or "To Whom It May Concern" - these will be added automatically.
Start with "Dear Hiring Manager," or "Dear [Company] Team,"
End with "Sincerely," (closing signature will be added automatically).
"""

PROFESSIONAL_SUMMARY_PROMPT = """
Generate a compelling professional summary with EXACTLY 10 bullet points for a {job_title} position at {company_name}.

**Job Description:**
{job_description}

**Candidate Background:**
{resume_text}

**Instructions:**
Create 10 impactful bullet points that:
1. Highlight the most relevant skills and experience for THIS specific role
2. Include quantifiable achievements (%, $, scale, impact)
3. Mention key technologies/skills from the job description
4. Show progression and leadership
5. Demonstrate domain expertise
6. Are action-oriented and results-focused
7. Are concise (1-2 lines each)
8. Use strong verbs (Led, Architected, Scaled, Optimized, etc.)
9. Show both technical depth and business impact
10. Create a compelling narrative of the candidate's value

**Format:**
Return ONLY the 10 bullet points, one per line, starting with "•"
Do NOT include a header or section title.
Do NOT include any other text.

Example format:
• Led cross-functional team of 12 engineers to deliver cloud migration, reducing infrastructure costs by 40% ($2M annually)
• Architected and implemented microservices platform serving 50M+ daily active users with 99.99% uptime
...
"""

WORK_EXPERIENCE_PROMPT = """
Generate a tailored work experience section for a {job_title} role at {company_name}.

**Job Description:**
{job_description}

**Candidate's Work History:**
{experience_text}

**CRITICAL REQUIREMENTS:**
1. Include ALL positions from the candidate's work history (up to 5 positions)
2. Company names are MANDATORY - every position MUST include the company name
3. Use EXACT format with NO variations

**Instructions:**
1. For EACH position, provide:
   - Position Title | Company Name
     * If position title contains "|", format as: "Position Part 1 | Position Part 2 | Company Name"
     * Company name is ALWAYS the LAST part after all "|" separators
   - Employment Period | Location
     * Format: "Month Year – Month Year" or "Month Year – Present"
     * Include full location: "City, State/Country" or "Remote, Country"
   - 4-6 impactful bullet points that:
     * Align with the job requirements
     * Include quantifiable results (%, $, numbers, scale)
     * Highlight relevant technologies and skills from job description
     * Show increasing responsibility and impact
     * Use strong action verbs (Led, Architected, Developed, Optimized, Implemented)

2. Prioritize most recent positions first, but include ALL positions

3. For each bullet point:
   - Use keywords from the job description
   - Match technologies mentioned in the JD
   - Show quantifiable impact
   - Reorder to put most relevant achievements FIRST

**MANDATORY FORMAT (use EXACTLY this format):**
Position Title | Company Name
Month Year – Month Year | Location
• Achievement/responsibility with quantifiable impact
• Achievement/responsibility with quantifiable impact
• Achievement/responsibility with quantifiable impact
• Achievement/responsibility with quantifiable impact

[Repeat for ALL positions - include ALL companies from candidate's background]

**CRITICAL:**
- NEVER omit company names
- NEVER use placeholders like "Company" or "N/A"
- ALWAYS use real company names from the candidate's background
- Company name is ALWAYS the last part after "|" separators
"""

