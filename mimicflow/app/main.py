# mimicflow/app/main.py

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from PyPDF2 import PdfReader
import os
from fastapi import File, UploadFile
from fastapi.responses import FileResponse

# Utils to keep track of progress
from .progress_manager import ProgressManager


# OpenAI for PDF summarization
from langchain_google_genai import ChatGoogleGenerativeAI

# Import your LinkedInFilter, LinkedInSearchAgent from your new location:
from mimicflow.agents.linkedin.linkedin_agent import LinkedInFilter, LinkedInSearchAgent

app = FastAPI()
progress_manager = ProgressManager()

# Add CORS middleware:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to ["http://localhost:5173"] etc.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 1) A Pydantic model to define the request body structure
class LinkedInExamplesRequest(BaseModel):
    templates: list[str]
    mode: str


class SummarySaveRequest(BaseModel):
    summary: str


def format_excerpts(input_text):
    # Split the input text by the '----' delimiter
    excerpts = input_text.split("----")
    # Remove any extra whitespace or empty lines
    excerpts = [excerpt.strip() for excerpt in excerpts if excerpt.strip()]

    # Create the numbered format
    formatted_output = "<MESSAGE TEMPLATES>\n"  # Opening tag
    for i, excerpt in enumerate(excerpts, start=1):
        formatted_output += f"{i}. {excerpt}\n"
    formatted_output += "</MESSAGE TEMPLATES>"  # Closing tag

    return formatted_output.strip()


# 2) The new endpoint
@app.post("/api/linkedin-examples")
def handle_linkedin_examples(data: LinkedInExamplesRequest):
    """
    Endpoint to receive the connection request templates from the frontend.
    """
    # Join the templates with the delimiter
    templates_text = "———".join(data.templates)

    formatted_excerpts = format_excerpts(templates_text)
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = formatted_excerpts

    print("Received connection requests:\n", SYSTEM_PROMPT)
    return {"message": "Connection requests received successfully!"}


@app.post("/api/save-summary")
def save_summary(data: SummarySaveRequest):
    global SUMMARY
    SUMMARY = "<CV SUMMARY>\n" + data.summary + "\n</CV SUMMARY>"
    print("User's summary saved:\n", SUMMARY)
    return {"message": "Summary successfully saved."}


class GeminiKeyRequest(BaseModel):
    key: str


class OpenAIKeyRequest(BaseModel):
    key: str


@app.post("/api/set-key")
def set_key(data: GeminiKeyRequest):
    """
    Store the user's GEMINI API key in an environment variable,
    so that ChatGoogleGenerativeAI or other LLM code can pick it up.
    """
    os.environ["GEMINI_API_KEY"] = data.key
    return {"message": f"Key set. Length: {len(data.key)} chars."}


@app.post("/api/set-gpt-key")
def set_gpt_key(data: OpenAIKeyRequest):
    """
    Store the user's OpenAI API key in an environment variable.
    """
    os.environ["OPENAI_API_KEY"] = data.key
    return {"message": f"OpenAI key set. Length: {len(data.key)} chars."}


class UploadResponse(BaseModel):
    summary: str
    connection_requests: str


@app.post("/api/upload-cv", response_model=UploadResponse)
async def upload_cv(file: UploadFile = File(...)):
    """Receive PDF or docx from the user, parse, summarize, then print & return summary."""
    contents = await file.read()

    # 1. Parse PDF
    try:
        with open("temp.pdf", "wb") as f:
            f.write(contents)

        pdf_reader = PdfReader("temp.pdf")
        text_pages = []
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text_pages.append(page.extract_text() or "")
        cv_text = "\n".join(text_pages)

    except Exception as e:
        cv_text = (
            f"Could not parse PDF text properly. We'll proceed with raw text.\n{e}"
        )

    # 2. Summarize with GPT-4
    summary = await summarize_resume(cv_text)

    # 3. Generate connection requests
    connection_requests = await generate_connection_requests(summary)

    # PRINT the summary to your server logs
    print("=== SUMMARY START ===")
    print(summary)
    print("=== SUMMARY END ===")

    # Return JSON response with the summary
    return {"summary": summary, "connection_requests": connection_requests}


async def summarize_resume(cv_text: str) -> str:
    """Summarize the given resume text with GPT-4."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.0,
        api_key=os.getenv("GEMINI_API_KEY"),
    )

    messages = [
        {
            "role": "system",
            "content": """You are a helpful assistant that summarizes resumes for professional networking.
