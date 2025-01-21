# mimicflow/agents/linkedin/cli_linkedin.py

import argparse
import asyncio
from mimicflow.agents.linkedin.linkedin_agent import (
    LinkedInFilter,
    LinkedInSearchAgent,
)
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Run a LinkedIn search from the command line"
    )
    parser.add_argument(
        "--companies",
        nargs="+",
        required=True,
        help="List of companies, e.g. --companies OpenAI DeepMind",
    )
    parser.add_argument(
        "--universities",
        nargs="+",
        default=[],
        help="List of universities, e.g. --universities Stanford MIT",
    )
    parser.add_argument(
        "--titles",
        nargs="+",
        required=True,
        help="List of job titles, e.g. --titles Engineer Scientist",
    )
    parser.add_argument(
        "--profiles-needed",
        type=int,
        default=5,
        help="Number of profiles to scrape. Default=5.",
    )
    parser.add_argument(
        "--additional-filters",
        nargs="+",
        default=[],
        help="Additional filters, e.g. --additional-filters 'Location:NewYork'",
    )

    args = parser.parse_args()

    # Build filter config
    filter_config = LinkedInFilter(
        companies=args.companies,
        universities=args.universities,
        titles=args.titles,
        profiles_needed=args.profiles_needed,
        additional_filters=args.additional_filters,
    )

    base_output_dir = Path(__file__).parent / "linkedin_searches"
    # Create search agent
    agent = LinkedInSearchAgent(
        filter_config=filter_config,
        base_output_dir=base_output_dir,
    )

    # Actually run the search agent
    results_df = asyncio.run(agent.run())

    # Print or do something with results
    if not results_df.empty:
        print("Collected profiles:")
        print(results_df)
    else:
        print("No profiles found or an error occurred.")


if __name__ == "__main__":
    main()
