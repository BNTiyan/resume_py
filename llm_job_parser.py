import os
import tempfile
import textwrap
import time
import re  # For email validation

try:
    import openai_compat  # noqa: F401
except Exception:
    openai_compat = None

try:
    import job_parse_cache as _jpc
except Exception:
    _jpc = None

from src.libs.resume_and_cover_builder.utils import LoggerChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
from pathlib import Path
from langchain_core.prompt_values import StringPromptValue
from langchain_core.runnables import RunnablePassthrough
from langchain_text_splitters import TokenTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from lib_resume_builder_AIHawk.config import global_config
from langchain_community.document_loaders import TextLoader
from requests.exceptions import HTTPError as HTTPStatusError  # HTTP error handling
import openai

# Load environment variables from the .env file
load_dotenv()

# Configure the log file
log_folder = 'log/resume/gpt_resume'
if not os.path.exists(log_folder):
    os.makedirs(log_folder)
log_path = Path(log_folder).resolve()
logger.add(log_path / "gpt_resume.log", rotation="1 day", compression="zip", retention="7 days", level="DEBUG")


def _make_embeddings(api_key=None, provider="openai"):
    """
    Return a LangChain-compatible embeddings object.

    Priority:
      1. Local sentence-transformers (all-MiniLM-L6-v2) — FREE, no API key, CPU-only
      2. Gemini embeddings   — free-tier API
      3. OpenAI embeddings   — paid fallback
    """
    # 1. Try local HF embeddings first (zero cost, ~80 MB model, cached after first download)
    try:
        from langchain_huggingface import HuggingFaceEmbeddings  # langchain-huggingface >=0.1
        logger.debug("Using local HuggingFace embeddings (all-MiniLM-L6-v2) — FREE")
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    except ImportError:
        pass
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings  # older langchain
        logger.debug("Using local HuggingFace embeddings (community, all-MiniLM-L6-v2) — FREE")
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        pass

    # 2. Gemini embeddings (free tier)
    if provider == "gemini" or os.getenv("GEMINI_API_KEY"):
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            gemini_key = api_key if provider == "gemini" else os.getenv("GEMINI_API_KEY")
            if gemini_key:
                logger.debug("Using Google Gemini embeddings — free tier")
                return GoogleGenerativeAIEmbeddings(
                    model="models/embedding-001",
                    google_api_key=gemini_key,
                )
        except Exception:
            pass

    # 3. OpenAI embeddings (paid fallback)
    from langchain_openai import OpenAIEmbeddings
    openai_key = api_key if provider == "openai" else os.getenv("OPENAI_API_KEY")
    logger.warning("Falling back to OpenAI embeddings (paid). Install sentence-transformers to avoid this.")
    return OpenAIEmbeddings(
        model=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-ada-002"),
        api_key=openai_key,
    )


