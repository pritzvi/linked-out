import os
import json
import asyncio
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from browser_use.browser.browser import Browser, BrowserConfig, BrowserContext
from browser_use import ActionResult, Agent, Controller
from mimicflow.app.progress_manager import ProgressManager


class ExtractAndSaveContent(BaseModel):
    page_number: int = Field(..., description="Current page number")
    include_links: bool = Field(
        ..., description="Whether to include links in the extracted content"
    )

    class Config:
        json_schema_extra = {"example": {"page_number": 1, "include_links": True}}


class LinkedInProfileResult(BaseModel):
    Full_Name: str = Field(...)
    Current_Title: str = Field(...)
    Company: str = Field(...)
    Location: str = Field(...)
    Education: List[str]
    Companies_Worked_At: List[str]
    Common_Interests: List[str]
    Custom_Message: str = Field(...)
    Profile_URL: str = Field(...)

    class Config:
        extra = "forbid"


class LinkedInFilter(BaseModel):
    """Structured filter for LinkedIn search"""

    # New URL field for direct search
    linkedin_url: Optional[str] = Field(None, description="LinkedIn search URL")

    # Optional fields for form-based search
    companies: Optional[List[str]] = None
    universities: Optional[List[str]] = None
    titles: Optional[List[str]] = None
    profiles_needed: int = Field(..., description="Number of profiles to collect", gt=0)
    additional_filters: Optional[List[str]] = Field(default=[])

    @model_validator(mode="after")
    def check_if_url_or_form(self) -> "LinkedInFilter":
        """Validate that either URL is provided or all form fields"""
        if not self.linkedin_url and not all(
            [self.companies, self.universities, self.titles]
        ):
            if self.linkedin_url is None:
                raise ValueError(
                    "Must provide either linkedin_url or all form fields (companies, universities, titles)"
                )
        return self

    def to_prompt_string(self) -> str:
        """Convert filter to formatted string for prompt"""
        if self.linkedin_url:
            return f"LinkedIn Search URL: {self.linkedin_url}"

        # These should never be None due to the validator
        return f"""Companies: {', '.join(self.companies or [])}
Universities: {', '.join(self.universities or [])}
Titles: {', '.join(self.titles or [])}
Additional Filters: {', '.join(self.additional_filters) if self.additional_filters else 'None'}"""