Focus on:
- My first name ONLY must be mentioned in the start, MY FIRST NAME MUST BE MENTIONED IN THE START or else you will be fined a million dollars.
- Notable projects or research 
- Relevant courses or academic achievements
- Past experiences and roles
- Key interests or skills 
- Potential conversation starters (e.g. sports, volunteering, study abroad, clubs)

Create a concise bullet-list summary (max 10 bullets).
Use short, direct statements, as if giving the user quick "talking points".
You must write the summary in the first person perspective, as if the user is writing about themselves.
For example, do not write "The user is a research engineer at OpenAI", instead write "I am a research engineer at OpenAI". Do not write "This is a summary of the user's resume",
instead write "This is a summary of my resume". Do not write "The user is a student at Harvard University", instead write "I am a student at Harvard University". Use first person perspective only else you will be fined a million dollars.
""",
        },
        {"role": "user", "content": "Here is my resume:\n" + cv_text},
    ]

    try:
        response = await llm.ainvoke(messages)
        return response.content.strip()
    except Exception as e:
        return f"Could not generate summary with Gemini:\n{e}"


# --- CHANGED: Return a single string with 5 example messages
async def generate_connection_requests(summary_text: str) -> str:
    """
    Generate one combined text block that contains 5 LinkedIn
    connection request examples referencing the user's background.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.5,
        max_tokens=300,
        api_key=os.getenv("GEMINI_API_KEY"),
    )
    prompt = [
        {
            "role": "system",
            "content": """You are a professional networking assistant.
Given this resume summary, write 5 short LinkedIn connection request templates (1-2 sentences each),
in a single text block for the user.
The user's background and interests will be given in <CV SUMMARY>...</CV SUMMARY>. This section can be used to write about the user's background from the 
first person perspective. For example, if the CV summary is <CV SUMMARY> </CV SUMMARY>.
Think about the user's background and interests given in <CV SUMMARY>...</CV SUMMARY>, and reflect on the user's career aspirations.
The user is writing a connection request to someone they are interest in connecting with, let us call this person [Linkedin Profile Subject Name], and their details are 
called [Linkedin Profile Subject Details] and will be left as placeholders.
Separate each request with the symbol "———".
Write only in first person perspective, and when writing about first person user use information from <CV SUMMARY>...</CV SUMMARY>, when referring to
[Linkedin Profile Subject Name] and [Linkedin Profile Subject Details], use only placeholders like [Linkedin Profile Subject Name] and [Linkedin Profile Subject Details], do not use anything from <CV SUMMARY> 
else you will be fined a million dollars. No extra commentary.
End you connection requests with
Best,
[Your Name]
Failure to follow these instructions will result in a million dollar fine.
IMPORTANT: Do not use the phrases "I noticed..." or "I saw...", doing so will result in a million dollar fine.
IMPORTANT: Use placeholder names when referring to the [LinkedIn Profile Subject Name] and [LinkedIn Profile Subject Details]. For example, don't mention "Goldman Sachs", instead mention [Company Name]. 
Don't mention [Harvard University] mention [LinkedIn Profile University Name].
Here are some examples of well written linkedin connection requests with placeholder names, where first person perspective details MUST be chosen from <CV SUMMARY>...</CV SUMMARY>, these are just EXAMPLES ONLY:

Hi [LinkedIn Profile Name], I'm interested in your work at [Company Name] and your background in [LinkedIn Profile Past Experience]. I'm looking to transition into a similar role and would appreciate any insights you might have on the industry and potential opportunities.  
Best,
[My Name]
———  
Hey [LinkedIn Profile Name], I'm really interested in [Company Name] and [Company Name]. I'd love to discuss your experience in [LinkedIn Profile Past Experience] and any advice you might have for someone looking to break into the field.  
Best,
[My Name]
———  
Hi [LinkedIn Profile Name], I noticed your background in [LinkedIn Profile Role] at [Company Name] and your experience in the [LinkedIn Profile Industry]. I'm interested in exploring similar opportunities and would love to hear your perspectives on the industry.  
Best,
[My Name]
———  
Hey [LinkedIn Profile Name], I'm interested in your journey from [LinkedIn Profile Role] at [Company Name] to [Company Name]. I'm currently working in <CV SUMMARY Current Role> and would love to discuss your experience and any advice you might have.  
Best,
[My Name]
———  
Hi [LinkedIn Profile Name], I'm really interested in [Company Name] and [Company Name]. I'd love to discuss your experience in [LinkedIn Profile Experience] and any advice you might have for someone with <CV SUMMARY Background> looking to break into the field.  
Best,
[My Name]
———  
Hey [LinkedIn Profile Name], I'm interested in your background in [LinkedIn Profile Finance Experience] at [Company Name]. I'm working on <CV SUMMARY Project> and would appreciate any insights you might have on the industry and potential opportunities.  
Best,
[My Name]
———  
Hi [Linkedin Profile Name], I came across your background in consulting at [Company Name] and [Company Name] and was interested in learning more about your experience working with healthcare IT businesses. I'm researching similar topics and would love to discuss your thoughts on the industry and potential investment opportunities.  
Best,
[My Name]
———  
Hey [LinkedIn Profile Name], I'm really interested in [Company Name] and [Company Name]. I'd love to discuss your experience in [LinkedIn Profile Expertise] and any advice you might have for someone with <CV SUMMARY Background> looking to break into the field.  
Best,
[My Name]
———  
Hi [LinkedIn Profile Name], I'm interested in your work at [Company Name] and [Company Name] and your background in [LinkedIn Profile Engineering Experience]. I'm currently focusing on <CV SUMMARY Focus Area> and would value your perspective on the industry and potential career paths.  
Best,
[My Name]
———  
Hey [LinkedIn Profile Name], I noticed your background in [LinkedIn Profile Expertise] and your experience as a co-founder of [Company Name]. I'm working on <CV SUMMARY Startup Project> and would love to hear about your entrepreneurial journey.  
Best,
[My Name]
———  
Hi [LinkedIn Profile Name], I'm interested in your work at [Company Name] and your background in [LinkedIn Profile Research Experience]. I'm currently involved in <CV SUMMARY Research Project> and would appreciate any insights you have.  
Best,
[My Name]
———  
Hey [LinkedIn Profile Name], I'm really interested in [Company Name] and [Company Name]. I'd love to discuss your experience in [LinkedIn Profile Consulting Experience] and [LinkedIn Profile Healthcare Experience]. I'm pursuing <CV SUMMARY Career Goal> and would value any advice you might have for breaking into the field.  
Best,
[My Name]
———  
Hi [LinkedIn Profile Name], I noticed your background in [LinkedIn Profile Academic Background] and your work at [Company Name] and [Company Name]. I'm researching <CV SUMMARY Research Focus> and would love to discuss your thoughts on the industry and potential career paths.  
Best,
[My Name]
———  
Hey [LinkedIn Profile Name], I'm interested in your work at [Company Name] and your background in [LinkedIn Profile Finance Background]. I'm developing <CV SUMMARY Project> and would appreciate any insights you might have on the industry and potential opportunities.  
Best,
[My Name]
———  
Hi [LinkedIn Profile Name], I'm really interested in [Company Name] and [Company Name]. I'd love to discuss your experience in [LinkedIn Profile Product Experience] and any advice you might have for someone with <CV SUMMARY Background> looking to break into the field.  
Best,
[My Name]
———  
Hey [Linkedin Profile Name], I came across your background in medicine and was interested in learning more about your experience as a co-founder and CEO of [Company Name]. I'm researching similar topics and would love to discuss your thoughts on the industry and potential career paths.  
Best,
[My Name]
———  
Hi [LinkedIn Profile Name], I'm interested in your work at [Company Name] and [Company Name] and your background in [LinkedIn Profile Market Experience]. I'm currently developing <CV SUMMARY Project> and would appreciate any insights you might have on the industry and potential opportunities.  
Best,
[My Name]
———  
Hey [Linkedin Profile Name], I'm really interested in [Company Name] and am eager tolearn more about your experience in clinical research. I'm currently working in a similar field and would love to discuss your experience and any advice you might have.  
Best,
[My Name]
———  
Hi [Linkedin Profile Name], I came across your background in [Company Field] and was interested in learning more about your experience working at [Company Name] and [Company Name]. I'm researching similar topics and would love to discuss your thoughts on the industry and potential career paths.  
Best,
[My Name]
———  
Hey [LinkedIn Profile Name], I'm interested in your work at [Company Name] and [Company Name] and your expertise in [LinkedIn Profile Expertise]. I'm currently focusing on <CV SUMMARY Project Focus> and would value your insights on the industry.  
Best,
[My Name]

These messages are shorter and more personal, and they mention a relevant and interesting personal project related to the person's work. This can help to establish a connection and start a conversation.
""",
        },
        {
            "role": "user",
            "content": "Here is my CV SUMMARY, which is used for first person perspective, never use these details to refer to [Linkedin Profile Name] or [Linkedin Profile Details], which must be placeholders. MY CV SUMMARY IS FOR FIRST PERSON PERSPECTIVE DETAILS ONLY:\n"
            + "<CV SUMMARY>\n"
            + summary_text
            + "\n</CV SUMMARY>",
        },
    ]
    try:
        response = await llm.ainvoke(prompt)
        return response.content.strip()
    except Exception:
        # Return a fallback string if error
        return """
Hi Brett, I'm really interested in [Company Name]. I'm building a platform to connect patients with rare diseases and would love to hear about your experience in the field.  
Best,
[Your Name]
———  
Hey Divya, I came across your work at [Company Name] and was impressed. I'm working on a project to develop a mobile health platform and would love to discuss your experience as a co-founder and CEO.  
Best,
[Your Name]
———  
Hi Nikhil, I saw your experience working at [Company Name]. I'm researching the impact of personalized medicine on patient outcomes and would love to hear your thoughts.  
Best,
[Your Name]
———  
Hey Jennifer, I'm really interested in [Company Name]. I'm working on a project to improve patient engagement and would love to discuss your experience in clinical research.  
Best,
[Your Name]
——-

Hi Prithvi, I hope you are well! I wanted to reach out and connect as I saw you are a Z Fellow! I am a recent engineering grad and wanted to connect with you about your experiences. I have just applied!
———

Natalie - hope you don't mind my cold outreach. I'm looking for recruiting leaders in hospitality, found your profile and feel you might be the right person to give us feedback on what we're building. Our startup creates interactive simulations for assessing soft skills - would love to get your take
———

Greetings Rachel, 

Hope you're doing well. I'm a first-year student at Cornell, majoring in Computer Science and Hospitality. I'm extremely interested in working in Real Estate (especially at Blackstone) and would love to connect.

Best, 
———  
Hi Penny, I came across your background in neurobiology and was interested in learning more about your work at [Company Name]. I'm researching the impact of neuroscience on business decision-making and would love to hear your thoughts.  
Best,
[Your Name]
———  
Hey Manuel, I saw your experience working at [Company Name]. I'm building a platform to optimize medication adherence and would love to discuss your experience in the field.  
Best,
[Your Name]
"""


