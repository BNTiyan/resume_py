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
   - Line 1: Candidate's full name (bold/large font, centered)
   - Line 2: Email address (centered)
   - Line 3: Phone number with country code (centered)
   - Line 4: GitHub URL (full URL, centered)
   - Line 5: LinkedIn URL (full URL, centered)
   - Example:
     ```
     Bhavana Nare
     n.bhavana.reddy5@gmail.com
     +1-706-715-9912
     https://github.com/Bhavana5N
     https://www.linkedin.com/in/bhavana-nare-60657385
     ```
   - MUST extract from candidate's background if not explicitly provided

2. **PROFESSIONAL SUMMARY - MUST HAVE EXACTLY 15 BULLET POINTS:**
   Section header: "PROFESSIONAL SUMMARY"
   
   **CRITICAL: MAXIMIZE TECHNICAL TERMS AND KEYWORDS**
   - Every bullet MUST include at least 2-3 technical terms from the job description
   - Use EXACT technology names (e.g., "Python", "AWS", "Kubernetes", "TensorFlow", "React", "PostgreSQL")
   - Include frameworks, tools, and methodologies from the JD (e.g., "CI/CD", "Docker", "Terraform", "GraphQL")
   
   **PRIORITIZE JOB-SPECIFIC CONTENT:**
   - Bullet 1: Years of experience + PRIMARY expertise area with 3-4 key technologies from JD
   - Bullet 2: Achievement using KEY TECHNOLOGY #1 from job description with quantifiable impact
   - Bullet 3: Achievement using KEY TECHNOLOGY #2 from job description with quantifiable impact
   - Bullet 4: Achievement using KEY TECHNOLOGY #3 from job description with quantifiable impact
   - Bullet 5: Achievement matching PRIMARY RESPONSIBILITY from JD with technical stack mentioned
   - Bullet 6: Achievement matching SECONDARY RESPONSIBILITY from JD with tools/frameworks
   - Bullet 7: Leadership/team collaboration achievement with technologies used
   - Bullet 8: System architecture/scalability achievement with specific tech stack
   - Bullet 9: Process improvement/efficiency gain with automation tools mentioned
   - Bullet 10: Cross-functional collaboration with platforms/tools used
   - Bullet 11: Cloud infrastructure achievement (if in JD) with specific services (AWS/Azure/GCP)
   - Bullet 12: Data/ML achievement (if in JD) with specific frameworks/libraries
   - Bullet 13: Security/compliance achievement (if in JD) with tools/practices
   - Bullet 14: Performance optimization achievement with metrics and technologies
   - Bullet 15: Domain expertise/industry knowledge with relevant technical certifications or publications
   
   **Each bullet MUST:**
   - Start with a strong action verb (Led, Architected, Developed, Optimized, Implemented, Engineered)
   - Include 2-3 specific technologies, frameworks, or tools (e.g., "Python, TensorFlow, AWS SageMaker")
   - Include specific numbers, percentages, or measurable impact
   - Be 1-2 lines maximum
   - Use KEYWORDS and TECHNICAL TERMS directly from the job description
   - Pack as many relevant technical skills as possible while maintaining readability
   - Prioritize achievements that match job requirements over generic accomplishments