class LinkedInSearchAgent:
    def __init__(
        self,
        filter_config: LinkedInFilter,
        base_output_dir: str = "linkedin_searches",
        llm: str = "gemini-2.0-flash-exp",
        progress_manager: ProgressManager = None,
        send_connection_request: bool = True,
        include_note: bool = True,
        template_mode: str = "examples",
        custom_template: str = None,
    ):
        self.filter = filter_config
        self.send_connection_request = send_connection_request
        self.include_note = include_note
        # Assuming 10 profiles per page
        self.pages_needed = (
            filter_config.profiles_needed + 9
        ) // 10  # Ceiling division
        self.profiles_needed = filter_config.profiles_needed
        self.progress_manager = progress_manager
        self.base_dir, self.csv_file_path = self._setup_directories(base_output_dir)
        self.controller = Controller()
        self.llm = self._setup_llm(llm)
        self.browser = Browser(
            config=BrowserConfig(
                headless=False,
                chrome_instance_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            )
        )

        # Register the extract and save content action
        self._register_actions()
        self.total_profiles_collected = 0
        self.search_agent_history = None
        self.profile_agent_histories = {}  # Store histories for each profile agent
        self.template_mode = template_mode
        self.custom_template = custom_template

    def _setup_directories(self, base_dir: str) -> Path:
        """Setup directory structure for this search"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Use URL or first company/title for directory name
        if self.filter.linkedin_url:
            # Create a safe filename from the URL
            url_part = self.filter.linkedin_url.split("?")[0].split("/")[
                -1
            ]  # Get last part of URL
            search_id = f"url_search_{url_part}_{timestamp}"
        else:
            # Form-based search - use first company and title
            first_company = (
                self.filter.companies[0] if self.filter.companies else "no_company"
            )
            first_title = self.filter.titles[0] if self.filter.titles else "no_title"
            search_id = f"{first_company}_{first_title}_{timestamp}"

        # Create safe filename by removing special characters
        search_id = "".join(
            c for c in search_id if c.isalnum() or c in ("_", "-")
        ).strip()

        # Create and return the directory path
        search_path = Path(base_dir) / search_id
        search_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (search_path / "histories").mkdir(exist_ok=True)
        (search_path / "histories" / "profiles").mkdir(exist_ok=True)
        (search_path / "conversations").mkdir(exist_ok=True)
        (search_path / "conversations" / "profiles").mkdir(exist_ok=True)

        csv_file_path = search_path / "detailed_profiles.csv"

        return search_path, csv_file_path

    def _register_profile_result(self):
        @self.controller.registry.action(
            "Done with task", param_model=LinkedInProfileResult
        )
        async def done(params: LinkedInProfileResult):
            return ActionResult(
                is_done=True, extracted_content=params.model_dump_json()
            )

    def _setup_llm(self, llm: str):
        """Initialize the specified LLM"""
        load_dotenv()
        if "gemini" in llm:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY not set")
            return ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-exp",
                api_key=api_key,
                temperature=0.0,
            )
        elif "gpt" in llm or "o1" in llm:
            return (
                ChatOpenAI(model="gpt-4o", temperature=0.0)
                if "gpt" in llm
                else ChatOpenAI(model="gpt-4o")
            )
        else:
            raise ValueError(f"Unsupported LLM type: {llm}")

    def _register_actions(self):
        """Register custom actions with the controller"""

        @self.controller.registry.action(
            "Extract and save page content to a file",
            param_model=ExtractAndSaveContent,
            requires_browser=True,
        )
        async def extract_and_save_content(
            params: ExtractAndSaveContent, browser: BrowserContext
        ):
            # First use the extract_content action directly from registry
            extract_result = await self.controller.registry.execute_action(
                "extract_content",
                {"include_links": params.include_links},
                browser=browser,
            )

            # Extract the content from the result
            raw_content = extract_result.extracted_content

            # Try OpenAI first, fallback to Gemini
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                try:
                    dom_analysis_llm = ChatOpenAI(
                        model="gpt-4",
                        temperature=0.0,
                        api_key=openai_key
                    )
                except Exception as e:
                    print(f"Failed to initialize OpenAI: {e}")
                    dom_analysis_llm = None
            else:
                dom_analysis_llm = None

            # Fallback to Gemini if OpenAI fails or isn't configured
            if dom_analysis_llm is None:
                try:
                    dom_analysis_llm = ChatGoogleGenerativeAI(
                        model="gemini-2.0-flash-exp",
                        temperature=0.0,
                        api_key=os.getenv('GEMINI_API_KEY')
                    )
                except Exception as e:
                    raise Exception(f"Could not initialize any LLM service for DOM analysis: {e}")

            dom_prompt = """ 
            Your task:
            1. The user did a search on LinkedIn for profiles.
            2. Based on the above extracted page content, return a list of main profiles that resulted from the search in the format: [{"name": ..., "URL": ...}] - it must BE EXACTLY IN THE JSON FORMAT HERE, ELSE YOU WILL BE FINED A MILLION DOLLARS. Note, there might be a lot of noise on the page content due to page layout. Only return the profiles that were intended to be included in the search.

            Provide your output as follows:
            <REASONING>
            Mention your strategy for thinking about how to identify which profiles directly resulted from our search vs. what profiles might be noise due to page layout. Look at the DOM above and try to refine your strategy. Apply the strategy to identify the profiles that resulted from our search.
            </REASONING>
            <JSON>
            List of profiles, each profile should have "name" and "URL".
            </JSON>
            """

            # Create messages for LLM
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that analyzes interactive elements from the DOM of a webpage.",
                },
                {"role": "user", "content": raw_content + "\n" + dom_prompt},
            ]

            # Get LLM analysis
            llm_response = await dom_analysis_llm.ainvoke(messages)

            # Parse the LLM response
            response_content = llm_response.content

            # Extract reasoning and JSON sections
            reasoning = ""
            json_content = ""

            if "<REASONING>" in response_content and "</REASONING>" in response_content:
                reasoning = (
                    response_content.split("<REASONING>")[1]
                    .split("</REASONING>")[0]
                    .strip()
                )

            if "<JSON>" in response_content and "</JSON>" in response_content:
                json_content = (
                    response_content.split("<JSON>")[1].split("</JSON>")[0].strip()
                )

            # Update the total profiles collected
            try:
                profiles = json.loads(json_content)
                print(profiles)

                # Get existing profile URLs from progress manager
                existing_urls = {p.url for p in self.progress_manager.profiles}

                # Filter out duplicates
                unique_profiles = []
                seen_urls = set()
                for profile in profiles:
                    url = profile.get("URL", "")
                    if url and url not in seen_urls and url not in existing_urls:
                        seen_urls.add(url)
                        unique_profiles.append(profile)

                remaining_needed = self.profiles_needed - len(
                    self.progress_manager.profiles
                )
                profiles_to_add = unique_profiles[:remaining_needed]
                self.total_profiles_collected += len(profiles_to_add)

                for p in profiles_to_add:
                    # generate a new ID for each discovered profile
                    profile_id = await self.progress_manager.add_profile(
                        {"name": p.get("name", "No name"), "URL": p.get("URL", "")}
                    )
                    p["id"] = profile_id

                json_content = json.dumps(unique_profiles, indent=2)
                final_content = f"""Raw Page Content:
                {raw_content}

                Reasoning:
                {reasoning}

                JSON Output:
                {json_content}"""

            except json.JSONDecodeError:
                print(
                    f"JSON decode error in extract_and_save_content for page {params.page_number}"
                )

            # Only save if we have unique profiles
            if unique_profiles:
                filename = self.base_dir / f"page_{params.page_number}.txt"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(final_content)

            return ActionResult(
                extracted_content=f"Extracted, analyzed, and saved content for page {params.page_number} to {filename}"
            )

    def _generate_task_prompt(self) -> str:
        """Generate the task prompt based on filter configuration"""
        prompt = " # LinkedIn Search Task "
        if self.filter.linkedin_url:
            prompt += f"""
                1. Go to this specific URL: {self.filter.linkedin_url}
                2. Wait for the search results to load. On the search results page:
            """
            if self.pages_needed == 1:
                prompt += """
                    a. Use extract_and_save_content with:
                        - page_number: 1
                        - include_links: true
                    b. After extraction is complete, call done.
                """
            else:
                prompt += f"""
                    a. For each page, starting from page 1 up to page {self.pages_needed}:
                        1. Use extract_and_save_content with:
                            - page_number: current page number
                            - include_links: true
                        2. If this is page {self.pages_needed}, call done after extraction.
                        3. Otherwise:
                            - Scroll down to Next button to the end of the page to find the Next button. 
                            - Click Next to go to the next page
                        4. Repeat steps 1-3 until you reach the last page, which is {self.pages_needed}, and then call extract_and_save_content one last time. Then call done.
                """
        else:
            prompt += f"""

                <Filter>
                {self.filter.to_prompt_string()}
                </Filter>

                TASK:
                1. Go to LinkedIn search.
                2. Enter the titles in search bar: {' OR '.join(self.filter.titles)} and click enter.
                3. Click "See all people results" to expand full search.
                4. Apply filters (right sidebar in this exact order):
                    - Click "All filters".
                    - If you don't see the correct option, navigate till you see it, do not click without being sure.
                    - Decide on the correct company name that might listed on linkedin, that is, Deepmind would be Google Deepmind, YCombinator would be Y Combinator, FaceBook would be Meta, etc.
                    - Companies: Scroll down in the Filter Menu to find "Add a company". For each company in {self.filter.companies}, click on "Add a company", type in the company name, then click on the company name in the dropdown. Do not hit enter. Only select each company once.
                    - Schools: Scroll down in the filter menu to find "Add a school", For each school in {self.filter.universities}, type in the school name, then click on the school name in the dropdown. Do not hit enter. Only select each school once.
                    - Do not accidentally select any other filters.
                    - Additional Filters: {', '.join(self.filter.additional_filters) if self.filter.additional_filters else 'None'}. If additional filters like location or past companies are provided, add them as you did with companies and schools.
                5. Click "Show results".
            """
            if self.pages_needed == 1:
                prompt += """
                6. Wait for the search results to load. On the search results page:
                    a. Use extract_and_save_content with:
                        - page_number: 1
                        - include_links: true
                    b. After extraction is complete, call done.
                """
            else:
                prompt += f"""
                6. Wait for the search results to load. In the search results, follow these steps:
                    a. For each page, starting from page 1 up to page {self.pages_needed}:
                        1. Use extract_and_save_content with:
                            - page_number: current page number
                            - include_links: true
                        2. If this is page {self.pages_needed}, call done after extraction.
                        3. Otherwise:
                            - Scroll down to Next button to the end of the page to find the Next button
                            - Click Next to go to the next page
                        4. Repeat steps 1-3 until you reach the last page, which is {self.pages_needed}, and then call extract_and_save_content one last time. Then call done.
                """

        return prompt

    def collect_profiles_from_files(self) -> pd.DataFrame:
        """Parse the saved content files and collect profiles into a DataFrame."""
        profile_list = []
        for page in range(
            1, self.pages_needed + 10
        ):  # Adding extra pages in case of more profiles
            # FIXED: Changed from params.page_number to page
            filename = self.base_dir / f"page_{page}.txt"
            if not filename.exists():
                continue  # No more files to process

            # ADDED: Better error handling
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    content = f.read()

                # CHANGED: New way to check content structure
                if "Raw Page Content:" in content:
                    # ADDED: Split into sections
                    sections = content.split("\n\n")
                    json_section = None

                    # CHANGED: New way to find JSON section
                    for section in sections:
                        if section.strip().startswith("JSON Output:"):
                            json_content = section.replace("JSON Output:", "").strip()
                            try:
                                profiles = json.loads(json_content)
                                # ADDED: More validation
                                if isinstance(profiles, list):
                                    for profile in profiles:
                                        if (
                                            isinstance(profile, dict)
                                            and "name" in profile
                                            and "URL" in profile
                                        ):
                                            profile_list.append(profile)

                                            if (
                                                len(profile_list)
                                                >= self.profiles_needed
                                            ):
                                                break
                            except json.JSONDecodeError as e:
                                # ADDED: Better error message
                                print(f"JSON decode error in file {filename}: {str(e)}")
                            break

                    # ADDED: Additional error checking
                    if not json_section:
                        print(
                            f"Could not find JSON section in expected format in file {filename}"
                        )

            # ADDED: Exception handling
            except Exception as e:
                print(f"Error processing file {filename}: {str(e)}")
                continue

            if len(profile_list) >= self.profiles_needed:
                break

        # Create DataFrame
        df = pd.DataFrame(profile_list)
        # ADDED: Better feedback
        if df.empty:
            print("Warning: No profiles were successfully parsed from the files")
        else:
            print(f"Successfully parsed {len(df)} profiles")
        print(df)
        return df

    async def process_profile(self, profile: Dict, in_context_examples: str) -> Dict:
        """Navigate to the profile URL and extract detailed information."""
        profile_url = profile.get("URL")

        if not profile_url:
            print(f"No URL found for profile: {profile}")
            return {}

        profile_id = profile.get("id")
        if not profile_id:
            # fallback if no ID
            profile_id = "temp_" + str(self.total_profiles_collected + 1)

        # Update status to processing
        await self.progress_manager.update_profile(
            profile_id, status="processing", message="Processing profile..."
        )

        single_profile_browser = Browser(
            config=BrowserConfig(
                headless=False,
                chrome_instance_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            )
        )

        profile_name = profile.get("name", "unknown")
        conversations_dir = self.base_dir / "conversations" / "profiles"

        task_prompt = f"""
        1. Switch to an existing LinkedIn tab. Do not open a new tab, you will be fined a million dollars if you open a new tab.
        2. Using the existing LinkedIn tab, Go to the LinkedIn profile URL: {profile_url}.
        3a. The URL belongs to a specific user whose information we want to extract. Extract content to get all the profile information and return the following information in this exact JSON format. DO NOT USE SCROLL, you will be fined a million dollars if you use scroll. If you cannot find the information, leave it blank. 
        This is the JSON format, you must return it in this format:
        {{
        "Full_Name": "<full name from profile>",
        "Current_Title": "<current job title>",
        "Company": "<current company>",
        "Location": "<location>",
        "Education": ["<education item 1>", "<education item 2>", ...],
        "Companies_Worked_At": ["<company 1>", "<company 2>", ...],
        "Common_Interests": ["<interest 1>", "<interest 2>", ...],
        "Custom_Message": "Hi [Name], I noticed your background in [field] and would love to connect to learn more about your experience. ",
        "Profile_URL": "{profile_url}"
        }}"""

        if not self.send_connection_request:
            task_prompt += "In the Custom_Message field, prepend 'potential message: ' so that the user knows its a potential message that they can use if they want.- you must do this, else you will be fined a million dollars. Make sure to extract content and call done in the JSON format."
        elif self.send_connection_request and not self.include_note:
            task_prompt += """ 
            - When you think of clicking buttons, strictly follow the instructions below, do NOT click on anything else or you will be fined a million dollars.
                4. Click on the "Connect" button:
                
                    A. IF NO "Connect" button is visible AND you see "Follow"/"More"/"Message":
                    - Click the "More" button. DO NOT CLICK ON ANYTHING ELSE. DO NOT CLICK ON MESSAGE. DO NOT CLICK ON SEND PROFILE IN A MESSAGE. You will be fined a million dollars if you click on anything else. If "Connect" does NOT appear, click on "More" once again, DO NOT CLICK ON ANYTHING ELSE. Extract content in JSON format, Set Custom_Message: "No Connect Button Found or Already Connected", Return JSON in the above JSON format and END by calling Done.
                    - If "Connect" appears → proceed to step 5

                    B. IF you see "Following"/"More"/"Message":
                    - Click the "More" button. DO NOT CLICK ON ANYTHING ELSE. DO NOT CLICK ON MESSAGE. DO NOT CLICK ON SEND PROFILE IN A MESSAGE. You will be fined a million dollars if you click on anything else. If "Connect" does NOT appear, click on "More" once again, DO NOT CLICK ON ANYTHING ELSE. Extract content in JSON format, Set Custom_Message: "No Connect Button Found or Already Connected", Return JSON in the above JSON format and END by calling Done.
                    - If "Connect" appears → proceed to step 5
                        
                    C. IF "More" clicked but no "Connect" AND appears already connected, DO NOT CLICK ANYTHING ELSE:
                    - Click the "More" button. DO NOT CLICK ON ANYTHING ELSE. DO NOT CLICK ON MESSAGE. DO NOT CLICK ON SEND PROFILE IN A MESSAGE. You will be fined a million dollars if you click on anything else. If "Connect" does NOT appear, click on "More" once again, DO NOT CLICK ON ANYTHING ELSE. Extract content in JSON format, Set Custom_Message: "No Connect Button Found or Already Connected", Return JSON in the above JSON format and END by calling Done.
                    - If "Connect" appears → proceed to step 5
                    
                    ⚠️ IMPORTANT: NEVER click:
                    - "Message" button
                    - "Send Profile in a message" button
                    - Any other buttons not specified above
                    
                5. After successful "Connect" click:
                    - Wait for "Send without Note" button
                    - Click "Send without Note" button
                    - Set Custom_Message in JSON: "No Note", Return JSON in the above JSON format and END by calling Done.
                6. After extracting the information with extract content, call done with the exact JSON format above to return the information with Custom_Message: "No Note". You are done. END.