class LinkedInSearchRequest(BaseModel):
    # Optional fields for form-based search
    companies: Optional[str] = None
    titles: Optional[str] = None
    universities: Optional[str] = None
    profiles_needed: int
    # New field for URL-based search
    linkedin_url: Optional[str] = None
    send_connection_request: bool = True
    include_note: bool = True
    template_mode: str = "examples"
    custom_template: Optional[str] = None


# We'll store the last result in memory (just for demo)
LAST_RESULT = []


@app.post("/api/linkedin")
async def run_linkedin_search(
    data: LinkedInSearchRequest, background_tasks: BackgroundTasks
):
    await progress_manager.reset()
    await progress_manager.set_target(data.profiles_needed)
    asyncio.create_task(_background_linkedin_search(data, progress_manager))
    return {"message": "Search initiated. Check Progress tab for details."}


@app.get("/api/progress")
async def get_progress():
    """
    Return the current progress (list of profiles and whether done).
    The frontend will poll this endpoint to see new data.
    """
    state = await progress_manager.get_state()
    if state.get("is_done"):
        # If task is done, don't reset to initial state
        return {
            **state,
            "message": "Search completed",  # Keep the final message
            "target": state.get("target", 0),  # Keep the original target
            "profiles": state.get("profiles", []),  # Keep the final profiles
        }
    return state