class LLMParser:
    def __init__(self, api_key, provider="openai"):
        self.provider = provider.lower()
        self.vectorstore = None
        self._current_url: str = ""  # set by set_body_html_with_cache
        
        # Always use local HF embeddings — free, no API key, runs on CPU.
        # Falls back to OpenAI/Gemini embeddings only if sentence-transformers is absent.
        self.llm_embeddings = _make_embeddings(api_key, provider=self.provider)

        if self.provider == "gemini":
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
            except ImportError:
                raise ImportError("langchain-google-genai is required for Gemini provider")

            gemini_key = api_key or os.getenv("GEMINI_API_KEY")
            if not gemini_key:
                raise ValueError("Gemini API key is required")

            self.llm = LoggerChatModel(
                ChatGoogleGenerativeAI(
                    model="gemini-1.5-flash",
                    google_api_key=gemini_key,
                    temperature=0.4,
                )
            )
        else:
            # Default to OpenAI
            openai_key = api_key or os.getenv("OPENAI_API_KEY")
            if not openai_key:
                raise ValueError("OpenAI API key is required")

            self.llm = LoggerChatModel(
                ChatOpenAI(
                    model="gpt-4o-mini", api_key=openai_key, temperature=0.4
                )
            )

    @staticmethod
    def _preprocess_template_string(template: str) -> str:
        """
        Preprocess the template string by removing leading whitespaces and indentation.
        Args:
            template (str): The template string to preprocess.
        Returns:
            str: The preprocessed template string.
        """
        return textwrap.dedent(template)
    
    def set_body_html(self, body_html):
        """
        Retrieves the job description from HTML, processes it, and initializes the vectorstore.
        Args:
            body_html (str): The HTML content to process.
        """

        # Save the HTML content to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as temp_file:
            temp_file.write(body_html)
            temp_file_path = temp_file.name 
        try:
            loader = TextLoader(temp_file_path, encoding="utf-8", autodetect_encoding=True)
            document = loader.load()
            logger.debug("Document successfully loaded.")
        except Exception as e:
            logger.error(f"Error during document loading: {e}")
            raise
        finally:
            os.remove(temp_file_path)
            logger.debug(f"Temporary file removed: {temp_file_path}")
        
        # Split the text into chunks
        text_splitter = TokenTextSplitter(chunk_size=500, chunk_overlap=50)
        all_splits = text_splitter.split_documents(document)
        logger.debug(f"Text split into {len(all_splits)} fragments.")
        
        # Create the vectorstore using FAISS
        try:
            self.vectorstore = FAISS.from_documents(documents=all_splits, embedding=self.llm_embeddings)
            logger.debug("Vectorstore successfully initialized.")
        except Exception as e:
            logger.error(f"Error during vectorstore creation: {e}")
            raise

    def set_body_html_with_cache(self, body_html: str, url: str = "") -> bool:
        """
        Cache-aware wrapper around set_body_html.

        If a parsed result for *url* already exists in the on-disk cache,
        this returns True immediately (caller can skip all extract_* calls and
        use get_cached_result instead).  Otherwise it delegates to set_body_html
        and returns False.

        Args:
            body_html: Raw HTML of the job posting page.
            url: Canonical URL used as the cache key.

        Returns:
            True if a cached result is available, False if the HTML was freshly processed.
        """
        self._current_url = url or ""
        if url and _jpc:
            cached = _jpc.get(url)
            if cached:
                logger.debug(f"Cache hit for {url} — skipping LLM extraction.")
                return True
        self.set_body_html(body_html)
        return False

    def get_cached_result(self) -> dict:
        """Return the cached extract_all result for the current URL, or {}."""
        if self._current_url and _jpc:
            return _jpc.get(self._current_url) or {}
        return {}

    def extract_all_with_cache(self) -> dict:
        """
        Like extract_all() but stores the result in the cache for future runs.
        Always prefer this over calling extract_all() directly.
        """
        result = self.extract_all()
        if self._current_url and _jpc:
            _jpc.put(self._current_url, result)
        return result

    def _retrieve_context(self, query: str, top_k: int = 3) -> str:
        """
        Retrieves the most relevant text fragments using the retriever.
        Args:
            query (str): The search query.
            top_k (int): Number of fragments to retrieve.
        Returns:
            str: Concatenated text fragments.
        """
        if not self.vectorstore:
            raise ValueError("Vectorstore not initialized. Run extract_job_description first.")
        
        retriever = self.vectorstore.as_retriever()
        retrieved_docs = retriever.get_relevant_documents(query)[:top_k]
        context = "\n\n".join(doc.page_content for doc in retrieved_docs)
        logger.debug(f"Context retrieved for query '{query}': {context[:200]}...")  # Log the first 200 characters
        return context
    
    def _extract_information(self, question: str, retrieval_query: str) -> str:
        """
        Generic method to extract specific information using the retriever and LLM.
        Args:
            question (str): The question to ask the LLM for extraction.
            retrieval_query (str): The query to use for retrieving relevant context.
        Returns:
            str: The extracted information.
        """
        context = self._retrieve_context(retrieval_query)

        prompt = ChatPromptTemplate.from_template(
            template="""
            You are an expert in extracting specific information from job descriptions.
            Carefully read the job description roles and responsibilities context below and provide a clear and concise answer to the question.

            Context: {context}

            Question: {question}
            Answer:
            """
        )

        formatted_prompt = prompt.format(context=context, question=question)
        logger.debug(f"Formatted prompt for extraction: {formatted_prompt[:200]}...")  # Log the first 200 characters

        try:
            chain = prompt | self.llm | StrOutputParser()
            result = chain.invoke({"context": context, "question": question})
            extracted_info = result.strip()
            logger.debug(f"Extracted information: {extracted_info}")
            return extracted_info
        except Exception as e:
            logger.error(f"Error during information extraction: {e}")
            return ""

    def extract_all(self) -> dict:
        """
        Extract all fields in a single LLM call instead of 5 separate calls.
        Reduces token usage by ~80% compared to calling each extract_* method individually.
        Returns:
            dict with keys: job_description, company_name, role, location, recruiter_email
        """
        import json as _json
        if not self.vectorstore:
            raise ValueError("Vectorstore not initialized. Run set_body_html first.")

        # Retrieve a broad context covering all fields at once
        context = self._retrieve_context("job title company name location recruiter email responsibilities", top_k=5)

        prompt = ChatPromptTemplate.from_template(
            template="""You are an expert at extracting structured data from job descriptions.
Read the context below and return a JSON object with exactly these keys:
- "job_description": concise summary of the role and responsibilities (2-4 sentences)
- "company_name": the hiring company's name (string, empty string if not found)
- "role": the job title or role being hired for (string)
- "location": work location, city/state/remote (string, empty string if not found)
- "recruiter_email": recruiter or contact email address (string, empty string if not found)

Context:
{context}

Respond with ONLY valid JSON, no markdown, no explanation."""
        )

        try:
            chain = prompt | self.llm | StrOutputParser()
            raw = chain.invoke({"context": context}).strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```$', '', raw)
            data = _json.loads(raw)
            logger.debug(f"extract_all result: {data}")

            # Validate email
            email = data.get("recruiter_email", "")
            if email and not re.match(r'[\w\.-]+@[\w\.-]+\.\w+', email):
                email = ""

            return {
                "job_description": data.get("job_description", "").strip(),
                "company_name": data.get("company_name", "").strip(),
                "role": data.get("role", "").strip(),
                "location": data.get("location", "").strip(),
                "recruiter_email": email.strip(),
            }
        except Exception as e:
            logger.error(f"extract_all failed: {e}. Falling back to individual extractions.")
            return {
                "job_description": self.extract_job_description(),
                "company_name": self.extract_company_name(),
                "role": self.extract_role(),
                "location": self.extract_location(),
                "recruiter_email": self.extract_recruiter_email(),
            }

    def extract_job_description(self) -> str:
        """
        Extracts the company name from the job description.
        Returns:
            str: The extracted job description.
        """
        question = "What is the job description of the company?"
        retrieval_query = "Job description"
        logger.debug("Starting job description extraction.")
        return self._extract_information(question, retrieval_query)

    def extract_company_name(self) -> str:
        """
        Extracts the company name from the job description.
        Returns:
            str: The extracted company name.
        """
        question = "What is the company's name?"
        retrieval_query = "Company name"
        logger.debug("Starting company name extraction.")
        return self._extract_information(question, retrieval_query)

    def extract_role(self) -> str:
        """
        Extracts the sought role/title from the job description.
        Returns:
            str: The extracted role/title.
        """
        question = "What is the role or title sought in this job description?"
        retrieval_query = "Job title"
        logger.debug("Starting role/title extraction.")
        return self._extract_information(question, retrieval_query)

    def extract_location(self) -> str:
        """
        Extracts the location from the job description.
        Returns:
            str: The extracted location.
        """
        question = "What is the location mentioned in this job description?"
        retrieval_query = "Location"
        logger.debug("Starting location extraction.")
        return self._extract_information(question, retrieval_query)

    def extract_recruiter_email(self) -> str:
        """
        Extracts the recruiter's email from the job description.
        Returns:
            str: The extracted recruiter's email.
        """
        question = "What is the recruiter's email address in this job description?"
        retrieval_query = "Recruiter email"
        logger.debug("Starting recruiter email extraction.")
        email = self._extract_information(question, retrieval_query)

        # Validate the extracted email using regex
        email_regex = r'[\w\.-]+@[\w\.-]+\.\w+'
        if re.match(email_regex, email):
            logger.debug("Valid recruiter's email.")
            return email
        else:
            logger.warning("Invalid or not found recruiter's email.")
            return ""
 