3. **WORK EXPERIENCE Section:**
   Section header: "WORK EXPERIENCE" or "PROFESSIONAL EXPERIENCE"
   
   **⚠️ CRITICAL - YOU MUST INCLUDE ALL 5 COMPANIES:**
   1. Rivian Automotive, LLC
   2. Robert Bosch, Michigan  
   3. Continental Automotive India Private Limited
   4. Teradata India Private Limited
   5. Tata Consultancy Services
   
   **CRITICAL FORMATTING REQUIREMENTS:**
   - You MUST include ALL 5 positions listed above - NO EXCEPTIONS
   - DO NOT skip any company even if you think it's less relevant
   - Each position MUST follow this EXACT TWO-LINE HEADER FORMAT with NO variations:
   ```
   Position Title | Company Name
   Month Year – Month Year | Location
   ```
   
   **HEADER FORMAT RULES (CRITICAL):**
   - Line 1: Position ONLY on the same line as Company (separated by " | ")
   - Line 2: Dates AND Location on the SAME line (separated by " | ")
   - DO NOT put dates on a separate line from location
   - DO NOT put location on a separate line from dates
   - Example CORRECT format:
     ```
     Cybersecurity AI Analyst | Rivian Automotive, LLC
     May 2025 – Present | Remote, USA
     • Achievement 1
     • Achievement 2
     ```
   - Example WRONG format (DO NOT USE):
     ```
     Cybersecurity AI Analyst | Rivian Automotive, LLC
     May 2025 – Present
     Remote, USA
     • Achievement 1
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
   
   **CRITICAL - JOB-SPECIFIC TAILORING:
   - Include ALL 5 positions from the candidate's work history (prioritize most recent first)
   - Each position must have 7-10 bullet points (minimum 7)
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
   Organize in categories with clear labels (use for bold category names):
   ```
   **Programming Languages:Python, C++, JavaScript, Java, Shell Scripting
   **Frameworks & Platforms:Django, Flask, React JS, PyTorch, TensorFlow, Keras, OpenCV
   **Cloud Technologies:AWS (S3, Lambda, CloudFormation, DynamoDB, SageMaker), Azure
   **Automation & DevOps Tools:Docker, Jenkins, CI/CD Pipelines, Terraform, Ansible
   **Data Management:Snowflake, PostgreSQL, SQLite, SQL, DynamoDB
   **Visualization Tools:Plotly, Dash, Matplotlib
   **Version Control:Git, GitHub, Bitbucket
   **Operating Systems:Linux (Ubuntu, RedHat), macOS
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
   **Machine Learning & AI:ML pipeline development, clustering algorithms, trust modeling, Bayesian models
   **Software Integration & Validation:Middleware analysis, system debugging, testbench validation
   **Pipeline Automation:CI/CD pipeline creation, PR automation, dependency management
   **Full Stack Development:Flask, Django, Dash, React JS, SQL databases
   **Computer Vision:Camera object detection, 2D to 3D box mapping, emergency braking systems
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
Bhavana Nare
n.bhavana.reddy5@gmail.com
+1-706-715-9912
https://github.com/Bhavana5N
https://www.linkedin.com/in/bhavana-nare-60657385

PROFESSIONAL SUMMARY
• [Bullet point 1 with technical details]
• [Bullet point 2 with technical details]
• [Bullet point 3 with technical details]
• [Bullet point 4 with technical details]
• [Bullet point 5 with technical details]
• [Bullet point 6 with technical details]
• [Bullet point 7 with technical details]
• [Bullet point 8 with technical details]
• [Bullet point 9 with technical details]
• [Bullet point 10 with technical details]
• [Bullet point 11 with technical details]
• [Bullet point 12 with technical details]
• [Bullet point 13 with technical details]
• [Bullet point 14 with technical details]
• [Bullet point 15 with technical details]

WORK EXPERIENCE

Cybersecurity AI Analyst | Rivian Automotive, LLC
May 2025 – Present | Remote, USA
• Developed cloud-based threat detection using Python, TensorFlow, and AWS Lambda
• Implemented ML-based anomaly detection reducing security incidents by 40%
• Built automated vulnerability scanning integrated with GitLab CI/CD pipelines
• Led security compliance initiatives for ISO 27001 and SOC 2 Type II certifications
• Architected zero-trust network security framework using Terraform and Kubernetes
• Reduced false positive alerts by 55% through ML model optimization
• Mentored team of 3 junior engineers on secure coding practices

Product Owner – Python Engineer | System Safety Engineer & Software Integrator | Robert Bosch, Michigan
August 2023 – April 2025 | Michigan, USA
• Developed resilient cloud-native services using Azure, Docker, Kubernetes, and Terraform
• Built Django REST APIs integrated with ML models for real-time diagnostics and analytics
• Automated CI/CD pipelines with Azure Pipelines reducing deployment time by 70%
• Designed PR Statistics Dashboard scaling to 1K requests/sec with AWS SageMaker
• Implemented observability, logging, and automated alerts across distributed microservices
• Reduced PR review times by 60% (5 days to 2 days) through ML-powered predictions
• Coordinated ISO 26262 and ASPICE compliance reviews with cross-functional teams