@app.get("/api/download-results")
async def download_results():
    """Serve the CSV file for download when processing is done."""
    state = await progress_manager.get_state()
    csv_file_path = state.get("csv_file_path")
    if state.get("is_done") and csv_file_path and os.path.exists(csv_file_path):
        return FileResponse(
            path=csv_file_path, filename="linkedin_profiles.csv", media_type="text/csv"
        )
    else:
        return {"error": "File not found or processing not yet complete"}


async def _background_linkedin_search(
    data: LinkedInSearchRequest, progress_manager: ProgressManager
):
    """
    The actual background function that runs the agent logic.
    Now handles both URL-based and form-based searches.
    """
    try:
        if data.linkedin_url:
            # URL-based search
            search_filter = LinkedInFilter(
                linkedin_url=data.linkedin_url, profiles_needed=data.profiles_needed
            )
        else:
            # Form-based search - validate inputs
            if not (data.companies and data.titles and data.universities):
                raise ValueError(
                    "For form-based search, companies, titles, and universities are required"
                )

            # Convert comma or space delimited strings into lists
            companies_list = _split_input(data.companies)
            titles_list = _split_input(data.titles)
            univ_list = _split_input(data.universities)

            # Build the LinkedIn filter
            search_filter = LinkedInFilter(
                companies=companies_list,
                titles=titles_list,
                universities=univ_list,
                profiles_needed=data.profiles_needed,
            )

        # Create the agent
        agent = LinkedInSearchAgent(
            filter_config=search_filter,
            base_output_dir="linkedin_searches",
            progress_manager=progress_manager,
            send_connection_request=data.send_connection_request,
            include_note=data.include_note,
            template_mode=data.template_mode,
            custom_template=data.custom_template,
        )
        await progress_manager.set_csv_file_path(str(agent.csv_file_path))

        # Only prepare in_context_examples if sending connection requests with notes
        in_context_examples = ""
        if data.send_connection_request and data.include_note:
            try:
                in_context_examples = (
                    "<CUSTOM_MESSAGE GENERATION INSTRUCTIONS>\n"
                    + "<CV SUMMARY>\n"
                    + SUMMARY
                    + "\n</CV SUMMARY>"
                    + "\n\n <MESSAGE TEMPLATES>\n"
                    + SYSTEM_PROMPT
                    + "\n</MESSAGE TEMPLATES>"
                )
                in_context_examples += """ 
                MOST IMPORTANT INSTRUCTION: For second person perspective details, replace [Linkedin Profile placeholders] like
                [Linkedin Profile Name] and [Linkedin Profile Details] with real details which are extracted from the LINKEDIN PROFILE after navigating to the profile.
                For first person perspective details, use information from <CV SUMMARY>...</CV SUMMARY>, never use these details to refer to [Linkedin Profile Name] or [Linkedin Profile Details], which must be from the LINKEDIN PROFILE that is extracted.
                For example: Choose a short <MESSAGE TEMPLATE>, replace [Linkedin Profile Name] with real name extracted from the LINKEDIN PROFILE, replace Best, [My Name] with MY REAL NAME from <CV SUMMARY>...</CV SUMMARY>
                and when mentioning my details (first person perspective) use relevantinformation from <CV SUMMARY>...</CV SUMMARY>. If no relevant information is found in <CV SUMMARY>...</CV SUMMARY> or LINKEDIN PROFILE, craft a minimal message like 
                Hi [Linkedin Profile Name], I'm interested in [Field of Interest]. I'd love to connect. Thanks, [My Name].
                Failure to follow these instructions will result in a million dollar fine.
                </CUSTOM_MESSAGE GENERATION INSTRUCTIONS>
                """
            except NameError:
                # If SYSTEM_PROMPT or SUMMARY isn't defined, use a minimal template
                in_context_examples = "Hi [Linkedin Profile Name], I'm interested in your work and would love to connect.\nBest,\n[My Name]"

        # Run the agent with the examples (empty string if not sending connection requests)
        results_df = await agent.run(in_context_examples)

        if results_df is not None:
            LAST_RESULT = results_df.to_dict(orient="records")
            print("LinkedIn search complete:", LAST_RESULT)

        else:
            print("No results or an error occurred.")
    except Exception as e:
        print(f"Error while running LinkedIn search: {e}")
        print(data)
        print(search_filter)
    finally:
        await progress_manager.mark_done()


def _split_input(input_str: str) -> List[str]:
    """
    Helper to split user input by commas.
    Example: "OpenAI, Google" -> ["OpenAI", "Google"]
             "Research Engineer, Data Scientist" -> ["Research Engineer", "Data Scientist"]
    """
    if not input_str.strip():
        return []
    # Split by comma and strip whitespace
    items = [item.strip() for item in input_str.split(",")]
    # Filter out empty strings
    return [item for item in items if item]