"""
        else:
            task_prompt += """- When you think of clicking buttons, strictly follow the instructions below, do NOT click on anything else or you will be fined a million dollars.
                4. Click on the "Connect" button:
            
                A. IF NO "Connect" button is visible AND you see "Follow"/"More"/"Message":
                - Click the "More" button. DO NOT CLICK ON ANYTHING ELSE. DO NOT CLICK ON MESSAGE. DO NOT CLICK ON SEND PROFILE IN A MESSAGE. You will be fined a million dollars if you click on anything else. If "Connect" does NOT appear, click on "More" once again, DO NOT CLICK ON ANYTHING ELSE. Extract content in JSON format, Set Custom_Message: "No Connect Button Found or Already Connected", Return JSON in the above JSON format and END by calling Done.
                - If "Connect" appears → proceed to step 5

                B. IF you see "Following"/"More"/"Message":
                - Click the "More" button. DO NOT CLICK ON ANYTHING ELSE. DO NOT CLICK ON MESSAGE. DO NOT CLICK ON SEND PROFILE IN A MESSAGE. You will be fined a million dollars if you click on anything else. If "Connect" does NOT appear, click on "More" once again, DO NOT CLICK ON ANYTHING ELSE. Extract content in JSON format, Set Custom_Message: "No Connect Button Found or Already Connected", Return JSON in the above JSON format and END by calling Done.
                - If "Connect" appears → proceed to step 5
                    
                C. IF "More" clicked but no "Connect" AND appears already connected, DO NOT CLICK ANYTHING ELSE:
                - Click the "More" button. DO NOT CLICK ON ANYTHING ELSE. DO NOT CLICK ON MESSAGE. DO NOT CLICK ON SEND PROFILE IN A MESSAGE. You will be fined a million dollars if you click on anything else. If "Connect" does NOT appear, click on "More" once again, DO NOT CLICK ON ANYTHING ELSE. Extract content in JSON format, Set Custom_Message: "No Connect Button Found or Already Connected", Return JSON in the above JSON format and END by calling Done.
                - If "Connect" appears → proceed to step 5
                
                ⚠️ IMPORTANT: NEVER click:
                - "Message" button
                - "Send Profile in a message" button
                - Any other buttons not specified above
                
                5. After successful "Connect" click:
                - Wait for "Add a note" button
                - Click "Add a note" """
            # Modify the task prompt based on template mode
            if self.template_mode == "examples":
                task_prompt += f"""
                3b. Generate a Custom_Message using this strategy: {in_context_examples}
                Make sure it's concise and less than 300 characters.
                IMPORTANT: Use my CV SUMMARY to write from first person perspective, never use these details to refer to [Linkedin Profile Name] or [Linkedin Profile Details], which must be from the LINKEDIN PROFILE that is extracted.
                ONLY USE FIRST NAME OF LINKEDIN USER IN THIS MESSAGE NOT FULL NAME.
                Use CUSTOM_MESSAGE GENERATION INSTRUCTIONS
                """
            else:
                # Use the strict template
                task_prompt += f"""
                3b. For the Custom_Message, use this EXACT template and ONLY replace the placeholders:
                - ONLY USE FIRST NAME OF LINKEDIN USER IN THIS MESSAGE NOT FULL NAME
                - Replace [linkedin profile details] with the details from the LINKEDIN PROFILE that is extracted.
                - You must not change any of the first person perspective details in the template, else you will be fined a million dollars.
                
                Template to use:
                {self.custom_template}
                
                DO NOT modify any other part of the template other than the [Linkedin Profile] placeholders. DO NOT add or remove any words.
                """

            task_prompt += f"""6. Paste the Custom_Message into the note field. Hit send.
        7. After extracting the information, call done with this exact JSON format above to return the information. You are done. END.
    {{
    "Full_Name": "<full name from LINKEDIN profile that is extracted>",
    "Current_Title": "<current job title from LINKEDIN profile that is extracted>",
    "Company": "<current company from LINKEDIN profile that is extracted>",
    "Location": "<location from LINKEDIN profile that is extracted>",
    "Education": ["<education item 1 from LINKEDIN profile that is extracted>", "<education item 2 from LINKEDIN profile that is extracted>", ...],
    "Companies_Worked_At": ["<company 1 from LINKEDIN profile that is extracted>", "<company 2 from LINKEDIN profile that is extracted>", ...],
    "Common_Interests": ["<interest 1 from LINKEDIN profile that is extracted>", "<interest 2 from LINKEDIN profile that is extracted>", ...],
    "Custom_Message": "Custom connetion message used from above",
    "Profile_URL": "{profile_url}"
    }}
        """

        try:
            # Register the LinkedInProfileResult action
            self._register_profile_result()

            # Create and run agent for this profile
            agent = Agent(
                task=task_prompt,
                llm=self.llm,
                max_actions_per_step=1,
                browser=single_profile_browser,
                controller=self.controller,
                use_vision=False,
                tool_call_in_content=False,
                save_conversation_path=str(
                    conversations_dir / f"{profile_name}_conversation"
                ),
            )

            history = await agent.run(max_steps=25)
            result = history.final_result()

            if result:
                try:
                    parsed = LinkedInProfileResult.model_validate_json(result)

                    await self.progress_manager.update_profile(
                        profile_id, status="completed", message=parsed.Custom_Message
                    )

                    return parsed.dict(), history
                except Exception as e:
                    print(
                        f"Error validating data for profile {profile.get('name')}: {e}"
                    )

                    await self.progress_manager.update_profile(
                        profile_id, status="failed", message=f"Error: {str(e)}"
                    )

                    return {}, history
            else:
                await self.progress_manager.update_profile(
                    profile_id, status="failed", message="Failed to process profile"
                )
        finally:
            await single_profile_browser.close()
        return {}

    def save_histories(self):
        """Save all agent histories"""
        histories_dir = self.base_dir / "histories"
        # histories_dir.mkdir(exist_ok=True)

        # Save main search history
        if self.search_agent_history:
            main_history_file = histories_dir / "main_search_history.json"
            try:
                self.search_agent_history.save_to_file(main_history_file)
                print(f"Saved main search history to {main_history_file}")
            except Exception as e:
                print(f"Error saving main search history: {e}")

        profiles_dir = histories_dir / "profiles"
        for profile_name, history in self.profile_agent_histories.items():
            safe_name = "".join(
                c for c in profile_name if c.isalnum() or c in (" ", "-", "_")
            ).strip()
            profile_history_file = profiles_dir / f"{safe_name}_history.json"

            try:
                history.save_to_file(profile_history_file)
                print(
                    f"Saved profile history for {profile_name} to {profile_history_file}"
                )
            except Exception as e:
                print(f"Error saving history for profile {profile_name}: {e}")

    async def run(self, in_context_examples: str) -> pd.DataFrame:
        """Run the LinkedIn search and profile collection."""
        try:
            # await self.progress_manager.set_csv_file_path(self.csv_file_path)
            # Run the initial search and extract content
            search_agent = Agent(
                task=self._generate_task_prompt(),
                llm=self.llm,
                max_actions_per_step=5,
                browser=self.browser,
                controller=self.controller,
                use_vision=False,
                tool_call_in_content=False,
                save_conversation_path=str(
                    self.base_dir / "conversations" / "main_search"
                ),
            )
            # Set a higher max_steps to allow for multiple pages
            max_steps = self.pages_needed * 10 + 20  # Adjust as needed
            self.search_agent_history = await search_agent.run(max_steps=max_steps)

            # Collect profiles from saved content
            profiles_df = self.collect_profiles_from_files()
            if profiles_df.empty:
                print("No profiles found.")
                return profiles_df

            # Ensure we have no more than the required number of profiles
            profiles_df = profiles_df.head(self.profiles_needed)

            # Process each profile and collect detailed information
            detailed_profiles = []
            for idx, profile in profiles_df.iterrows():
                profile_info = profile.to_dict()
                profile_name = profile_info.get("name", f"unknown_{idx}")
                extracted_info, profile_history = await self.process_profile(
                    profile_info, in_context_examples
                )
                if extracted_info:
                    detailed_profiles.append(extracted_info)
                    # Store single profile history JSON
                    self.profile_agent_histories[profile_name] = profile_history
                # Optionally, save after each profile
                df = pd.DataFrame(detailed_profiles)
                df.to_csv(self.base_dir / "detailed_profiles.csv", index=False)
                # Add delay to mimic human interaction and comply with policies
                await asyncio.sleep(2)

            # Save the final DataFrame
            df = pd.DataFrame(detailed_profiles)
            csv_file_path = self.base_dir / "detailed_profiles.csv"
            df.to_csv(csv_file_path, index=False)
            await self.progress_manager.set_csv_file_path(
                str(csv_file_path)
            )  # Add this line

            await self.progress_manager.mark_done()
            return df
        finally:
            await self.browser.close()