Scrum Master – ADAS Camera Object Detection, Tool Architect & Developer | Continental Automotive India Private Limited
May 2019 – July 2023 | Bangalore, India
• Led agile teams developing camera object detection systems for emergency braking
• Architected AUTOSIM prototype reducing manual testing effort by 70%
• Developed TM_KPI_PORTAL dashboard automating KPI reporting for 50+ engineers
• Implemented 2D to 3D box mapping improving object detection accuracy by 25%
• Built Python automation tools processing 10K+ test cases daily
• Managed sprint planning and retrospectives for distributed team of 15 engineers
• Improved deployment reliability by 40% through automated validation frameworks

Python Developer and Data Analyst | Teradata India Private Limited
August 2018 – April 2019 | Hyderabad, India
• Developed ETL pipelines using Python and SQL processing 500GB+ daily data volumes
• Built data visualization dashboards using Plotly and Dash for executive reporting
• Optimized SQL queries reducing data processing time by 50%
• Automated data quality checks catching 95% of anomalies before production

Senior Software Engineer | Tata Consultancy Services
June 2014 – July 2018 | Hyderabad, India
• Developed full-stack applications using Java, JavaScript, and MySQL
• Built RESTful APIs serving 10K+ daily users with 99.9% uptime
• Implemented automated testing frameworks reducing bug count by 60%
• Led code reviews and mentored 5 junior developers on best practices

[⚠️ REMEMBER: ALL 5 COMPANIES MUST BE INCLUDED IN EVERY RESUME]

EDUCATION

Degree | University
Month Year – Month Year | GPA: X.X/4.0

TECHNICAL SKILLS

**Programming Languages:Python, C++, JavaScript, Java
**Frameworks & Platforms:Django, Flask, React JS, PyTorch, TensorFlow
**Cloud Technologies:AWS (S3, Lambda, CloudFormation), Azure
**Automation & DevOps Tools:Docker, Jenkins, CI/CD, Terraform
**Data Management:PostgreSQL, SQLite, SQL, DynamoDB
**Visualization Tools:Plotly, Dash, Matplotlib
**Version Control:Git, GitHub, Bitbucket

FUNCTIONAL EXPERTISE

**Machine Learning & AI:ML pipeline development, clustering, trust modeling
**Software Integration & Validation:Middleware analysis, debugging, testbench validation
**Pipeline Automation:CI/CD pipeline creation, PR automation, dependency management
**Full Stack Development:Flask, Django, Dash, React JS, SQL databases
**Computer Vision:Camera object detection, 2D to 3D mapping, emergency braking systems

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
- **CONTACT INFORMATION IS MANDATORY** - ALWAYS include the full header with:
  * Line 1: Candidate's full name
  * Line 2: Email address
  * Line 3: Phone number with country code (+1-XXX-XXX-XXXX)
  * Line 4: GitHub URL (FULL URL starting with https://)
  * Line 5: LinkedIn URL (FULL URL starting with https://)
  * Each contact detail on its OWN SEPARATE LINE
- **ALL 5 COMPANIES ARE MANDATORY** - You MUST include EVERY company:
  1. Rivian Automotive, LLC (most recent)
  2. Robert Bosch, Michigan
  3. Continental Automotive India Private Limited
  4. Teradata India Private Limited
  5. Tata Consultancy Services (oldest)
- NO generic placeholders like "Company" or "Position" - ALWAYS use REAL names from candidate's background
- COMPANY NAMES ARE MANDATORY - every position MUST include the company name after the position title
- If position title contains "|", format as: "Position Part 1 | Position Part 2 | Company Name" (company is LAST)
- EXACTLY 15 bullet points in Professional Summary (each with 2-3 technical terms)
- Include ALL 5 work positions with company names - DO NOT SKIP ANY
- Each position must have 7-10 bullet points (minimum 7)
- EVERY achievement must include numbers/metrics
- Focus on relevance to the target job
- Dates format: "Month Year – Month Year" or "Month Year – Present"
- Location format: "City, State/Country" or "Remote, Country"

**⚠️ FINAL REMINDER BEFORE YOU START:**
1. Generate the HEADER first (5 separate lines for contact info)
2. Generate PROFESSIONAL SUMMARY with EXACTLY 15 bullets
3. Generate WORK EXPERIENCE with ALL 5 COMPANIES in order:
   - Rivian Automotive, LLC (first)
   - Robert Bosch, Michigan (second)
   - Continental Automotive India Private Limited (third)
   - Teradata India Private Limited (fourth)
   - Tata Consultancy Services (fifth/last)
4. Each company MUST have 2 lines: "Position | Company" then "Dates | Location"
5. Then generate EDUCATION, TECHNICAL SKILLS, FUNCTIONAL EXPERTISE, KEY ACHIEVEMENTS, PUBLICATIONS

DO NOT STOP AFTER 2-3 COMPANIES. INCLUDE ALL 5.
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
Generate a compelling professional summary with EXACTLY 15 bullet points for a {job_title} position at {company_name}.

**Job Description:**
{job_description}

**Candidate Background:**
{resume_text}

**CRITICAL: MAXIMIZE TECHNICAL KEYWORDS**
- Every bullet MUST include 2-3 specific technical terms, tools, or frameworks
- Use EXACT technology names from the job description (e.g., Python, AWS, Kubernetes, TensorFlow, Docker)
- Include programming languages, frameworks, cloud platforms, databases, and methodologies
- Pack relevant technical skills while maintaining natural readability

**Instructions:**
Create 15 impactful bullet points that:
1. Highlight the most relevant skills and experience for THIS specific role
2. Include quantifiable achievements (%, $, scale, impact)
3. Mention 2-3 key technologies/skills from the job description in EACH bullet
4. Show progression and leadership with technical context
5. Demonstrate domain expertise with specific tools/frameworks
6. Are action-oriented and results-focused
7. Are concise (1-2 lines each)
8. Use strong verbs (Led, Architected, Engineered, Scaled, Optimized, Implemented, Developed)
9. Show both technical depth (specific technologies) and business impact (metrics)
10. Create a compelling narrative of the candidate's value
11. Include cloud platforms (AWS/Azure/GCP) if mentioned in JD
12. Include ML/AI frameworks (TensorFlow/PyTorch/scikit-learn) if mentioned in JD
13. Include DevOps tools (Docker/Kubernetes/Jenkins/Terraform) if mentioned in JD
14. Include data technologies (SQL/NoSQL/Snowflake/Spark) if mentioned in JD
15. Prioritize technical skills that appear multiple times in the job description

**Format:**
Return ONLY the 15 bullet points, one per line, starting with "•"
Do NOT include a header or section title.
Do NOT include any other text.

**Example Format:**
• Architected scalable microservices using Python, FastAPI, and PostgreSQL, reducing API latency by 60% and handling 10M+ requests/day
• Led cloud migration to AWS (EC2, S3, Lambda, RDS) saving $500K annually while improving system reliability to 99.99% uptime
• Developed ML pipelines using TensorFlow, Kubeflow, and Databricks for real-time predictions serving 5M+ users daily

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
   - 7-10 impactful bullet points (MINIMUM 7) that:
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
• Highlight 1 with techincal details
• Highlight 2 with techincal details
• Highlight 3 with techincal details
• Highlight 4 with techincal details
• Achievement 1 with quantifiable results
• Achievement 2 with quantifiable results
• Achievement 3 with quantifiable results

[Repeat for ALL positions - include ALL companies from candidate's background]

**CRITICAL:**
- NEVER omit company names
- NEVER use placeholders like "Company" or "N/A"
- ALWAYS use real company names from the candidate's background
- Company name is ALWAYS the last part after "|" separators
"""

